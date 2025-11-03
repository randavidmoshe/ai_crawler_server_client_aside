"""
Exploration Planner - Systematic exploration of interactive form elements
"""

from typing import Dict, List, Set, Optional, Tuple
from dataclasses import dataclass, field
from collections import deque
import json


@dataclass
class InteractiveElement:
    """Represents a discoverable interactive element"""
    element_id: str
    element_type: str  # dropdown, tab, button, checkbox
    locator: str  # xpath
    options: List[str]  # For dropdowns: option values, for tabs: tab names
    parent_path: List[Dict] = field(default_factory=list)  # Path to reach this element
    depth: int = 0


@dataclass
class ExplorationPath:
    """A complete path to explore (potentially nested)"""
    steps: List[Dict]  # [{'action': 'select_dropdown', 'locator': '...', 'value': '...'}]
    depth: int
    element_chain: List[str]  # Track which elements are in this path
    
    def to_signature(self) -> str:
        """Create unique signature for this path"""
        return json.dumps(self.steps, sort_keys=True)


class ExplorationPlanner:
    """
    Manages systematic exploration of form interactive elements.
    Discovers dropdowns, tabs, buttons and generates exploration queue.
    """
    
    def __init__(self, max_depth: int = 5):
        """
        Args:
            max_depth: Maximum nesting depth to explore
        """
        self.max_depth = max_depth
        
        # Discovered interactive elements
        self.interactive_elements: Dict[str, InteractiveElement] = {}
        
        # Exploration queue (BFS)
        self.exploration_queue: deque[ExplorationPath] = deque()
        
        # Completed explorations
        self.explored_paths: Set[str] = set()
        
        # Current exploration context
        self.current_path: Optional[ExplorationPath] = None
        self.previous_path: Optional[ExplorationPath] = None
        
        # Tracking
        self.total_paths_generated = 0
        self.total_paths_explored = 0
    
    def discover_interactive_elements(self, elements: List[Dict]) -> int:
        """
        Register newly discovered interactive elements.
        
        Args:
            elements: List of dicts with {id, type, locator, options, depth}
        
        Returns:
            Number of NEW paths added to queue
        """
        new_paths = 0
        
        for elem_dict in elements:
            element_id = elem_dict['id']
            
            # Skip if already discovered
            if element_id in self.interactive_elements:
                continue
            
            # Create element
            element = InteractiveElement(
                element_id=element_id,
                element_type=elem_dict['type'],
                locator=elem_dict['locator'],
                options=elem_dict['options'],
                parent_path=elem_dict.get('parent_path', []),
                depth=elem_dict.get('depth', 0)
            )
            
            # Check depth limit
            if element.depth >= self.max_depth:
                print(f"  ⚠ Skipping {element_id} - max depth reached")
                continue
            
            # Register element
            self.interactive_elements[element_id] = element
            
            # Generate exploration paths for this element
            paths_added = self._generate_paths_for_element(element)
            new_paths += paths_added
        
        return new_paths
    
    def _generate_paths_for_element(self, element: InteractiveElement) -> int:
        """
        Generate all exploration paths for an element's options.
        
        Args:
            element: Interactive element to explore
            
        Returns:
            Number of paths added
        """
        paths_added = 0
        
        for option in element.options:
            # Skip empty/placeholder options
            if not option or option.lower() in ['select', 'choose', 'select one', '']:
                continue
            
            # Build step for this option
            step = self._create_step(element, option)
            
            # Combine with parent path
            full_steps = element.parent_path + [step]
            
            # Create exploration path
            path = ExplorationPath(
                steps=full_steps,
                depth=element.depth,
                element_chain=[element.element_id]
            )
            
            # Check if already explored
            if path.to_signature() in self.explored_paths:
                continue
            
            # Add to queue
            self.exploration_queue.append(path)
            paths_added += 1
            self.total_paths_generated += 1
        
        return paths_added
    
    def _create_step(self, element: InteractiveElement, option: str) -> Dict:
        """Create a navigation step for an element option"""
        base_step = {
            'locator': element.locator,
            'locator_type': 'xpath',
            'element_id': element.element_id
        }
        
        if element.element_type == 'dropdown':
            return {
                **base_step,
                'action': 'select_dropdown',
                'value': option,
                'wait_after': 2
            }
        
        elif element.element_type == 'tab':
            return {
                **base_step,
                'action': 'click_tab',
                'tab_name': option,
                'wait_after': 1
            }
        
        elif element.element_type == 'radio':
            return {
                **base_step,
                'action': 'click_radio',
                'value': option,
                'radio_name': element.element_id,
                'wait_after': 1
            }
        
        elif element.element_type == 'checkbox_toggle':
            # Single checkbox toggle (on/off)
            return {
                **base_step,
                'action': 'click_checkbox',
                'value': option,  # 'checked' or 'unchecked'
                'wait_after': 1
            }
        
        elif element.element_type == 'checkbox_group':
            # Checkbox group - click specific checkbox in group
            return {
                **base_step,
                'action': 'click_checkbox',
                'value': option,  # Specific checkbox id
                'wait_after': 1
            }
        
        else:
            # Generic click
            return {
                **base_step,
                'action': 'click',
                'wait_after': 1
            }
    
    def get_next_exploration(self) -> Optional[ExplorationPath]:
        """
        Get next path to explore from queue.
        
        Returns:
            ExplorationPath or None if queue empty
        """
        if not self.exploration_queue:
            return None
        
        # Pop from front (BFS)
        path = self.exploration_queue.popleft()
        
        # Update tracking
        self.previous_path = self.current_path
        self.current_path = path
        
        # Mark as exploring
        self.explored_paths.add(path.to_signature())
        self.total_paths_explored += 1
        
        return path
    
    def mark_path_complete(self, path: ExplorationPath):
        """Mark a path as fully explored"""
        self.explored_paths.add(path.to_signature())
    
    def is_complete(self) -> bool:
        """Check if all paths have been explored"""
        return len(self.exploration_queue) == 0
    
    def get_current_context(self) -> Dict:
        """
        Get exploration context for AI.
        
        Returns:
            Dict with current exploration metadata
        """
        if not self.current_path:
            return {}
        
        context = {
            'exploration_active': True,
            'current_depth': self.current_path.depth,
            'max_depth': self.max_depth,
            'paths_explored': self.total_paths_explored,
            'paths_remaining': len(self.exploration_queue),
            'current_path_steps': self.current_path.steps
        }
        
        # Extract last action details
        if self.current_path.steps:
            last_step = self.current_path.steps[-1]
            context['last_action'] = {
                'element_id': last_step.get('element_id'),
                'action': last_step.get('action'),
                'value': last_step.get('value') or last_step.get('tab_name')
            }
        
        # Previous action details
        if self.previous_path and self.previous_path.steps:
            prev_step = self.previous_path.steps[-1]
            context['previous_action'] = {
                'element_id': prev_step.get('element_id'),
                'action': prev_step.get('action'),
                'value': prev_step.get('value') or prev_step.get('tab_name')
            }
        
        return context
    
    def get_element_options(self, element_id: str) -> List[str]:
        """Get all options for an element"""
        if element_id in self.interactive_elements:
            return self.interactive_elements[element_id].options
        return []
    
    def get_all_element_options(self) -> Dict[str, List[str]]:
        """Get all options for all discovered elements"""
        return {
            elem_id: elem.options
            for elem_id, elem in self.interactive_elements.items()
        }
    
    def get_status(self) -> str:
        """Get human-readable status"""
        return (
            f"Elements: {len(self.interactive_elements)} | "
            f"Explored: {self.total_paths_explored} | "
            f"Remaining: {len(self.exploration_queue)}"
        )
    
    def reset(self):
        """Reset planner state"""
        self.interactive_elements.clear()
        self.exploration_queue.clear()
        self.explored_paths.clear()
        self.current_path = None
        self.previous_path = None
        self.total_paths_generated = 0
        self.total_paths_explored = 0
