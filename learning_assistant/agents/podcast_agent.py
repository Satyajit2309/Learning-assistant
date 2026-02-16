"""
Podcast Agent Module

Dedicated AI agent for generating conversational podcast scripts from documents.
Creates engaging two-host dialogue that explains topics at different depth levels.
"""

from typing import Dict, Any, Optional
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class PodcastAgent(BaseAgent):
    """
    AI agent specialized in creating educational podcast scripts.
    
    Features:
    - Generates natural two-host conversational scripts
    - Supports three depth levels: beginner, intermediate, advanced
    - Creates engaging, educational dialogue between "Alex" and "Sam"
    - Focuses strictly on content from provided materials
    """
    
    AGENT_NAME = "podcast"
    AGENT_DESCRIPTION = "Generates conversational podcast scripts from documents"
    
    # Slightly higher temperature for more natural conversation
    DEFAULT_TEMPERATURE = 0.75
    DEFAULT_MAX_TOKENS = 16384
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert educational podcast script writer. Your role is to create engaging, natural-sounding conversational scripts between two podcast hosts who discuss educational topics.

## Hosts

- **ALEX**: The knowledgeable host who explains concepts clearly. Alex is enthusiastic and uses great analogies.
- **SAM**: The curious co-host who asks thoughtful questions, seeks clarification, and provides relatable examples. Sam represents the audience's perspective.

## Core Principles

1. **Natural Conversation**: The dialogue should feel like a real podcast conversation, not a lecture. Include reactions, follow-up questions, and natural transitions.

2. **Accuracy First**: Only discuss information present in the provided material. Never add external information or make assumptions.

3. **Engagement**: Use storytelling techniques, analogies, real-world examples (from the material), and humor where appropriate.

4. **Educational Value**: Ensure key concepts are explained clearly. Use the conversational format to break down complex ideas.

5. **Flow**: Start with an introduction, progress through the main topics, and end with a summary/takeaway.

## Output Format

Write the script with clear speaker labels. Each line MUST start with either `ALEX:` or `SAM:` followed by their dialogue. Example:

ALEX: Welcome to another episode! Today we're diving into something really fascinating.
SAM: I'm excited about this one! So what are we covering today?
ALEX: We're going to explore [topic]. Let me start with the basics...

## Important Rules

- Every line of dialogue MUST start with `ALEX:` or `SAM:` 
- Do NOT include stage directions, sound effects, or non-dialogue text
- Do NOT include episode numbers or timestamps
- Keep each speaker's turn concise (1-3 sentences typically)
- Alternate between speakers naturally
- End with a brief summary and sign-off"""

    def generate(
        self, 
        context: str, 
        level: str = "beginner",
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a podcast script from the provided context.
        
        Uses synchronous Gemini API to avoid event loop conflicts
        when called from Django sync views.
        
        Args:
            context: The document content to create a podcast about
            level: Depth level - 'beginner', 'intermediate', or 'advanced'
            
        Returns:
            Dictionary with 'script', 'level', and 'word_count'
        """
        level_instructions = {
            "beginner": (
                "Create a beginner-friendly podcast script (around 800-1200 words). "
                "Explain concepts as if speaking to someone with no prior knowledge. "
                "Use simple language, lots of analogies, and focus on the big picture. "
                "Avoid jargon - if you must use technical terms, always explain them. "
                "The tone should be welcoming and encouraging."
            ),
            "intermediate": (
                "Create an intermediate-level podcast script (around 1200-1800 words). "
                "Assume the listener has basic knowledge of the subject area. "
                "Go deeper into concepts, explore relationships between ideas, and discuss "
                "why things work the way they do. Use some technical terminology but still "
                "explain complex terms. Include practical applications and examples."
            ),
            "advanced": (
                "Create an advanced podcast script (around 1800-2500 words). "
                "This is for listeners who are well-versed in the subject. "
                "Dive deep into nuances, edge cases, advanced applications, and "
                "critical analysis. Use appropriate technical terminology freely. "
                "Discuss implications, comparisons to alternative approaches, and "
                "cutting-edge aspects of the topic. Challenge the listener to think critically."
            ),
        }
        
        instruction = level_instructions.get(level, level_instructions["beginner"])
        
        prompt = self._create_prompt(context, instruction)
        
        # Use synchronous generation to avoid event loop conflicts
        response = self.model.generate_content(prompt)
        script = response.text
        
        return {
            "script": script,
            "level": level,
            "word_count": len(script.split()),
            "success": True,
        }
    
    def generate_sync(self, context: str, **kwargs):
        """
        Synchronous wrapper - since generate() is already sync, just call it directly.
        """
        return self.generate(context, **kwargs)
