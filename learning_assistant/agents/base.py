"""
Base Agent Module

Contains the BaseAgent class that all AI agents inherit from.
Provides shared access to the Gemini API client and common utilities.
"""

import google.generativeai as genai
from django.conf import settings
from abc import ABC, abstractmethod
from typing import Optional, Dict, Any, List


# Singleton Gemini client instance
_gemini_client = None


def get_gemini_client():
    """
    Get or create the shared Gemini client instance.
    This ensures all agents share the same API connection.
    """
    global _gemini_client
    
    if _gemini_client is None:
        api_key = getattr(settings, 'GEMINI_API_KEY', None)
        if not api_key:
            raise ValueError(
                "GEMINI_API_KEY not configured. "
                "Please add it to your .env file and settings.py"
            )
        genai.configure(api_key=api_key)
        _gemini_client = genai
    
    return _gemini_client


class BaseAgent(ABC):
    """
    Abstract base class for all AI agents.
    
    All agents share:
    - The same Gemini API client
    - Common configuration options
    - Standard interface for generation
    
    To create a new agent:
    1. Inherit from BaseAgent
    2. Set AGENT_NAME and AGENT_DESCRIPTION class attributes
    3. Override the system_prompt property
    4. Implement the generate() method
    """
    
    # Override these in subclasses
    AGENT_NAME: str = "base"
    AGENT_DESCRIPTION: str = "Base agent class"
    
    # Default model configuration
    DEFAULT_MODEL = "gemini-2.5-flash"
    DEFAULT_TEMPERATURE = 0.7
    DEFAULT_MAX_TOKENS = 8192
    
    def __init__(
        self,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
        max_tokens: Optional[int] = None,
    ):
        """
        Initialize the agent with optional custom configuration.
        
        Args:
            model_name: Gemini model to use (default: gemini-2.0-flash)
            temperature: Generation temperature (default: 0.7)
            max_tokens: Maximum output tokens (default: 8192)
        """
        self.client = get_gemini_client()
        self.model_name = model_name or self.DEFAULT_MODEL
        self.temperature = temperature if temperature is not None else self.DEFAULT_TEMPERATURE
        self.max_tokens = max_tokens or self.DEFAULT_MAX_TOKENS
        
        # Create the model instance with configuration
        self.model = self.client.GenerativeModel(
            model_name=self.model_name,
            generation_config=genai.GenerationConfig(
                temperature=self.temperature,
                max_output_tokens=self.max_tokens,
            ),
            system_instruction=self.system_prompt,
        )
    
    @property
    @abstractmethod
    def system_prompt(self) -> str:
        """
        Return the system prompt for this agent.
        Must be implemented by all subclasses.
        """
        pass
    
    @abstractmethod
    async def generate(self, context: str, **kwargs) -> Dict[str, Any]:
        """
        Generate output based on the provided context.
        
        Args:
            context: The relevant content/context for generation
            **kwargs: Additional parameters specific to the agent
            
        Returns:
            Dictionary containing the generated output and metadata
        """
        pass
    
    def _create_prompt(self, context: str, user_request: Optional[str] = None) -> str:
        """
        Create a prompt combining context and optional user request.
        
        Args:
            context: The document/content context
            user_request: Optional specific user instructions
            
        Returns:
            Formatted prompt string
        """
        prompt_parts = [
            "## Content to Process",
            context,
        ]
        
        if user_request:
            prompt_parts.extend([
                "",
                "## User Request",
                user_request,
            ])
        
        return "\n".join(prompt_parts)
    
    async def _generate_content(self, prompt: str) -> str:
        """
        Generate content using the Gemini model.
        
        Args:
            prompt: The formatted prompt
            
        Returns:
            Generated text response
        """
        response = await self.model.generate_content_async(prompt)
        return response.text
    
    def generate_sync(self, context: str, **kwargs) -> Dict[str, Any]:
        """
        Synchronous version of generate for use in Django views.
        
        Args:
            context: The relevant content/context for generation
            **kwargs: Additional parameters specific to the agent
            
        Returns:
            Dictionary containing the generated output and metadata
        """
        import asyncio
        
        # Get or create event loop
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
        
        return loop.run_until_complete(self.generate(context, **kwargs))
    
    def __repr__(self) -> str:
        return f"<{self.__class__.__name__}(model={self.model_name})>"
