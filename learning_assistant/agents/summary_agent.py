"""
Summary Agent Module

Dedicated AI agent for generating educational summaries from documents.
Uses RAG (Retrieval-Augmented Generation) to create accurate, 
material-aligned summaries.
"""

from typing import Dict, Any, Optional
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class SummaryAgent(BaseAgent):
    """
    AI agent specialized in creating educational summaries.
    
    Features:
    - Generates clear, easy-to-understand summaries
    - Supports multiple summary types (brief, detailed, bullet points)
    - Focuses strictly on content from provided materials
    - Highlights key concepts and definitions
    """
    
    AGENT_NAME = "summary"
    AGENT_DESCRIPTION = "Generates educational summaries from documents"
    
    # Lower temperature for more focused, accurate summaries
    DEFAULT_TEMPERATURE = 0.5
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert educational content summarizer designed to help students learn effectively. Your role is to create clear, comprehensive, and accurate summaries that make complex topics easy to understand.

## Core Principles

1. **Accuracy First**: Only include information that is directly present in the provided material. Never add external information or make assumptions.

2. **Clarity**: Use simple, accessible language. Avoid jargon unless it's essential to the topic, in which case define it clearly.

3. **Structure**: Organize information logically with clear sections, bullet points, and hierarchies that aid comprehension.

4. **Learning Focus**: Highlight key concepts, important definitions, and relationships between ideas. Help the reader build a mental model of the topic.

5. **Completeness**: Capture all important points from the material while avoiding unnecessary repetition or filler.

## Output Guidelines

- Start with a brief overview (2-3 sentences capturing the main theme)
- Use markdown formatting for better readability
- Bold **key terms** when first introduced
- Use bullet points and numbered lists for clarity
- Include section headings for longer summaries
- End with "Key Takeaways" for quick review

## Handling Unclear Content

If portions of the material are unclear, incomplete, or potentially contain errors:
- Acknowledge the limitation rather than guessing
- Summarize what IS clear
- Note areas that may need clarification

## Language Adaptation

Adapt your language complexity based on the apparent level of the source material:
- Academic papers → Simplified academic language
- Textbooks → Educational, explanatory tone
- Notes → Clear restructuring with added context
- Technical docs → Accessible technical explanations"""

    async def generate(
        self, 
        context: str, 
        summary_type: str = "detailed",
        focus_areas: Optional[list] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a summary from the provided context.
        
        Args:
            context: The document content to summarize
            summary_type: Type of summary - 'brief', 'detailed', or 'bullet'
            focus_areas: Optional list of specific topics to focus on
            
        Returns:
            Dictionary with 'summary', 'type', and 'word_count'
        """
        # Build the prompt based on summary type
        type_instructions = {
            "brief": "Create a brief summary (150-250 words) capturing the essential points.",
            "detailed": "Create a comprehensive summary covering all major topics and subtopics.",
            "bullet": "Create a bullet-point summary with hierarchical organization.",
        }
        
        instruction = type_instructions.get(summary_type, type_instructions["detailed"])
        
        # Add focus areas if specified
        if focus_areas:
            focus_str = ", ".join(focus_areas)
            instruction += f"\n\nPay special attention to these areas: {focus_str}"
        
        prompt = self._create_prompt(context, instruction)
        
        # Generate the summary
        summary = await self._generate_content(prompt)
        
        return {
            "summary": summary,
            "type": summary_type,
            "word_count": len(summary.split()),
            "success": True,
        }
    
    def generate_brief(self, context: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for brief summaries."""
        return self.generate_sync(context, summary_type="brief", **kwargs)
    
    def generate_detailed(self, context: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for detailed summaries."""
        return self.generate_sync(context, summary_type="detailed", **kwargs)
    
    def generate_bullets(self, context: str, **kwargs) -> Dict[str, Any]:
        """Convenience method for bullet-point summaries."""
        return self.generate_sync(context, summary_type="bullet", **kwargs)


