# orchestrator.py
# The brain of form discovery - manages exploration algorithm

import time
import json
import hashlib
from typing import Dict, List, Optional, Set
from collections import deque


class FormDiscoveryOrchestrator:
    """
    Orchestrates the form discovery process
    - Maintains exploration queue
    - Tracks visited states
    - Decides what to explore next
    - Registers discovered forms with their paths
    """
    
    def __init__(
        self,
        agent,
        ai_prompter,
        start_url: str,
        project_name: str,
        max_depth: int = 10,
        max_states: int = 100
    ):
        self.agent = agent
        self.ai_prompter = ai_prompter
        self.start_url = start_url
        self.project_name = project_name
        self.max_depth = max_depth
        self.max_states = max_states
        
        # Setup output directory
        import os
        username = os.getenv('USER') or os.getenv('USERNAME') or 'user'
        self.output_dir = f"/home/{username}/automation_product_config/ai_projects/{project_name}"
        os.makedirs(self.output_dir, exist_ok=True)
        self.output_file = os.path.join(self.output_dir, "discovered_forms.json")
        
        # Exploration tracking
        self.exploration_queue = deque()  # States to explore
        self.visited_states = set()  # State hashes we've seen
        self.queued_state_hashes = set()  # NEW: Track queued paths to prevent duplicates
        self.discovered_forms = []  # Forms found with their paths
        self._list_of_visited_paths = []
        
        # Statistics
        self.states_explored = 0
        self.forms_found = 0
        
    def discover_forms(self) -> List[Dict]:
        """
        Main discovery loop
        Returns list of discovered forms with their navigation paths
        """
        print(f"\n{'='*70}")
        print(f"🔍 STARTING FORM DISCOVERY")
        print(f"{'='*70}")
        print(f"Start URL: {self.start_url}")
        print(f"Max Depth: {self.max_depth}")
        print(f"Max States: {self.max_states}")
        print(f"{'='*70}\n")
        
        # Initialize: Add starting state to queue
        initial_state = {
            'url': self.start_url,
            'interaction_path': [],
            'depth': 0
        }
        self.exploration_queue.append(initial_state)

        self._list_of_visited_paths = []
        self._list_of_visited_paths.append(initial_state)
        # Main exploration loop
        while self.exploration_queue and not self._should_stop():
            state = self.exploration_queue.popleft()


            
            # Remove from queued tracking (we're exploring it now)
            path_tuple = tuple(step['description'] for step in state['interaction_path'])
            self.queued_state_hashes.discard(path_tuple)
            print("-------------------------------------------------------------")
            print(f"\n[Orchestrator] Exploring state (depth={state['depth']}, queue={len(self.exploration_queue)})")
            print(f"[Orchestrator] Path: {self._format_path(state['interaction_path'])}")
            
            # Navigate to this state
            if not self._navigate_to_state(state):
                print(f"[Orchestrator] ❌ Failed to navigate to state, skipping")
                continue


            # Check if last step was a dropdown
            is_dropdown_state = False
            if state['interaction_path']:
                last_step = state['interaction_path'][-1]
                is_dropdown_state = self._is_dropdown_click(last_step)
            
            # Get DOM (quickly for dropdowns, stable for others)
            if is_dropdown_state:
                # For dropdowns, get DOM immediately before menu closes
                #dom_result = self.agent.get_current_dom() # <- there was no get current dom
                dom_result = self.agent.get_stable_dom()
                print(f"[Orchestrator] DOM captured (dropdown mode)")
            else:
                # For normal pages, wait for stability
                dom_result = self.agent.get_stable_dom()
                wait_time = dom_result.get('wait_time', 0)
                stable = dom_result.get('stable', False)
                print(f"[Orchestrator] DOM ready (wait: {wait_time}s, stable: {stable})")
            
            if not dom_result.get('success'):
                print(f"[Orchestrator] ❌ Failed to get DOM: {dom_result.get('error')}")
                continue
            
            dom = dom_result.get('html', '')
            
            # Check if we've seen this state before
            #state_hash = self._hash_state(dom, state['url'])
            #if state_hash in self.visited_states:
            #    print(f"[Orchestrator] ⚠️ Already visited this state, skipping")
            #    continue
            
            #self.visited_states.add(state_hash)
            self.states_explored += 1
            
            # Get current URL (might have changed)
            current_url_result = self.agent.get_current_url()
            current_url = current_url_result.get('url', state['url'])
            
            # AI analyzes the page
            print(f"[Orchestrator] 🤖 Analyzing page with AI...")
            analysis = self.ai_prompter.analyze_page(dom, current_url, state['interaction_path'], self._list_of_visited_paths)
            
            # Check if this is a form page
            if analysis['is_form_page']:
                self._register_form(state, analysis, current_url)
            else:
                print(f"[Orchestrator] ℹ️ Not a form page")
            
            # Find exploration opportunities
            opportunities = self._extract_opportunities(analysis)
            
            # DEBUG: Log what AI found
            nav_items = analysis.get('navigation_items', [])
            if nav_items:
                print(f"[Orchestrator] 🔍 AI found {len(nav_items)} navigation items:")
                for item in nav_items[:5]:  # Show first 5
                    print(f"   - {item.get('text', 'N/A')} (type: {item.get('type', 'N/A')})")
                if len(nav_items) > 5:
                    print(f"   ... and {len(nav_items) - 5} more")
            
            # Queue new states
            self._queue_opportunities(state, opportunities)
            
            # Brief pause between explorations
            time.sleep(0.5)
        
        # Discovery complete
        print(f"\n{'='*70}")
        print(f"✅ DISCOVERY COMPLETE")
        print(f"{'='*70}")
        print(f"States explored: {self.states_explored}")
        print(f"Forms found: {self.forms_found}")
        print(f"{'='*70}\n")
        
        return self.discovered_forms
    
    def _navigate_to_state(self, state: Dict) -> bool:
        """
        Navigate to a specific state by replaying interaction path
        """
        # Start at base URL
        nav_result = self.agent.navigate_to_url(state['url'])
        if not nav_result.get('success'):
            return False
        
        self.agent.wait_dom_ready()
        time.sleep(1)
        
        # Replay each interaction in the path
        for i, step in enumerate(state['interaction_path']):
            print(f"[Orchestrator]   → {step['description']}")
            
            result = self.agent.execute_step(step)
            
            if not result.get('success'):
                print(f"[Orchestrator]   ❌ Step failed: {result.get('error')}")
                return False
            
            # Check if this is the last step and if it's a dropdown
            is_last_step = (i == len(state['interaction_path']) - 1)
            is_dropdown = self._is_dropdown_click(step)
            
            if is_last_step and is_dropdown:
                # For dropdowns, wait briefly but don't wait for stability
                # (dropdown menu might close if we wait too long)
                print(f"[Orchestrator]   ℹ️ Dropdown detected, capturing DOM quickly")
                time.sleep(0.3)  # Just enough for animation
            else:
                # Normal wait for non-dropdown steps
                time.sleep(0.5)
                self.agent.wait_dom_ready()
        
        return True
    
    def _extract_opportunities(self, analysis: Dict) -> List[Dict]:
        """
        Extract all exploration opportunities from AI analysis
        Returns list of {type, selector, description, action}
        """
        opportunities = []
        
        # All navigation items (sidebar, tabs, dropdowns, buttons)
        for item in analysis.get('navigation_items', []):
            item_type = item.get('type', 'link')
            item_text = item.get('text', 'item')
            
            opportunities.append({
                'type': item_type,
                'selector': item.get('selector'),
                'description': f"Click '{item_text}'",
                'action': 'click'
            })
        
        return opportunities
    
    def _is_dropdown_click(self, step: Dict) -> bool:
        """
        Check if a step is clicking a dropdown button
        """
        selector = step.get('selector', '')
        description = step.get('description', '').lower()
        
        # Check for dropdown indicators in selector or description
        dropdown_keywords = [
            'chevron', 'dropdown', 'menu', 'expand',
            'job', 'organization', 'qualifications', 'configuration',
            'entitlements', 'configure', 'reports', 'project info',
            'attendance', 'my trackers', 'employee trackers'
        ]
        
        for keyword in dropdown_keywords:
            if keyword in selector.lower() or keyword in description:
                return True
        
        return False
    
    def _queue_opportunities(self, current_state: Dict, opportunities: List[Dict]):
        """
        Add new states to exploration queue based on opportunities
        """
        if current_state['depth'] >= self.max_depth:
            print(f"[Orchestrator] Max depth reached, not queuing more states")
            return
        
        queued_count = 0
        duplicate_count = 0
        
        for opp in opportunities:
            # Create new state
            new_state = {
                'url': self.start_url,  # Always start from base URL
                'interaction_path': current_state['interaction_path'] + [self._create_step(opp)],
                'depth': current_state['depth'] + 1
            }
            
            # Create hash from interaction path to detect duplicates
            path_tuple = tuple(step['description'] for step in new_state['interaction_path'])
            
            # Check if this exact path is already queued
            if path_tuple in self.queued_state_hashes:
                duplicate_count += 1
                print(f"[Orchestrator] ⚠️ Found this path as duplicate, skipping it, '{path_tuple}'")
                continue  # Skip duplicate
            
            # Add to queue and tracking set
            self.exploration_queue.append(new_state)
            self._list_of_visited_paths.append(new_state.get("interaction_path")[-2:])
            self.queued_state_hashes.add(path_tuple)
            queued_count += 1
        
        print(f"[Orchestrator] Queued {queued_count} new states ({duplicate_count} duplicates skipped, queue size: {len(self.exploration_queue)})")
    
    def _create_step(self, opportunity: Dict) -> Dict:
        """
        Convert opportunity into a step that agent.execute_step() can handle
        """
        step = {
            'selector': opportunity['selector'],
            'description': opportunity['description'],
            'step_number': f"discovery_{self.states_explored}"
        }
        
        if opportunity['action'] == 'click':
            step['action'] = 'click'
        elif opportunity['action'] == 'select':
            step['action'] = 'select'
            step['value'] = opportunity['value']
        
        return step
    
    def _register_form(self, state: Dict, analysis: Dict, current_url: str):
        """
        Register a discovered form with its navigation path
        Creates an empty folder for the form
        """
        import os
        import re
        
        form_name = analysis.get('form_name', f'Form {self.forms_found + 1}')
        
        # Sanitize form name for folder (remove special chars)
        safe_name = re.sub(r'[^\w\s-]', '', form_name)
        safe_name = re.sub(r'[-\s]+', '_', safe_name).strip('_')
        
        form = {
            'id': f"form_{self.forms_found + 1}",
            'name': form_name,
            'url': current_url,
            'path': state['interaction_path'].copy(),  # This now includes ALL steps to reach the form
            'relationship_fields': analysis.get('relationship_fields', []),
            'depth': state['depth']
        }
        
        self.discovered_forms.append(form)
        self.forms_found += 1
        
        # Create empty folder for this form
        form_folder = os.path.join(self.output_dir, safe_name)
        try:
            os.makedirs(form_folder, exist_ok=True)
            print(f"[Orchestrator] 📁 Created folder: {form_folder}")
        except Exception as e:
            print(f"[Orchestrator] ⚠️ Could not create folder: {e}")
        
        print(f"\n{'='*70}")
        print(f"✅ FORM FOUND: {form['name']}")
        print(f"{'='*70}")
        print(f"URL: {current_url}")
        print(f"Path: {self._format_path(state['interaction_path'])}")
        print(f"Relationship Fields: {len(form['relationship_fields'])}")
        print(f"Folder: {safe_name}/")
        print(f"{'='*70}\n")
    
    def _hash_state(self, dom: str, url: str) -> str:
        """
        Create unique hash for a page state
        Uses DOM structure + URL
        """
        # Create signature from key DOM features
        from bs4 import BeautifulSoup
        soup = BeautifulSoup(dom, 'html.parser')
        
        # Get form signatures
        form_sigs = []
        for form in soup.find_all(['form', 'input', 'select', 'textarea']):
            form_sigs.append(f"{form.name}:{form.get('name', '')}:{form.get('type', '')}")
        
        # Get heading text
        headings = [h.get_text(strip=True) for h in soup.find_all(['h1', 'h2', 'h3'])]
        
        # Combine into hash
        signature = {
            'url': url,
            'forms': sorted(form_sigs),
            'headings': sorted(headings)
        }
        
        return hashlib.md5(json.dumps(signature, sort_keys=True).encode()).hexdigest()
    
    def _format_path(self, path: List[Dict]) -> str:
        """
        Format interaction path for display
        """
        if not path:
            return "Dashboard (start)"
        return " → ".join([step.get('description', 'unknown') for step in path])
    
    def _should_stop(self) -> bool:
        """
        Check if we should stop exploration
        """
        if self.states_explored >= self.max_states:
            print(f"\n[Orchestrator] Max states ({self.max_states}) reached")
            return True
        
        return False
    
    def save_results(self, output_file: str = None):
        """
        Save discovered forms to JSON file
        Uses default path if not specified: /home/{user}/automation_product_config/ai_projects/{project_name}/discovered_forms.json
        """
        if output_file is None:
            output_file = self.output_file
        
        try:
            with open(output_file, 'w') as f:
                json.dump(self.discovered_forms, f, indent=2)
            print(f"[Orchestrator] ✅ Saved {len(self.discovered_forms)} forms to {output_file}")
        except Exception as e:
            print(f"[Orchestrator] ❌ Failed to save results: {e}")
    
    def print_summary(self):
        """
        Print discovery summary
        """
        print(f"\n{'='*70}")
        print(f"DISCOVERY SUMMARY")
        print(f"{'='*70}")
        
        for i, form in enumerate(self.discovered_forms, 1):
            print(f"\n{i}. {form['name']}")
            print(f"   URL: {form['url']}")
            print(f"   Depth: {form['depth']}")
            print(f"   Relationship Fields: {len(form['relationship_fields'])}")
            print(f"   Path ({len(form['path'])} steps):")
            for j, step in enumerate(form['path'], 1):
                print(f"      {j}. {step['description']}")
        
        print(f"\n{'='*70}\n")
