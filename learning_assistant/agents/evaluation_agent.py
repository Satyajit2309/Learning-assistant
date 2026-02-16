"""
Evaluation Agent for Answer Sheet Grading

Uses Gemini Vision to directly analyze handwritten answer sheets
and provide percentage-based scoring with detailed feedback.
"""

import json
import base64
from pathlib import Path
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class EvaluationAgent(BaseAgent):
    """Agent for evaluating handwritten answer sheets using Gemini Vision."""
    
    AGENT_NAME = "evaluation"
    AGENT_DESCRIPTION = "Evaluates handwritten answer sheets using AI vision and provides detailed feedback"
    
    @property
    def system_prompt(self) -> str:
        """System prompt for the evaluation agent."""
        return """You are an expert teacher and evaluator specializing in grading handwritten answer sheets.
Your role is to carefully analyze student submissions and provide fair, constructive feedback."""

    async def generate(self, context: str, **kwargs) -> dict:
        """
        Async wrapper for evaluation. Uses generate_sync internally.
        For vision-based evaluation, use generate_sync directly with image_path.
        """
        return self.generate_sync(context, **kwargs)
    
    def _build_prompt(self, difficulty: int = 5, reference_content: str = None) -> str:
        """Build the evaluation prompt based on difficulty and reference material."""
        
        # Difficulty descriptions
        difficulty_guides = {
            1: "Be very lenient. Accept any reasonable attempt that shows understanding.",
            2: "Be lenient. Focus on core concepts, ignore minor errors.",
            3: "Be somewhat lenient. Accept partial answers that show effort.",
            4: "Use standard grading. Balance accuracy with understanding.",
            5: "Use standard grading. Expect correct answers with reasonable explanations.",
            6: "Use standard grading. Look for completeness and accuracy.",
            7: "Be strict. Expect precise and complete answers.",
            8: "Be strict. Deduct points for incomplete or imprecise answers.",
            9: "Be very strict. Expect near-perfect answers with proper terminology.",
            10: "Be extremely strict. Only perfect, comprehensive answers get full marks."
        }
        
        grading_guide = difficulty_guides.get(difficulty, difficulty_guides[5])
        
        reference_section = ""
        if reference_content:
            # Truncate reference if too long
            max_ref_chars = 6000
            if len(reference_content) > max_ref_chars:
                reference_content = reference_content[:max_ref_chars] + "\n\n[... Reference truncated ...]"
            
            reference_section = f"""
## Reference Material
Use this reference material to evaluate the accuracy of answers:

{reference_content}

---
"""
        
        prompt = f"""You are an expert teacher evaluating a student's handwritten answer sheet.

## Your Task
1. Look at the uploaded image of the answer sheet
2. Identify each question and the student's written answer
3. Evaluate each answer based on correctness and completeness
4. Provide a percentage score (0-100) for each question
5. Give specific feedback for improvement

## Grading Guidelines
Difficulty Level: {difficulty}/10
{grading_guide}

{reference_section}

## Response Format
You MUST respond with valid JSON in exactly this format:
{{
    "questions": [
        {{
            "question_text": "The question as you read it from the sheet",
            "student_answer": "What the student wrote",
            "ideal_answer": "What the correct/ideal answer should be",
            "score_percentage": 85,
            "feedback": "Specific feedback about this answer"
        }}
    ],
    "overall_score": 78.5,
    "general_feedback": "Overall feedback about the student's performance"
}}

## Important Notes
- Read the handwriting carefully, even if messy
- If you can't read something, note it in the feedback
- Score each question individually from 0-100
- The overall_score should be the average of all question scores
- Be constructive in your feedback
- If no questions are visible, return an error message

Analyze the answer sheet image now and provide your evaluation."""

        return prompt
    
    def _encode_image(self, image_path: str) -> tuple:
        """Encode image to base64 and determine mime type."""
        path = Path(image_path)
        
        extension = path.suffix.lower()
        mime_types = {
            '.jpg': 'image/jpeg',
            '.jpeg': 'image/jpeg',
            '.png': 'image/png',
            '.gif': 'image/gif',
            '.webp': 'image/webp',
        }
        
        mime_type = mime_types.get(extension, 'image/jpeg')
        
        with open(image_path, 'rb') as f:
            image_data = base64.b64encode(f.read()).decode('utf-8')
        
        return image_data, mime_type
    
    def generate_sync(
        self,
        image_path: str,
        difficulty: int = 5,
        reference_content: str = None,
        **kwargs
    ) -> dict:
        """
        Evaluate an answer sheet image using Gemini Vision.
        
        Args:
            image_path: Path to the answer sheet image
            difficulty: Grading strictness (1-10)
            reference_content: Optional reference material text
            
        Returns:
            dict with 'success', 'questions', 'overall_score', 'general_feedback'
        """
        try:
            # Build the prompt
            prompt = self._build_prompt(difficulty, reference_content)
            
            # Encode the image
            image_data, mime_type = self._encode_image(image_path)
            
            # Create the message with image
            message_parts = [
                {
                    "inline_data": {
                        "mime_type": mime_type,
                        "data": image_data
                    }
                },
                prompt
            ]
            
            # Call Gemini with vision
            response = self.model.generate_content(message_parts)
            
            # Parse the response
            response_text = response.text.strip()
            
            # Clean up markdown code blocks if present
            if response_text.startswith('```'):
                lines = response_text.split('\n')
                if lines[0].startswith('```'):
                    lines = lines[1:]
                if lines and lines[-1].strip() == '```':
                    lines = lines[:-1]
                response_text = '\n'.join(lines)
            
            # Parse JSON
            try:
                result = json.loads(response_text)
            except json.JSONDecodeError:
                # Try to extract JSON from the response
                import re
                json_match = re.search(r'\{[\s\S]*\}', response_text)
                if json_match:
                    result = json.loads(json_match.group())
                else:
                    return {
                        'success': False,
                        'error': f'Could not parse evaluation response as JSON'
                    }
            
            # Validate and normalize
            questions = result.get('questions', [])
            if not questions:
                return {
                    'success': False,
                    'error': 'No questions found in the answer sheet'
                }
            
            # Add order to questions
            for i, q in enumerate(questions):
                q['order'] = i + 1
                # Ensure score is within bounds
                q['score_percentage'] = max(0, min(100, float(q.get('score_percentage', 0))))
            
            # Calculate overall score if not provided
            overall_score = result.get('overall_score')
            if overall_score is None:
                scores = [q['score_percentage'] for q in questions]
                overall_score = sum(scores) / len(scores) if scores else 0
            else:
                overall_score = max(0, min(100, float(overall_score)))
            
            return {
                'success': True,
                'questions': questions,
                'overall_score': overall_score,
                'general_feedback': result.get('general_feedback', 'Evaluation complete.')
            }
            
        except Exception as e:
            import traceback
            print(traceback.format_exc())
            return {
                'success': False,
                'error': str(e)
            }



