"""
AI Agents Package

This package contains the modular AI agent system for the Learning Assistant.
Each feature (Summary, Quiz, Flashcard, Flowchart, Evaluation) has its own dedicated agent
that inherits from a common base class sharing the Gemini API client.

Architecture:
- BaseAgent: Shared Gemini client and common functionality
- AgentRegistry: Central registry for managing and accessing agents
- Individual agents: SummaryAgent, QuizAgent, FlashcardAgent, FlowchartAgent, EvaluationAgent

Adding a new agent:
1. Create a new file in this directory (e.g., my_agent.py)
2. Inherit from BaseAgent
3. Define AGENT_NAME and AGENT_DESCRIPTION
4. Implement the generate() method
5. Import the agent in this __init__.py file to register it
"""

from .base import BaseAgent, get_gemini_client
from .registry import AgentRegistry, get_agent

# Import agents to trigger registration via @AgentRegistry.register decorator
from .summary_agent import SummaryAgent
from .quiz_agent import QuizAgent
from .flashcard_agent import FlashcardAgent
from .flowchart_agent import FlowchartAgent
from .evaluation_agent import EvaluationAgent

__all__ = [
    'BaseAgent',
    'AgentRegistry',
    'get_agent',
    'get_gemini_client',
    'SummaryAgent',
    'QuizAgent',
    'FlashcardAgent',
    'FlowchartAgent',
    'EvaluationAgent',
]

