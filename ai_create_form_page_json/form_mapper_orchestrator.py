"""
Form Mapper Orchestrator
Manages the iterative process of AI-assisted form mapping with Selenium
"""

import json
import time
from typing import Dict, List, Optional, Tuple, Any
from dataclasses import dataclass, asdict, field
from enum import Enum
import sys
import os

# Add current directory to path for imports
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from exploration_planner import ExplorationPlanner, ExplorationPath
from dom_change_detector import DOMChangeDetector, DOMChange


class FieldType(Enum):
    """Types of form fields"""
    TEXT_INPUT = "enter_text"
    DROPDOWN = "select_dropdown"
    CHECKBOX = "click_checkbox"
    RADIO = "click_radio"
    BUTTON = "click_button"
    TAB = "click_tab"
    DATE_PICKER = "select_date"
    FILE_UPLOAD = "upload_file"
    TEXTAREA = "enter_textarea"
    SLEEP = "sleep"


@dataclass
class InteractionRequest:
    """Request from AI to interact with an element to reveal more fields"""
    locator: str
    locator_type: str  # css, xpath, id
    action_type: str  # click, select, etc.
    action_value: Optional[str] = None  # For dropdowns, what to select
    description: str = ""
    selenium_actions: List[Dict] = None
    
    def to_dict(self):
        return asdict(self)


@dataclass
class MappingState:
    """Tracks the current state of form mapping"""
    current_json: Dict
    interaction_history: List[Dict]
    clicked_xpaths: List[str]
    iteration_count: int
    is_complete: bool
    pending_interaction: Optional[InteractionRequest]
    previous_dom: Optional[str] = None
    iframe_contents: Dict[str, str] = field(default_factory=dict)
    base_url: Optional[str] = None
    
    # NEW: Systematic exploration
    exploration_planner: Optional[ExplorationPlanner] = None
    change_detector: Optional[DOMChangeDetector] = None
    last_change: Optional[DOMChange] = None
    
    # NEW: Visibility tracking for condition building
    visibility_map: List[Dict] = field(default_factory=list)
    last_accessible_fields: List[str] = field(default_factory=list)  # From AI's analysis
    last_executed_path: Optional[Any] = None  # Last exploration path that was executed
    
    # Deprecated (kept for compatibility)
    current_exploration_depth: int = 0
    max_exploration_depth: int = 5
    explored_states: set = field(default_factory=set)
    
    def to_dict(self):
        result = {
            'current_json': self.current_json,
            'interaction_history': self.interaction_history,
            'clicked_xpaths': self.clicked_xpaths,
            'iteration_count': self.iteration_count,
            'is_complete': self.is_complete,
            'pending_interaction': self.pending_interaction.to_dict() if self.pending_interaction else None,
            'iframe_contents': self.iframe_contents,
            'base_url': self.base_url
        }
        
        # Add exploration status if planner exists
        if self.exploration_planner:
            result['exploration_status'] = self.exploration_planner.get_status()
        
        return result


