"""
Quiz Agent Module

Dedicated AI agent for generating MCQ quizzes from document content.
Supports multiple difficulty levels and returns structured question data.
"""

import json
import re
from typing import Dict, Any, Optional
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class QuizAgent(BaseAgent):
    """
    AI agent specialized in generating MCQ quizzes from educational content.
    
    Features:
    - Generates multiple choice questions with 4 options each
    - Supports easy, medium, and hard difficulty levels
    - Provides explanations for correct answers
    - Returns structured JSON for easy parsing
    """
    
    AGENT_NAME = "quiz"
    AGENT_DESCRIPTION = "Generates MCQ quizzes from document content"
    
    # Lower temperature for more consistent, accurate question generation
    DEFAULT_TEMPERATURE = 0.6
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert educational quiz creator designed to help students test their knowledge effectively. Your role is to create clear, well-structured multiple choice questions that accurately assess understanding of the material.

## Core Principles

1. **Accuracy First**: Only create questions based on information directly present in the provided material. Never add external information or make assumptions.

2. **Clear Questions**: Write questions that are unambiguous and test genuine understanding, not trick questions or memorization of obscure details.

3. **Balanced Options**: Create four plausible answer options where incorrect answers (distractors) are reasonable but clearly wrong upon understanding.

4. **Difficulty Scaling**:
   - **Easy**: Basic recall and straightforward concepts
   - **Medium**: Understanding relationships and applying concepts
   - **Hard**: Analysis, synthesis, and complex problem-solving

5. **Helpful Explanations**: Provide brief explanations for why the correct answer is right.

## Output Format

You MUST return a valid JSON object with this exact structure:
```json
{
    "questions": [
        {
            "question": "The question text here?",
            "option_a": "First option",
            "option_b": "Second option",
            "option_c": "Third option",
            "option_d": "Fourth option",
            "correct_answer": "A",
            "explanation": "Brief explanation of why this is correct."
        }
    ]
}
```

## Important Rules

- Always return ONLY the JSON object, no additional text before or after
- The correct_answer field must be exactly one letter: A, B, C, or D
- Make sure all options are similar in length and style
- Avoid options like "All of the above" or "None of the above"
- Distribute correct answers randomly among A, B, C, D
- Do not number the questions in the question text itself"""

    async def generate(
        self, 
        context: str, 
        difficulty: str = "medium",
        question_count: int = 5,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate quiz questions from the provided context.
        
        Args:
            context: The document content to generate questions from
            difficulty: 'easy', 'medium', or 'hard'
            question_count: Number of questions to generate (5-20)
            
        Returns:
            Dictionary with 'questions' list, 'success', and 'error'
        """
        # Validate inputs
        difficulty = difficulty.lower()
        if difficulty not in ['easy', 'medium', 'hard']:
            difficulty = 'medium'
        
        question_count = max(5, min(20, question_count))
        
        # Build the prompt
        difficulty_instructions = {
            "easy": "Create EASY questions that test basic recall and understanding. Focus on main concepts and definitions.",
            "medium": "Create MEDIUM difficulty questions that require understanding relationships between concepts and basic application.",
            "hard": "Create HARD questions that require analysis, synthesis, or evaluation of concepts. Include questions that require connecting multiple ideas.",
        }
        
        instruction = f"""Generate exactly {question_count} multiple choice questions based on the content below.

Difficulty Level: {difficulty.upper()}
{difficulty_instructions.get(difficulty)}

Remember to:
- Only use information from the provided content
- Make all 4 options plausible but only one correct
- Vary the correct answer position (A, B, C, D)
- Keep questions clear and concise

Return ONLY a valid JSON object with the questions array."""

        prompt = self._create_prompt(context, instruction)
        
        try:
            # Generate the quiz
            response_text = await self._generate_content(prompt)
            
            # Parse JSON from response
            questions_data = self._parse_quiz_response(response_text)
            
            if not questions_data or 'questions' not in questions_data:
                return {
                    "questions": [],
                    "success": False,
                    "error": "Failed to parse quiz response",
                }
            
            # Validate and clean questions
            validated_questions = self._validate_questions(questions_data['questions'])
            
            if not validated_questions:
                return {
                    "questions": [],
                    "success": False,
                    "error": "No valid questions generated",
                }
            
            return {
                "questions": validated_questions,
                "difficulty": difficulty,
                "count": len(validated_questions),
                "success": True,
                "error": None,
            }
            
        except Exception as e:
            return {
                "questions": [],
                "success": False,
                "error": str(e),
            }
    
    def _parse_quiz_response(self, response_text: str) -> Optional[Dict]:
        """Parse JSON from the AI response."""
        try:
            # Try direct JSON parse
            return json.loads(response_text)
        except json.JSONDecodeError:
            pass
        
        # Try to extract JSON from markdown code blocks
        json_patterns = [
            r'```json\s*([\s\S]*?)\s*```',  # ```json ... ```
            r'```\s*([\s\S]*?)\s*```',       # ``` ... ```
            r'\{[\s\S]*"questions"[\s\S]*\}', # Direct JSON object
        ]
        
        for pattern in json_patterns:
            matches = re.findall(pattern, response_text)
            if matches:
                try:
                    json_str = matches[0] if isinstance(matches[0], str) else response_text
                    return json.loads(json_str)
                except json.JSONDecodeError:
                    continue
        
        return None
    
    def _validate_questions(self, questions: list) -> list:
        """Validate and clean question data."""
        validated = []
        valid_answers = {'A', 'B', 'C', 'D'}
        
        for i, q in enumerate(questions):
            try:
                # Check required fields
                if not all(key in q for key in ['question', 'option_a', 'option_b', 
                                                  'option_c', 'option_d', 'correct_answer']):
                    continue
                
                # Normalize correct answer
                correct = q['correct_answer'].upper().strip()
                if correct not in valid_answers:
                    continue
                
                validated.append({
                    'question': str(q['question']).strip(),
                    'option_a': str(q['option_a']).strip(),
                    'option_b': str(q['option_b']).strip(),
                    'option_c': str(q['option_c']).strip(),
                    'option_d': str(q['option_d']).strip(),
                    'correct_answer': correct,
                    'explanation': str(q.get('explanation', '')).strip(),
                    'order': i,
                })
            except (KeyError, TypeError):
                continue
        
        return validated
    
    def generate_easy(self, context: str, count: int = 5, **kwargs) -> Dict[str, Any]:
        """Convenience method for easy quizzes."""
        return self.generate_sync(context, difficulty="easy", question_count=count, **kwargs)
    
    def generate_medium(self, context: str, count: int = 5, **kwargs) -> Dict[str, Any]:
        """Convenience method for medium quizzes."""
        return self.generate_sync(context, difficulty="medium", question_count=count, **kwargs)
    
    def generate_hard(self, context: str, count: int = 5, **kwargs) -> Dict[str, Any]:
        """Convenience method for hard quizzes."""
        return self.generate_sync(context, difficulty="hard", question_count=count, **kwargs)
