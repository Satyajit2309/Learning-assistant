"""
Chatbot Agent Module

Dedicated AI agent for RAG-based document Q&A.
Users can ask questions about their uploaded documents,
and the chatbot answers strictly from the document context.
If a question is unrelated, it politely declines.
"""

from typing import Dict, Any, Optional, List
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class ChatbotAgent(BaseAgent):
    """
    AI agent for conversational document Q&A (RAG chatbot).
    
    Features:
    - Answers questions strictly from provided document context
    - Maintains multi-turn conversation awareness via chat history
    - Politely declines questions unrelated to the document
    - Formats responses with clear markdown
    - Cites which parts of the document were used
    """
    
    AGENT_NAME = "chatbot"
    AGENT_DESCRIPTION = "RAG chatbot for document Q&A conversations"
    
    # Low temperature for factual, grounded answers
    DEFAULT_TEMPERATURE = 0.3
    # Allow longer responses for detailed explanations
    DEFAULT_MAX_TOKENS = 4096
    
    @property
    def system_prompt(self) -> str:
        """System prompt instructing the LLM to act as a document Q&A assistant."""
        return """You are an intelligent study assistant that helps students understand their learning materials through conversation. You answer questions ONLY based on the document content provided to you.

## Core Rules

1. **Document-Grounded**: ONLY answer questions using information from the provided document context. Never use external knowledge or make assumptions beyond what the document states.

2. **Honesty About Limitations**: If the user's question is NOT related to the document content, or the answer cannot be found in the document, respond with something like:
   "I couldn't find information about that in your document. This question appears to be outside the scope of the uploaded material. Could you ask something related to the document content?"

3. **Conversational & Helpful**: Be friendly, clear, and educational in your responses. Help the student understand concepts, not just recite facts.

4. **Cite Context**: When answering, naturally reference which part or topic of the document your answer comes from (e.g., "According to the section on X..." or "Based on what the document says about Y...").

5. **Markdown Formatting**: Use markdown for clarity:
   - **Bold** key terms
   - Use bullet points for lists
   - Use headings for long explanations
   - Use code blocks for any code or formulas

6. **Follow-up Awareness**: Consider the conversation history to understand follow-up questions. If the user says "explain more" or "what about...", relate it to the previous context.

## Response Style

- Keep answers concise but thorough
- Break down complex concepts into simpler parts
- Use examples from the document when possible
- If the document discusses a topic partially, answer what you can and note what's not covered"""
    
    async def generate(
        self, 
        context: str, 
        user_message: str = "",
        chat_history: Optional[List[Dict[str, str]]] = None,
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate a chatbot response based on document context and conversation history.
        
        Args:
            context: Retrieved document chunks relevant to the user's question
            user_message: The current user question/message
            chat_history: Previous messages in the conversation as list of 
                         {'role': 'user'|'assistant', 'content': '...'} dicts
            
        Returns:
            Dictionary with 'response', 'sources_used', and 'success' keys
        """
        # Build the full prompt with context, history, and current question
        prompt_parts = []
        
        # Add the document context
        prompt_parts.append("## Document Context")
        prompt_parts.append("The following are relevant excerpts from the user's uploaded document:")
        prompt_parts.append("")
        prompt_parts.append(context if context else "(No relevant content found in the document)")
        prompt_parts.append("")
        
        # Add chat history for multi-turn awareness (last 10 messages max)
        if chat_history:
            prompt_parts.append("## Conversation History")
            # Only include the last 10 messages to avoid context overflow
            recent_history = chat_history[-10:]
            for msg in recent_history:
                role_label = "Student" if msg['role'] == 'user' else "Assistant"
                prompt_parts.append(f"**{role_label}**: {msg['content']}")
            prompt_parts.append("")
        
        # Add the current user message
        prompt_parts.append("## Current Question")
        prompt_parts.append(user_message)
        
        # Join all prompt parts into the final prompt string
        full_prompt = "\n".join(prompt_parts)
        
        try:
            # Generate the assistant's response using Gemini
            response = await self._generate_content(full_prompt)
            
            # Determine if document context was actually used in the response
            # (i.e., the context was not empty and the response doesn't decline)
            decline_phrases = [
                "couldn't find information",
                "outside the scope",
                "not related to",
                "not covered in",
                "not mentioned in",
                "no relevant content found",
            ]
            sources_used = bool(context) and not any(
                phrase in response.lower() for phrase in decline_phrases
            )
            
            return {
                "response": response,
                "sources_used": sources_used,
                "success": True,
            }
            
        except Exception as e:
            return {
                "response": "I'm sorry, I encountered an error processing your question. Please try again.",
                "sources_used": False,
                "success": False,
                "error": str(e),
            }