class FormMapperOrchestrator:
    """
    Orchestrates the AI-Selenium collaboration for form mapping
    """
    
    def __init__(self, selenium_driver, ai_client, form_name: str, max_exploration_depth: int = 5):
        """
        Args:
            selenium_driver: Selenium WebDriver instance
            ai_client: AI client (e.g., Anthropic Claude API client)
            form_name: Name of the form being mapped
            max_exploration_depth: Maximum depth for recursive exploration (default: 5)
        """
        self.driver = selenium_driver
        self.ai = ai_client
        self.form_name = form_name
        self.max_exploration_depth = max_exploration_depth
        self.state = self._initialize_state()
        
    def _initialize_state(self) -> MappingState:
        """Initialize empty mapping state"""
        initial_json = {
            "gui_fields": []
        }
        return MappingState(
            current_json=initial_json,
            interaction_history=[],
            clicked_xpaths=[],
            iteration_count=0,
            is_complete=False,
            pending_interaction=None,
            iframe_contents={},
            base_url=None,
            exploration_planner=ExplorationPlanner(max_depth=self.max_exploration_depth),
            change_detector=DOMChangeDetector(),
            last_change=None,
            current_exploration_depth=0,
            max_exploration_depth=self.max_exploration_depth,
            explored_states=set()
        )
    
    def start_mapping(self, max_iterations: int = 50) -> Dict:
        """
        Start the iterative form mapping process
        
        Args:
            max_iterations: Maximum number of AI-Selenium iterations
            
        Returns:
            Complete form JSON mapping
        """
        print(f"Starting form mapping for: {self.form_name}")
        
        # Store base URL on first iteration
        if not self.state.base_url:
            self.state.base_url = self.driver.current_url
            print(f"📍 Base URL: {self.state.base_url}")
        
        while not self.state.is_complete and self.state.iteration_count < max_iterations:
            self.state.iteration_count += 1
            print(f"\n{'='*60}")
            print(f"Iteration {self.state.iteration_count}/{max_iterations}")
            print(f"{'='*60}")
            print(f"  🐛 DEBUG: Loop starting - is_complete = {self.state.is_complete}")
            print(f"  🐛 DEBUG: Queue has {len(self.state.exploration_planner.exploration_queue)} paths")
            
            # PHASE 1: Get current DOM and detect changes
            current_dom = self._extract_dom()
            
            if self.state.previous_dom:
                # Detect what changed
                self.state.last_change = self.state.change_detector.detect_changes(
                    self.state.previous_dom,
                    current_dom
                )
                print(self.state.change_detector.format_change_summary(self.state.last_change))
            
            # PHASE 2: Discover interactive elements (initial + recursive)
            if self.state.iteration_count == 1:
                # First iteration: discover all base-level interactive elements
                print("🔍 Discovering interactive elements...")
                elements = self.state.change_detector.extract_interactive_elements_from_dom(
                    current_dom, 
                    depth=0,
                    parent_path=[]
                )
                new_paths = self.state.exploration_planner.discover_interactive_elements(elements)
                print(f"  ✓ Found {len(elements)} interactive elements")
                print(f"  ✓ Generated {new_paths} exploration paths")
                print(f"  📊 {self.state.exploration_planner.get_status()}")
            
            elif self.state.last_change and self.state.last_change.appeared_fields:
                # Subsequent iterations: check if new interactive elements appeared (RECURSIVE)
                print("🔍 Checking for NEW interactive elements (recursive discovery)...")
                
                # Get current exploration context
                current_path = self.state.exploration_planner.current_path
                current_depth = current_path.depth if current_path else 0
                parent_path = current_path.steps if current_path else []
                
                # Check depth limit
                if current_depth < self.state.exploration_planner.max_depth:
                    # Discover new elements at next depth level
                    new_elements = self.state.change_detector.extract_interactive_elements_from_dom(
                        current_dom,
                        depth=current_depth + 1,
                        parent_path=parent_path
                    )
                    
                    if new_elements:
                        # Add newly discovered elements to planner
                        new_paths = self.state.exploration_planner.discover_interactive_elements(new_elements)
                        
                        if new_paths > 0:
                            print(f"  ✨ Discovered {len(new_elements)} NEW interactive elements (nested!)")
                            print(f"  ✨ Generated {new_paths} additional exploration paths")
                            print(f"  📊 {self.state.exploration_planner.get_status()}")
                        else:
                            print(f"  ℹ️  Found {len(new_elements)} elements but already explored")
                    else:
                        print(f"  ✓ No new interactive elements at depth {current_depth + 1}")
                else:
                    print(f"  ⚠ Max depth ({self.state.exploration_planner.max_depth}) reached, skipping deeper discovery")
            
            # PHASE 3: Prepare context for AI (with exploration metadata)
            ai_context = self._prepare_ai_context(current_dom)
            
            # DEBUG: Determine current state description
            if self.state.iteration_count == 1:
                current_state_desc = "BASE STATE (initial page load, no selections)"
            else:
                # Get the last action from visibility_map if available
                if self.state.visibility_map:
                    last_action = self.state.visibility_map[-1]['action']
                    current_state_desc = f"AFTER ACTION: {last_action['element']} = {last_action['value']}"
                else:
                    current_state_desc = "UNKNOWN STATE"
            
            print(f"\n  {'='*70}")
            print(f"  🎯 CURRENT STATE: {current_state_desc}")
            print(f"  {'='*70}")
            
            # DEBUG: Save DOM to file so we can inspect what AI sees
            debug_dom_file = f"/tmp/dom_iteration_{self.state.iteration_count}.html"
            try:
                with open(debug_dom_file, 'w', encoding='utf-8') as f:
                    f.write(current_dom)
                print(f"  📄 DEBUG - DOM saved to: {debug_dom_file}")
            except Exception as e:
                print(f"  ⚠️ Could not save DOM: {e}")
            
            # DEBUG: Check what WE find as visible using Selenium
            our_visible_fields = self._extract_visible_fields()
            print(f"  🔍 DEBUG - WE found {len(our_visible_fields)} visible fields (Selenium .is_displayed()):")
            print(f"      {sorted(our_visible_fields)[:15]}{'...' if len(our_visible_fields) > 15 else ''}")
            
            # PHASE 4: Get AI response (AI maps fields based on what it sees)
            ai_response = self._call_ai(ai_context)
            
            # PHASE 5: Process AI response (update JSON mapping)
            self._process_ai_response(ai_response, current_dom)
            
            # PHASE 5.5: Track visibility IMMEDIATELY for CURRENT state
            if self.state.last_accessible_fields:
                # Determine what action/state we're currently in
                if self.state.iteration_count == 1:
                    # Base state
                    action_info = {"element": "base", "value": "initial"}
                else:
                    # Use the last executed path we stored
                    if hasattr(self.state, 'last_executed_path') and self.state.last_executed_path and self.state.last_executed_path.steps:
                        last_step = self.state.last_executed_path.steps[-1]
                        action_info = {
                            "element": last_step.get('element_id', 'unknown'),
                            "value": last_step.get('value', '')
                        }
                    else:
                        # Fallback
                        action_info = {"element": "unknown", "value": "unknown"}
                
                self.state.visibility_map.append({
                    "action": action_info,
                    "visible_fields": self.state.last_accessible_fields
                })
                print(f"  📊 Tracked {len(self.state.last_accessible_fields)} accessible fields for current state: {action_info['element']}={action_info['value']}")
            
            # PHASE 6: Check if mapping is complete
            if ai_response.get('mapping_complete', False):
                # AI thinks it's done, but check if exploration is complete
                print(f"  🐛 DEBUG: AI says mapping_complete=True")
                print(f"  🐛 DEBUG: exploration_planner.is_complete() = {self.state.exploration_planner.is_complete()}")
                print(f"  🐛 DEBUG: Queue length = {len(self.state.exploration_planner.exploration_queue)}")
                print(f"  🐛 DEBUG: Queue contents = {[path.to_signature()[:100] for path in self.state.exploration_planner.exploration_queue][:3]}")
                
                if self.state.exploration_planner.is_complete():
                    self.state.is_complete = True
                    print("✓ AI indicates mapping complete AND all paths explored")
                else:
                    print(f"  ⚠ AI wants to finish but {len(self.state.exploration_planner.exploration_queue)} paths remain")
                    print("  → Continuing exploration...")
            
            # PHASE 7: Execute next exploration from planner (orchestrator decides)
            print(f"  🐛 DEBUG: Before Phase 7 - is_complete = {self.state.is_complete}")
            
            if not self.state.is_complete:
                print(f"  🐛 DEBUG: Attempting to get next exploration path...")
                next_path = self.state.exploration_planner.get_next_exploration()
                print(f"  🐛 DEBUG: next_path = {next_path is not None}")
                
                if next_path:
                    print(f"  🐛 DEBUG: Got path with {len(next_path.steps)} steps")
                    
                    # Show what we're about to click/select
                    if next_path.steps:
                        last_step = next_path.steps[-1]
                        action_desc = f"{last_step.get('action')} on {last_step.get('element_id')} = {last_step.get('value')}"
                        print(f"  🎯 THIS ITERATION WILL: {action_desc}")
                    
                    print(f"  🔍 Orchestrator: Exploring path (depth {next_path.depth})...")
                    success = self._execute_exploration_path(next_path)
                    
                    # Store the executed path for visibility tracking
                    self.state.last_executed_path = next_path
                    
                    if not success:
                        print(f"  ✗ Exploration failed, continuing anyway")
                    
                    # CRITICAL: Extract DOM AFTER exploration for next iteration's comparison
                    self.state.previous_dom = self._extract_dom()
                else:
                    # No more paths to explore
                    print(f"  🐛 DEBUG: No next_path returned!")
                    print(f"  🐛 DEBUG: Queue empty? {len(self.state.exploration_planner.exploration_queue) == 0}")
                    print(f"  🐛 DEBUG: Setting is_complete = True")
                    print("  ✓ All exploration paths completed")
                    self.state.is_complete = True
                    # Store final DOM state
                    self.state.previous_dom = current_dom
            else:
                print(f"  🐛 DEBUG: is_complete=True, skipping exploration")
                # No exploration happened, store current DOM
                self.state.previous_dom = current_dom
            
            print(f"  🐛 DEBUG: End of iteration - is_complete = {self.state.is_complete}")
            
            # Small delay between iterations
            time.sleep(0.5)
        
        if self.state.is_complete:
            print("\n✓ Form mapping completed successfully!")
        else:
            print(f"\n⚠ Reached maximum iterations ({max_iterations})")
            
        return self._finalize_json()
    
    def _extract_dom(self) -> str:
        """
        Extract DOM from Selenium
        
        Returns:
            HTML string of current page state
        """
        from dom_extractor import DOMExtractor
        extractor = DOMExtractor(self.driver)
        return extractor.extract_interactive_elements()
    
    def _extract_visible_fields(self, dom_html: str = None) -> List[str]:
        """
        Extract all ACTUALLY VISIBLE form field IDs from the page
        
        Uses Selenium to check if elements are displayed (not hidden with display:none, visibility:hidden, etc.)
        
        Returns:
            List of field IDs for fields that are actually visible
        """
        from selenium.webdriver.common.by import By
        from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
        
        field_ids = []
        
        # Find all input, select, textarea elements using Selenium
        try:
            # Get all input elements
            inputs = self.driver.find_elements(By.TAG_NAME, 'input')
            for elem in inputs:
                try:
                    # Check if element is displayed (considers CSS display, visibility, opacity, etc.)
                    if elem.is_displayed():
                        field_id = elem.get_attribute('id') or elem.get_attribute('name')
                        if field_id:
                            field_ids.append(field_id)
                except (StaleElementReferenceException, NoSuchElementException):
                    pass
            
            # Get all select elements
            selects = self.driver.find_elements(By.TAG_NAME, 'select')
            for elem in selects:
                try:
                    if elem.is_displayed():
                        field_id = elem.get_attribute('id') or elem.get_attribute('name')
                        if field_id:
                            field_ids.append(field_id)
                except (StaleElementReferenceException, NoSuchElementException):
                    pass
            
            # Get all textarea elements
            textareas = self.driver.find_elements(By.TAG_NAME, 'textarea')
            for elem in textareas:
                try:
                    if elem.is_displayed():
                        field_id = elem.get_attribute('id') or elem.get_attribute('name')
                        if field_id:
                            field_ids.append(field_id)
                except (StaleElementReferenceException, NoSuchElementException):
                    pass
                    
        except Exception as e:
            print(f"  ⚠️ Error extracting visible fields: {e}")
            return []
        
        return list(set(field_ids))  # Remove duplicates
    
    def _prepare_ai_context(self, current_dom: str) -> Dict:
        """
        Prepare context to send to AI
        
        Args:
            current_dom: Current DOM HTML
            
        Returns:
            Context dictionary for AI
        """
        context = {
            'iteration': self.state.iteration_count,
            'form_name': self.form_name,
            'current_dom': current_dom,
            'previous_dom': self.state.previous_dom,
            'current_json': self.state.current_json,
            'clicked_xpaths': self.state.clicked_xpaths,
            'interaction_history': self.state.interaction_history,
            'is_first_iteration': self.state.iteration_count == 1,
            'iframe_contents': self.state.iframe_contents if hasattr(self.state, 'iframe_contents') else {}
        }
        
        # NEW: Add exploration context from planner
        exploration_context = self.state.exploration_planner.get_current_context()
        if exploration_context:
            context['exploration_context'] = exploration_context
            
            # Add all dropdown options so AI knows what values exist
            context['all_element_options'] = self.state.exploration_planner.get_all_element_options()
        
        # NEW: Add change detection info
        if self.state.last_change:
            context['detected_changes'] = {
                'appeared': [
                    {'id': f.get('id'), 'name': f.get('name'), 'type': f.get('type')}
                    for f in self.state.last_change.appeared_fields
                ],
                'disappeared': [
                    {'id': f.get('id'), 'name': f.get('name'), 'type': f.get('type')}
                    for f in self.state.last_change.disappeared_fields
                ],
                'unchanged_count': len(self.state.last_change.unchanged_fields)
            }
        
        # Include last interaction details if exists
        if self.state.interaction_history:
            last_interaction = self.state.interaction_history[-1]
            context['last_interaction'] = {
                'description': last_interaction['interaction']['description'],
                'locator': last_interaction['interaction']['locator'],
                'action_type': last_interaction['interaction']['action_type'],
                'action_value': last_interaction['interaction'].get('action_value')
            }
            
        return context
    
    def _call_ai(self, context: Dict) -> Dict:
        """
        Call AI with context and get response
        
        Args:
            context: Context dictionary
            
        Returns:
            AI response dictionary
        """
        from ai_prompter import AIPrompter
        prompter = AIPrompter()
        
        prompt = prompter.build_prompt(context)
        
        # Call AI with sufficient token budget
        # Small forms: ~2000 tokens, Medium: ~8000, Large: ~16000, Very Large: ~19000
        # Using 19000 to handle large forms without triggering streaming requirement
        response = self.ai.generate(prompt, max_tokens=19000)
        
        # Parse AI response to extract JSON
        parsed_response = prompter.parse_response(response)
        
        return parsed_response
    
    def _process_ai_response(self, ai_response: Dict, current_dom: str):
        """
        Process AI response and update state
        
        Args:
            ai_response: Parsed AI response
            current_dom: Current DOM (stored for reference)
        """
        # DEBUG: Print AI's explanation on iteration 3
        # COMMENTED OUT - Can be re-enabled if needed for debugging
        # if self.state.iteration_count == 3 and 'debug_explanation' in ai_response:
        #     print("\n" + "="*70)
        #     print("🤖 AI'S EXPLANATION ABOUT COMPANYME AND TAXID:")
        #     print("="*70)
        #     print(ai_response['debug_explanation'])
        #     print("="*70 + "\n")
        
        # NEW: Extract accessible_fields from AI (if provided)
        if 'accessible_fields' in ai_response:
            accessible_fields_raw = ai_response['accessible_fields']
            
            # DEBUG: Print the FULL list
            print(f"  🔍 DEBUG - AI's accessible_fields list ({len(accessible_fields_raw)} fields):")
            for i, field in enumerate(accessible_fields_raw, 1):
                print(f"      {i}. {field}")
            
            # Process: expand iframe IDs to include their internal fields
            accessible_fields_expanded = []
            for field_id in accessible_fields_raw:
                # Check if this is an iframe ID
                if field_id in self.state.iframe_contents:
                    # It's an iframe! Add all fields from inside it
                    print(f"  📦 Expanding iframe '{field_id}' into its internal fields")
                    # TODO: Extract field IDs from iframe content
                    # For now, just add the iframe ID itself
                    accessible_fields_expanded.append(field_id)
                else:
                    # Regular field
                    accessible_fields_expanded.append(field_id)
            
            # Store for use in visibility tracking
            self.state.last_accessible_fields = accessible_fields_expanded
            print(f"  ✅ AI identified {len(accessible_fields_expanded)} accessible fields")
        
        # Update JSON with new fields
        if 'gui_fields' in ai_response:
            self.state.current_json['gui_fields'] = ai_response['gui_fields']
            print(f"  📝 AI mapped {len(ai_response['gui_fields'])} fields")
        
        # Handle iframe exploration requests (still AI-driven, this is discovery not exploration)
        if 'iframes_to_explore' in ai_response and ai_response['iframes_to_explore']:
            print(f"  📦 AI found {len(ai_response['iframes_to_explore'])} iframe(s) to explore")
            self._extract_iframe_contents(ai_response['iframes_to_explore'])
        else:
            # Clear iframe contents if no requests
            self.state.iframe_contents = {}
        
        # NOTE: AI no longer requests exploration_step - orchestrator decides exploration
        # Keeping this for backward compatibility if AI still returns it
        if 'exploration_step' in ai_response:
            print("  ⚠ AI sent exploration_step but orchestrator now controls exploration (ignoring)")
        
        # Check if AI marked as complete (but orchestrator has final say)
        if ai_response.get('mapping_complete', False):
            print("  ℹ️  AI indicates fields mapped (orchestrator will verify exploration complete)")
        
        # Check if AI requested interaction
        if 'interaction_request' in ai_response and ai_response['interaction_request']:
            req = ai_response['interaction_request']
            self.state.pending_interaction = InteractionRequest(
                locator=req['locator'],
                locator_type=req.get('locator_type', 'xpath'),
                action_type=req['action_type'],
                action_value=req.get('action_value'),
                description=req.get('description', ''),
                selenium_actions=req.get('selenium_actions', [])
            )
            print(f"→ AI requests interaction: {self.state.pending_interaction.description}")
        
        # Store previous DOM
        self.state.previous_dom = current_dom
    
    def _extract_iframe_contents(self, iframes_to_explore: List[Dict]):
        """
        Extract contents from requested iframes
        
        Args:
            iframes_to_explore: List of iframe dicts with iframe_id and iframe_xpath
        """
        from selenium.webdriver.common.by import By
        from dom_extractor import DOMExtractor
        
        if not hasattr(self.state, 'iframe_contents'):
            self.state.iframe_contents = {}
        
        # Clear previous iframe contents
        self.state.iframe_contents = {}
        
        for iframe_info in iframes_to_explore:
            iframe_id = iframe_info.get('iframe_id')
            iframe_xpath = iframe_info.get('iframe_xpath')
            
            if not iframe_id or not iframe_xpath:
                print(f"  ⚠ Skipping iframe with missing id or xpath: {iframe_info}")
                continue
            
            try:
                print(f"  → Exploring iframe: {iframe_id}")
                
                # Find and switch to iframe
                iframe_element = self.driver.find_element(By.XPATH, iframe_xpath)
                self.driver.switch_to.frame(iframe_element)
                
                # Wait for iframe content to load
                import time
                time.sleep(1)
                
                # Extract iframe DOM
                extractor = DOMExtractor(self.driver)
                iframe_dom = extractor.extract_interactive_elements()
                
                # Store iframe content
                self.state.iframe_contents[iframe_id] = iframe_dom
                
                print(f"    ✓ Extracted {len(iframe_dom)} chars from iframe '{iframe_id}'")
                
                # Switch back to main document
                self.driver.switch_to.default_content()
                
            except Exception as e:
                print(f"  ✗ Failed to extract iframe '{iframe_id}': {str(e)}")
                import traceback
                print(f"  🐛 DEBUG: Iframe exception traceback:")
                traceback.print_exc()
                # Make sure we're back in main document
                try:
                    self.driver.switch_to.default_content()
                except:
                    pass
    
    def _reset_to_base_url(self):
        """Navigate back to base URL and wait for stable"""
        if not self.state.base_url:
            print("  ⚠ No base URL stored, cannot reset")
            return False
        
        print(f"  🔄 Resetting to base URL...")
        try:
            self.driver.get(self.state.base_url)
            import time
            time.sleep(2)  # Wait for page to load
            print("  ✓ Back at base")
            return True
        except Exception as e:
            print(f"  ✗ Failed to reset to base: {str(e)}")
            import traceback
            print(f"  🐛 DEBUG: Reset exception traceback:")
            traceback.print_exc()
            return False

    def _execute_navigation_sequence(self, sequence: List[Dict]) -> bool:
        """
        Execute a sequence of navigation steps from base URL
        
        Args:
            sequence: List of navigation step dictionaries
            
        Returns:
            True if successful, False otherwise
        """
        from selenium_executor import SeleniumExecutor
        import time
        
        # Always start from base
        if not self._reset_to_base_url():
            return False
        
        executor = SeleniumExecutor(self.driver)
        
        # Execute each step in order
        for i, step in enumerate(sequence, 1):
            action = step.get('action')
            print(f"  → Step {i}/{len(sequence)}: {action} ({step.get('element_id')})")
            
            try:
                if action == 'select_dropdown':
                    # Dropdown selection
                    actions = [
                        {
                            'action': 'wait_for_element',
                            'locator': step['locator'],
                            'locator_type': step.get('locator_type', 'xpath'),
                            'timeout': 10
                        },
                        {
                            'action': 'select_dropdown',
                            'locator': step['locator'],
                            'locator_type': step.get('locator_type', 'xpath'),
                            'value': step['value']
                        }
                    ]
                    executor.execute_actions(actions)
                    print(f"    ✓ Selected '{step['value']}'")
                
                elif action == 'click_radio':
                    # Radio button selection
                    radio_xpath = f"{step['locator']}[@value='{step['value']}']"
                    actions = [
                        {
                            'action': 'wait_for_element',
                            'locator': radio_xpath,
                            'locator_type': 'xpath',
                            'timeout': 10
                        },
                        {
                            'action': 'click',
                            'locator': radio_xpath,
                            'locator_type': 'xpath'
                        }
                    ]
                    executor.execute_actions(actions)
                    print(f"    ✓ Selected radio '{step['value']}'")
                
                elif action == 'click_checkbox':
                    # Checkbox - check or uncheck
                    actions = [
                        {
                            'action': 'wait_for_element',
                            'locator': step['locator'],
                            'locator_type': 'xpath',
                            'timeout': 10
                        }
                    ]
                    
                    # Check if we need to check or uncheck
                    if step['value'] == 'checked':
                        actions.append({
                            'action': 'click_checkbox',
                            'locator': step['locator'],
                            'locator_type': 'xpath',
                            'checked': True  # ← FIXED: was 'check'
                        })
                    else:
                        actions.append({
                            'action': 'click_checkbox',
                            'locator': step['locator'],
                            'locator_type': 'xpath',
                            'checked': False  # ← FIXED: was 'check'
                        })
                    
                    executor.execute_actions(actions)
                    print(f"    ✓ Checkbox {step['value']}")
                    
                elif action in ['click_tab', 'click_button', 'click']:
                    # Click actions (tabs, buttons, etc.)
                    actions = [
                        {
                            'action': 'wait_for_element',
                            'locator': step['locator'],
                            'locator_type': step.get('locator_type', 'xpath'),
                            'timeout': 10
                        },
                        {
                            'action': 'click',
                            'locator': step['locator'],
                            'locator_type': step.get('locator_type', 'xpath')
                        }
                    ]
                    executor.execute_actions(actions)
                    print(f"    ✓ Clicked")
                
                # Wait after action if specified
                wait_time = step.get('wait_after', 1)
                time.sleep(wait_time)
                
            except Exception as e:
                print(f"  ✗ Step {i} failed: {str(e)}")
                import traceback
                print(f"  🐛 DEBUG: Exception traceback:")
                traceback.print_exc()
                return False
        
        print(f"  ✓ Navigation sequence complete")
        return True
    
    def _execute_exploration_path(self, path: ExplorationPath) -> bool:
        """
        Execute a complete exploration path from base URL.
        
        Args:
            path: ExplorationPath object with steps to execute
            
        Returns:
            True if successful, False otherwise
        """
        # Use existing navigation sequence executor
        return self._execute_navigation_sequence(path.steps)
    
    def _execute_interaction(self, interaction: InteractionRequest) -> bool:
        """
        Execute Selenium interaction requested by AI
        
        Args:
            interaction: InteractionRequest object
            
        Returns:
            True if successful, False otherwise
        """
        from selenium_executor import SeleniumExecutor
        import time
        
        executor = SeleniumExecutor(self.driver)
        
        try:
            print(f"Executing: {interaction.description}")
            success = executor.execute_actions(interaction.selenium_actions)
            
            if success:
                # Add to clicked xpaths if it was a click action
                if interaction.locator_type == 'xpath' and 'click' in interaction.action_type:
                    self.state.clicked_xpaths.append(interaction.locator)
                
                # CRITICAL: Wait for page to stabilize after interaction
                print("  ⏳ Waiting for content to load after interaction...")
                self._wait_after_interaction(interaction)
                    
            return success
            
        except Exception as e:
            print(f"  ✗ Error executing interaction: {str(e)}")
            import traceback
            print(f"  🐛 DEBUG: Exception traceback:")
            traceback.print_exc()
            return False
    
    def _wait_after_interaction(self, interaction: InteractionRequest):
        """
        Wait appropriate time after interaction based on action type
        
        Args:
            interaction: The interaction that was executed
        """
        import time
        
        action_type = interaction.action_type.lower()
        
        # Determine wait time based on action type
        if 'tab' in action_type:
            wait_time = 2.0  # Tabs often load new content
        elif 'dropdown' in action_type or 'select' in action_type:
            wait_time = 1.5  # Dropdowns might trigger dependent fields
        elif 'next' in action_type or 'submit' in action_type:
            wait_time = 3.0  # Navigation actions
        elif 'frame' in action_type or 'iframe' in action_type:
            wait_time = 1.0  # Frame switching
        else:
            wait_time = 1.0  # Default
        
        time.sleep(wait_time)
        print(f"  ✓ Waited {wait_time}s for stability")
    
    def _finalize_json(self) -> Dict:
        """
        Add metadata and finalize the JSON structure
        
        Returns:
            Complete JSON with all sections
        """
        # NEW: Build conditions from visibility_map before finalizing
        print("\n🔧 Building non_editable_condition from visibility data...")
        self._build_conditions_from_visibility_map()
        
        final_json = {
            "gui_pre_create_actions": [],
            "css_values": self._generate_css_values(),
            "gui_post_update_actions": [],
            "gui_post_create_actions": [],
            "gui_pre_update_actions": [],
            "gui_pre_verification_actions": [],
            "system_values": self._generate_system_values(),
            "gui_fields": self.state.current_json.get('gui_fields', [])
        }
        
        # Save to file
        output_file = f"{self.form_name}_main_setup.json"
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(final_json, f, indent=4, ensure_ascii=False)
        
        print(f"\n✓ Saved complete mapping to: {output_file}")
        
        return final_json
    
    def _build_conditions_from_visibility_map(self):
        """
        Build non_editable_condition for each field based on visibility_map
        
        This processes the collected visibility data to determine which
        field is hidden under which conditions.
        """
        if not self.state.visibility_map:
            print("  ⚠ No visibility data collected")
            return
        
        # DEBUG: Print the complete visibility_map table
        print("\n  📊 VISIBILITY MAP TABLE:")
        print("  " + "="*80)
        for i, row in enumerate(self.state.visibility_map):
            action = row['action']
            field_count = len(row['visible_fields'])
            fields_list = sorted(row['visible_fields'])
            print(f"  State {i}: {action['element']}={action['value']} → {field_count} visible fields")
            print(f"    Fields: {fields_list}")
        print("  " + "="*80 + "\n")
        
        # Get all unique fields across all states
        all_fields = set()
        for row in self.state.visibility_map:
            all_fields.update(row["visible_fields"])
        
        print(f"  📊 Processing {len(all_fields)} unique fields across {len(self.state.visibility_map)} states")
        print(f"  🔍 DEBUG: All tracked fields: {sorted(list(all_fields))[:10]}")  # Show first 10
        
        # Get gui_fields from current JSON
        gui_fields = self.state.current_json.get('gui_fields', [])
        
        # Build map of field name to gui_field object
        field_map = {}
        for field in gui_fields:
            field_name = field.get('name')
            if field_name:
                # Try to match by name (convert to field ID format)
                field_id = field_name.replace('_', '').lower()
                field_map[field_id] = field
                # Also map original name
                field_map[field_name] = field
        
        conditions_set = 0
        
        # For each field, determine where it's hidden
        for field_id in all_fields:
            hidden_actions = []
            visible_states = []
            hidden_states = []
            
            # Check each state - if field is NOT visible, it's hidden
            for row in self.state.visibility_map:
                is_visible = field_id in row["visible_fields"]
                action_str = f"{row['action']['element']}={row['action']['value']}"
                
                if is_visible:
                    visible_states.append(action_str)
                else:
                    hidden_states.append(action_str)
                    hidden_actions.append(row["action"])
            
            # If field is sometimes hidden, build condition
            if hidden_actions:
                # Group by element
                by_element = {}
                for action in hidden_actions:
                    element = action["element"]
                    value = action["value"]
                    
                    # Skip base state
                    if element == "base":
                        continue
                    
                    if element not in by_element:
                        by_element[element] = []
                    by_element[element].append(value)
                
                # Find matching gui_field and set condition
                field_obj = None
                
                # Try various name formats to find the field
                possible_names = [
                    field_id,                          # original: companyName
                    field_id.lower(),                  # lowercase: companyname
                    field_id.replace('-', '_'),        # dashes to underscores
                    field_id.replace('_', ''),         # remove underscores: companyname
                    field_id.replace('_', '').lower(), # remove underscores + lowercase
                    # Convert camelCase to snake_case
                    ''.join(['_'+c.lower() if c.isupper() else c for c in field_id]).lstrip('_'),
                ]
                
                # Debug: print what we're trying to match
                print(f"  🔍 Trying to match field_id='{field_id}' with variations: {possible_names[:3]}")
                
                for name in possible_names:
                    if name in field_map:
                        field_obj = field_map[name]
                        print(f"    ✓ Matched with '{name}'")
                        break
                
                if field_obj and by_element:
                    # Build condition
                    if len(by_element) == 1:
                        # Single element controls visibility
                        element, values = list(by_element.items())[0]
                        condition = {
                            "operator": "or",
                            element: values
                        }
                    else:
                        # Multiple elements - use complex condition (for now, just use first)
                        element, values = list(by_element.items())[0]
                        condition = {
                            "operator": "or",
                            element: values
                        }
                    
                    # Set condition in create_action and update_action
                    if 'create_action' in field_obj:
                        field_obj['create_action']['non_editable_condition'] = condition
                    if 'update_action' in field_obj:
                        field_obj['update_action']['non_editable_condition'] = condition
                    
                    conditions_set += 1
                    
                    # DEBUG: Show visibility analysis for this field
                    print(f"  ✅ {field_obj['name']}: {condition}")
                    print(f"      📊 Visible in: {visible_states}")
                    print(f"      📊 Hidden in: {hidden_states}")
        
        print(f"  📊 Set conditions for {conditions_set} fields")
    
    def _generate_css_values(self) -> List[Dict]:
        """Generate standard CSS values structure"""
        return [
            {"name": "save_button_css", "value": ""},
            {"name": "edit_button_css", "value": ""},
            {"name": "x_cancel_button_css", "value": ""},
            {"name": "approve_cancel_button_css", "value": ""},
            {"name": "save_message_css", "value": ""},
            {"name": "tab_css", "value": ""}
        ]
    
    def _generate_system_values(self) -> List[Dict]:
        """Generate standard system values structure"""
        return [
            {
                "_comment": "the main tab(form page) of the entity where the main info is filled in is called 'main'",
                "name": "main_component_tab",
                "value": "main"
            },
            {
                "_comment": "the folder name under which screenshot bugs for this entity are placed",
                "name": "folder_name_for_bugs_screenshots",
                "value": self.form_name
            },
            {
                "name": "is_sub_project",
                "value": False
            },
            {
                "name": "tab_name",
                "value": "main"
            }
        ]
    
    def save_state(self, filename: str = None):
        """Save current state to file for resuming"""
        if filename is None:
            filename = f"{self.form_name}_mapping_state.json"
        
        with open(filename, 'w', encoding='utf-8') as f:
            json.dump(self.state.to_dict(), f, indent=4, ensure_ascii=False)
        
        print(f"State saved to: {filename}")
    
    def load_state(self, filename: str):
        """Load state from file to resume mapping"""
        with open(filename, 'r', encoding='utf-8') as f:
            state_dict = json.load(f)
        
        # Reconstruct state
        self.state = MappingState(
            current_json=state_dict['current_json'],
            interaction_history=state_dict['interaction_history'],
            clicked_xpaths=state_dict['clicked_xpaths'],
            iteration_count=state_dict['iteration_count'],
            is_complete=state_dict['is_complete'],
            pending_interaction=InteractionRequest(**state_dict['pending_interaction']) 
                if state_dict['pending_interaction'] else None
        )
        
        print(f"State loaded from: {filename}")


# Example usage function
def example_usage():
    """
    Example of how to use the FormMapperOrchestrator
    """
    from selenium import webdriver
    from ai_client_wrapper import AIClientWrapper
    
    # Initialize Selenium
    driver = webdriver.Chrome()
    driver.get("https://your-app.com/form-page")
    
    # Initialize AI client (you'll need to implement this wrapper)
    ai_client = AIClientWrapper(api_key="your-api-key")
    
    # Create orchestrator
    orchestrator = FormMapperOrchestrator(
        selenium_driver=driver,
        ai_client=ai_client,
        form_name="engagement"
    )
    
    try:
        # Start mapping process
        result_json = orchestrator.start_mapping(max_iterations=30)
        
        print("\n" + "="*60)
        print("Mapping completed!")
        print(f"Total fields mapped: {len(result_json['gui_fields'])}")
        print(f"Total iterations: {orchestrator.state.iteration_count}")
        
    finally:
        driver.quit()


if __name__ == "__main__":
    example_usage()
