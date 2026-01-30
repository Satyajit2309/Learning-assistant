"""
Flowchart Agent Module

Dedicated AI agent for generating concept flowcharts from document content.
Produces structured node and edge data for interactive visualization.
"""

import json
import re
from typing import Dict, Any, Optional
from .base import BaseAgent
from .registry import AgentRegistry


@AgentRegistry.register
class FlowchartAgent(BaseAgent):
    """
    AI agent specialized in generating concept flowcharts from educational content.
    
    Features:
    - Generates nodes with labels and types (concept/action/decision/start/end)
    - Creates edges connecting related concepts
    - Returns structured JSON for visualization
    - Supports configurable node counts (5-20)
    """
    
    AGENT_NAME = "flowchart"
    AGENT_DESCRIPTION = "Generates concept flowcharts from document content"
    
    # Lower temperature for structured, logical output
    DEFAULT_TEMPERATURE = 0.5
    
    @property
    def system_prompt(self) -> str:
        return """You are an expert educational content visualizer designed to help students understand complex topics through flowcharts and concept maps. Your role is to analyze educational content and create clear, logical flowcharts that show relationships between concepts.

## Core Principles

1. **Accuracy First**: Only create nodes based on information directly present in the provided material. Never add external information or make assumptions.

2. **Logical Flow**: Create meaningful connections between concepts. The flowchart should tell a coherent story or explain a process.

3. **Node Types**:
   - **start**: Entry point of the flowchart (usually one)
   - **end**: Exit/conclusion point (usually one)
   - **concept**: Key ideas, definitions, or facts
   - **action**: Steps, processes, or procedures
   - **decision**: Questions or branching points

4. **Clear Labels**: Keep node labels concise but meaningful. Aim for 2-6 words per node.

5. **Meaningful Edges**: Use edge labels sparingly to clarify relationships when needed (e.g., "leads to", "if yes", "causes").

## Output Format

You MUST return a valid JSON object with a "flowcharts" key containing a LIST of flowchart objects. Structure:
```json
{
    "flowcharts": [
        {
            "title": "Flowchart 1 Title",
            "description": "Description of first flowchart",
            "nodes": [
                {"id": "1", "label": "Start", "type": "start"},
                {"id": "2", "label": "Concept", "type": "concept"}
            ],
            "edges": [
                {"from": "1", "to": "2", "label": ""}
            ]
        },
        {
            "title": "Flowchart 2 Title",
            "description": "Description of second flowchart",
            "nodes": [...],
            "edges": [...]
        }
    ]
}
```

## Important Rules

- Return ONLY the JSON object
- Node IDs must be unique strings WITHIN each flowchart
- Every node except 'start' should have at least one incoming edge
- Every node except 'end' should have at least one outgoing edge
- The type field must be exactly one of: start, end, concept, action, decision
- Keep each flowchart connected - no orphan nodes"""

    async def generate(
        self, 
        context: str, 
        detail_level: str = 'medium',
        **kwargs
    ) -> Dict[str, Any]:
        """
        Generate flowcharts from the provided context based on detail level.
        
        Args:
            context: The document content to generate from
            detail_level: 'simple', 'medium', or 'detailed'
            
        Returns:
            Dictionary with 'flowcharts' list, 'success', and 'error'
        """
        # Validate input
        detail_config = {
            'simple': {
                'count': 1,
                'nodes': '5-10',
                'desc': 'Create 1 simple flowchart covering the most fundamental concept.'
            },
            'medium': {
                'count': '1-2',
                'nodes': '10-15',
                'desc': 'Create 1-2 flowcharts. One high-level overview and optionally one specific process or sub-concept.'
            },
            'detailed': {
                'count': '2-3',
                'nodes': '15-20',
                'desc': 'Create 2-3 flowcharts. Cover the main architecture/process and detailed sub-processes or distinct sections.'
            }
        }
        
        config = detail_config.get(detail_level, detail_config['medium'])
        
        # Build the prompt
        instruction = f"""Analyze the content below and create {config['count']} flowchart(s) based on '{detail_level}' detail level.

Guidelines:
- {config['desc']}
- Each flowchart should have approximately {config['nodes']} nodes.
- Ensure each flowchart focuses on a distinct coherent topic or process.
- Use appropriate node types (start, end, concept, action, decision).

Return a JSON object with a 'flowcharts' list containing the data."""

        prompt = self._create_prompt(context, instruction)
        
        try:
            # Generate the flowchart
            response_text = await self._generate_content(prompt)
            
            # Parse JSON from response
            response_data = self._parse_flowchart_response(response_text)
            
            if not response_data:
                return {
                    "flowcharts": [],
                    "success": False,
                    "error": "Failed to parse flowchart response",
                }
            
            # Normalize structure
            if 'flowcharts' not in response_data:
                # Handle case where AI might return single flowchart structure
                if 'nodes' in response_data:
                    response_data = {'flowcharts': [response_data]}
                else:
                    return {
                        "flowcharts": [],
                        "success": False,
                        "error": "Invalid response structure",
                    }
            
            # Validate and clean each flowchart
            valid_flowcharts = []
            for fc in response_data['flowcharts']:
                validated = self._validate_flowchart(fc)
                if validated['nodes']:
                    valid_flowcharts.append(validated)
            
            if not valid_flowcharts:
                return {
                    "flowcharts": [],
                    "success": False,
                    "error": "No valid flowcharts generated",
                }
            
            return {
                "flowcharts": valid_flowcharts,
                "count": len(valid_flowcharts),
                "success": True,
                "error": None,
            }
            
        except Exception as e:
            return {
                "flowcharts": [],
                "success": False,
                "error": str(e),
            }
    
    def _parse_flowchart_response(self, response_text: str) -> Optional[Dict]:
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
            r'\{[\s\S]*"flowcharts"[\s\S]*\}',    # JSON object with flowcharts key
            r'\{[\s\S]*"nodes"[\s\S]*\}',    # Fallback to single flowchart
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
    
    def _validate_flowchart(self, data: Dict) -> Dict:
        """Validate and clean flowchart data."""
        valid_types = {'start', 'end', 'concept', 'action', 'decision'}
        
        validated_nodes = []
        node_ids = set()
        
        # Validate nodes
        for node in data.get('nodes', []):
            try:
                node_id = str(node.get('id', ''))
                node_type = str(node.get('type', 'concept')).lower()
                label = str(node.get('label', '')).strip()
                
                if not node_id or not label:
                    continue
                
                if node_type not in valid_types:
                    node_type = 'concept'
                
                validated_nodes.append({
                    'id': node_id,
                    'label': label,
                    'type': node_type,
                })
                node_ids.add(node_id)
                
            except (KeyError, TypeError):
                continue
        
        # Validate edges (only include edges where both nodes exist)
        validated_edges = []
        for edge in data.get('edges', []):
            try:
                from_id = str(edge.get('from', ''))
                to_id = str(edge.get('to', ''))
                label = str(edge.get('label', '')).strip()
                
                if from_id in node_ids and to_id in node_ids:
                    validated_edges.append({
                        'from': from_id,
                        'to': to_id,
                        'label': label,
                    })
                    
            except (KeyError, TypeError):
                continue
        
        # Add metadata
        return {
            'title': str(data.get('title', 'Concept Flowchart')).strip(),
            'description': str(data.get('description', '')).strip(),
            'nodes': validated_nodes,
            'edges': validated_edges,
            'node_count': len(validated_nodes),
            'edge_count': len(validated_edges)
        }
