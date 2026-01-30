"""
Flashcard Agent Module

Dedicated AI agent for generating flashcards from document content.
Extracts key concepts and creates prioritized study cards.
"""

import json
import re
from typing import Dict, Any, Optional
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class FlashcardAgent(BaseAgent):
    """
    AI agent specialized in generating flashcards from educational content.
    
    Features:
    - Extracts key concepts, terms, and important points
    - Creates front (question/concept) and back (answer/explanation) pairs
    - Prioritizes content based on importance (1-5 scale)
    - Adjusts detail level based on requested card count
    """
    
    AGENT_NAME = "flashcard"
    AGENT_DESCRIPTION = "Generates flashcards from document content"
    
    # Moderate temperature for balanced creativity and accuracy
    DEFAULT_TEMPERATURE = 0.5
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert educational content creator specializing in creating effective flashcards for learning and memorization. Your goal is to extract the most important concepts from educational material and create clear, concise flashcards.

## Core Principles

1. **Extract Key Concepts**: Identify the most important terms, definitions, concepts, facts, and relationships from the material.

2. **Priority-Based Selection**: 
   - Priority 1 (Critical): Core concepts that are fundamental to understanding the topic
   - Priority 2 (Very Important): Key supporting concepts and definitions
   - Priority 3 (Important): Significant details and relationships
   - Priority 4 (Helpful): Useful supplementary information
   - Priority 5 (Supplementary): Additional details for deeper understanding

3. **Clear Card Design**:
   - **Front**: A clear question, term, or concept prompt (keep concise)
   - **Back**: A complete but concise answer or explanation

4. **Adaptive Detail**:
   - Fewer cards requested = Focus only on the most critical concepts
   - More cards requested = Include more detailed and supplementary information

5. **Learning Optimization**:
   - Each card should test ONE concept
   - Avoid overly complex or multi-part answers
   - Use clear, simple language

## Output Format

You MUST return a valid JSON object with this exact structure:
```json
{
    "flashcards": [
        {
            "front": "What is [concept]?",
            "back": "Clear, concise explanation or definition",
            "priority": 1
        }
    ]
}
```

## Important Rules

- Always return ONLY the JSON object, no additional text
- Priority must be an integer from 1 to 5
- Front should be concise (ideally under 100 characters)
- Back should be comprehensive but not overwhelming (under 300 characters)
- Order flashcards by priority (most important first)
- Only use information from the provided content"""

    async def generate(
        self, 
        context: str, 
        card_count: int = 10,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate flashcards from the provided context.
        
        Args:
            context: The document content to extract flashcards from
            card_count: Number of flashcards to generate (5-30)
            
        Returns:
            Dictionary with 'flashcards' list, 'success', and 'error'
        """
        # Validate inputs
        card_count = max(5, min(30, card_count))
        
        # Adjust instructions based on card count
        if card_count <= 5:
            detail_instruction = "Focus ONLY on the most critical and fundamental concepts. Each card must cover an absolutely essential point."
        elif card_count <= 10:
            detail_instruction = "Focus on critical and very important concepts. Cover the core material thoroughly."
        elif card_count <= 15:
            detail_instruction = "Include critical, very important, and important concepts. Provide good coverage of the material."
        elif card_count <= 20:
            detail_instruction = "Include all important concepts plus helpful supplementary information for comprehensive coverage."
        else:
            detail_instruction = "Create comprehensive coverage including all concepts from critical to supplementary. Include detailed information for thorough study."
        
        instruction = f"""Generate exactly {card_count} flashcards based on the content below.

{detail_instruction}

Guidelines:
- Start with the most important concepts (priority 1-2)
- Fill remaining cards with progressively less critical content
- Each flashcard should be self-contained and test one concept
- Front: Clear question or concept prompt
- Back: Concise but complete answer

Return ONLY a valid JSON object with the flashcards array."""

        prompt = self._create_prompt(context, instruction)
        
        try:
            # Generate the flashcards
            response_text = await self._generate_content(prompt)
            
            # Parse JSON from response
            flashcards_data = self._parse_flashcard_response(response_text)
            
            if not flashcards_data or 'flashcards' not in flashcards_data:
                return {
                    "flashcards": [],
                    "success": False,
                    "error": "Failed to parse flashcard response",
                }
            
            # Validate and clean flashcards
            validated_flashcards = self._validate_flashcards(flashcards_data['flashcards'])
            
            if not validated_flashcards:
                return {
                    "flashcards": [],
                    "success": False,
                    "error": "No valid flashcards generated",
                }
            
            return {
                "flashcards": validated_flashcards,
                "count": len(validated_flashcards),
                "success": True,
                "error": None,
            }
            
        except Exception as e:
            return {
                "flashcards": [],
                "success": False,
                "error": str(e),
            }
    
    def _parse_flashcard_response(self, response_text: str) -> Optional[Dict]:
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
            r'\{[\s\S]*"flashcards"[\s\S]*\}', # Direct JSON object
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
    
    def _validate_flashcards(self, flashcards: list) -> list:
        """Validate and clean flashcard data."""
        validated = []
        
        for i, card in enumerate(flashcards):
            try:
                # Check required fields
                if not all(key in card for key in ['front', 'back']):
                    continue
                
                # Get and validate priority
                priority = card.get('priority', 3)
                if isinstance(priority, str):
                    try:
                        priority = int(priority)
                    except ValueError:
                        priority = 3
                priority = max(1, min(5, priority))
                
                # Clean and validate content
                front = str(card['front']).strip()
                back = str(card['back']).strip()
                
                if not front or not back:
                    continue
                
                validated.append({
                    'front': front,
                    'back': back,
                    'priority': priority,
                    'order': i,
                })
            except (KeyError, TypeError):
                continue
        
        # Sort by priority
        validated.sort(key=lambda x: (x['priority'], x['order']))
        
        # Re-assign order after sorting
        for i, card in enumerate(validated):
            card['order'] = i
        
        return validated
    
    def generate_quick(self, context: str, count: int = 5, **kwargs) -> Dict[str, Any]:
        """Convenience method for quick flashcard generation (5 cards)."""
        return self.generate_sync(context, card_count=count, **kwargs)
    
    def generate_standard(self, context: str, count: int = 10, **kwargs) -> Dict[str, Any]:
        """Convenience method for standard flashcard generation (10 cards)."""
        return self.generate_sync(context, card_count=count, **kwargs)
    
    def generate_comprehensive(self, context: str, count: int = 20, **kwargs) -> Dict[str, Any]:
        """Convenience method for comprehensive flashcard generation (20 cards)."""
        return self.generate_sync(context, card_count=count, **kwargs)
