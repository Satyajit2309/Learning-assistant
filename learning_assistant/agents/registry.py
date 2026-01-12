"""
Agent Registry Module

Provides a central registry for managing AI agents.
Agents are automatically registered when their modules are imported.
This allows seamless addition of new agents without modifying existing code.
"""

from typing import Dict, Type, Optional
from .base import BaseAgent


class AgentRegistry:
    """
    Central registry for all AI agents.
    
    Usage:
        # Register an agent
        AgentRegistry.register(SummaryAgent)
        
        # Get an agent instance
        agent = AgentRegistry.get('summary')
        
        # List all available agents
        agents = AgentRegistry.list_agents()
    """
    
    _agents: Dict[str, Type[BaseAgent]] = {}
    _instances: Dict[str, BaseAgent] = {}
    
    @classmethod
    def register(cls, agent_class: Type[BaseAgent]) -> Type[BaseAgent]:
        """
        Register an agent class with the registry.
        Can be used as a decorator.
        
        Args:
            agent_class: The agent class to register
            
        Returns:
            The registered agent class (for decorator usage)
        """
        if not hasattr(agent_class, 'AGENT_NAME'):
            raise ValueError(f"Agent class {agent_class.__name__} must define AGENT_NAME")
        
        agent_name = agent_class.AGENT_NAME.lower()
        cls._agents[agent_name] = agent_class
        
        return agent_class
    
    @classmethod
    def get(cls, agent_name: str, **kwargs) -> BaseAgent:
        """
        Get an agent instance by name.
        Creates a new instance or returns cached one.
        
        Args:
            agent_name: Name of the agent to retrieve
            **kwargs: Optional configuration for the agent
            
        Returns:
            Agent instance
            
        Raises:
            KeyError: If agent is not registered
        """
        agent_name = agent_name.lower()
        
        if agent_name not in cls._agents:
            available = ", ".join(cls._agents.keys())
            raise KeyError(
                f"Agent '{agent_name}' not found. "
                f"Available agents: {available or 'none registered'}"
            )
        
        # Create new instance if kwargs provided or not cached
        cache_key = f"{agent_name}_{hash(frozenset(kwargs.items()))}" if kwargs else agent_name
        
        if cache_key not in cls._instances:
            cls._instances[cache_key] = cls._agents[agent_name](**kwargs)
        
        return cls._instances[cache_key]
    
    @classmethod
    def list_agents(cls) -> Dict[str, str]:
        """
        List all registered agents with their descriptions.
        
        Returns:
            Dictionary mapping agent names to descriptions
        """
        return {
            name: agent_class.AGENT_DESCRIPTION
            for name, agent_class in cls._agents.items()
        }
    
    @classmethod
    def is_registered(cls, agent_name: str) -> bool:
        """Check if an agent is registered."""
        return agent_name.lower() in cls._agents
    
    @classmethod
    def clear_cache(cls) -> None:
        """Clear cached agent instances."""
        cls._instances.clear()
    
    @classmethod
    def unregister(cls, agent_name: str) -> None:
        """Remove an agent from the registry."""
        agent_name = agent_name.lower()
        cls._agents.pop(agent_name, None)
        # Also remove any cached instances
        keys_to_remove = [k for k in cls._instances if k.startswith(agent_name)]
        for key in keys_to_remove:
            cls._instances.pop(key, None)


def get_agent(agent_name: str, **kwargs) -> BaseAgent:
    """
    Convenience function to get an agent from the registry.
    
    Args:
        agent_name: Name of the agent to retrieve
        **kwargs: Optional configuration for the agent
        
    Returns:
        Agent instance
    """
    return AgentRegistry.get(agent_name, **kwargs)
