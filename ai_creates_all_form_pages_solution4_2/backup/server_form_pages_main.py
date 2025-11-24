# server_form_pages_main.py
# SERVER SIDE - Main server class
# Handles AI operations and communicates with agent

import os
from typing import List, Dict, Any, Optional
from server_form_pages_ai_helper import AIHelper


class Server:
    """
    Server running on AWS (future) or locally (current).
    Handles AI operations and coordinates with agent.
    """
    
    def __init__(self, api_key: Optional[str] = None):
        """
        Initialize server with AI capabilities
        
        Args:
            api_key: Anthropic API key (or from environment)
        """
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        
        # Track created form names
        self.created_form_names = []
        
        # Store parent reference fields for current form (to be used later)
        self.current_form_parent_fields = []
        
        # AI Helper - only initialize if API key available
        self.ai_helper = None
        if self.api_key:
            try:
                self.ai_helper = AIHelper(api_key=self.api_key)
                print("[Server] ✅ AI Helper initialized")
            except Exception as e:
                print(f"[Server] ⚠️ Failed to initialize AI: {e}")
        else:
            print("[Server] ⚠️ No API key - AI disabled")
    
    # ============================================================
    # AI METHODS - Called by Agent when it needs AI assistance
    # ============================================================
    
    def find_form_page_candidates(self, page_html: str, page_url: str) -> List[Dict[str, Any]]:
        """
        Agent calls this to get AI analysis of which elements might lead to forms
        
        Args:
            page_html: HTML content from agent's browser
            page_url: Current URL
            
        Returns:
            List of candidate elements with selectors and reasoning
        """
        if not self.ai_helper:
            print("[Server] ⚠️ AI not available - returning empty list")
            return []
        
        try:
            print(f"[Server] AI: Analyzing page for form candidates: {page_url}")
            candidates = self.ai_helper.find_form_page_candidates(page_html, page_url)
            print(f"[Server] AI: Found {len(candidates)} candidates")
            return candidates
        except Exception as e:
            print(f"[Server] ❌ AI error: {e}")
            return []
    
    def analyze_form_fields(self, page_html: str, page_url: str) -> List[Dict[str, Any]]:
        """
        Agent calls this to get AI analysis of form fields and obstacles
        
        Args:
            page_html: HTML content from agent's browser
            page_url: Current URL
            
        Returns:
            List of form fields with type, obstacles, and solutions
        """
        if not self.ai_helper:
            print("[Server] ⚠️ AI not available - returning empty list")
            return []
        
        try:
            print(f"[Server] AI: Analyzing form fields: {page_url}")
            fields = self.ai_helper.analyze_form_fields(page_html, page_url)
            print(f"[Server] AI: Found {len(fields)} form fields")
            return fields
        except Exception as e:
            print(f"[Server] ❌ AI error: {e}")
            return []
    
    def determine_field_assignment(self, field_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Agent calls this to get AI determination of how to fill a field
        
        Args:
            field_info: Field metadata (type, label, name, etc.)
            
        Returns:
            Assignment configuration (type, value, etc.)
        """
        if not self.ai_helper:
            print("[Server] ⚠️ AI not available - returning default")
            return {"type": "assign_random_text", "size": "50"}
        
        try:
            assignment = self.ai_helper.determine_field_assignment(field_info)
            return assignment
        except Exception as e:
            print(f"[Server] ❌ AI error: {e}")
            return {"type": "assign_random_text", "size": "50"}
    
    def suggest_field_value(self, field_info: Dict[str, Any]) -> str:
        """
        Agent calls this to get suggested test value for a field
        
        Args:
            field_info: Field metadata
            
        Returns:
            Suggested value as string
        """
        if not self.ai_helper:
            return "Test Value"
        
        try:
            value = self.ai_helper.suggest_field_value(field_info)
            return value
        except Exception as e:
            print(f"[Server] ❌ AI error: {e}")
            return "Test Value"
    
    def get_ai_cost_summary(self) -> Dict[str, Any]:
        """
        Get AI usage cost summary
        
        Returns:
            Dictionary with token usage and cost information
        """
        if not self.ai_helper:
            return {
                "api_calls": 0,
                "input_tokens": 0,
                "output_tokens": 0,
                "total_tokens": 0,
                "input_cost": 0.0,
                "output_cost": 0.0,
                "total_cost": 0.0
            }
        
        return self.ai_helper.get_cost_summary()
    
    def print_ai_cost_summary(self):
        """Print formatted AI cost summary"""
        if self.ai_helper:
            self.ai_helper.print_cost_summary()
        else:
            print("\n[Server] No AI usage to report\n")
    
    def is_submission_button(self, button_text: str) -> bool:
        """
        Agent calls this to determine if button is a submission button
        
        Args:
            button_text: Text on the button
            
        Returns:
            True if submission button, False otherwise
        """
        if not self.ai_helper:
            print("[Server] ⚠️ AI not available - returning False")
            return False
        
        try:
            prompt = f"""You are analyzing a button on a web page to determine if it's a form SUBMISSION button.

            Button text: "{button_text}"
            

            CRITICAL: Distinguish between two types of buttons:

            ✅ SUBMISSION BUTTONS (answer YES):
            - Buttons that SUBMIT/SAVE data on the CURRENT form
            - Examples: 'Submit', 'Save', 'Update', 'Confirm', 'Apply', 'Send'
            - These buttons process data that's already entered in the form

            ❌ NOT SUBMISSION BUTTONS (answer NO):
            - Buttons that NAVIGATE to a NEW form page to create/add something
            - Examples: 'Add', 'Create', 'New', 'Insert', 'Register'
            - These buttons OPEN a form, they don't submit one
            - Also: search buttons, filter buttons, navigation buttons, cancel buttons

            Question: Does this button SUBMIT data on the current form, or does it OPEN a new form page?
            If it opens a new form → answer 'no'
            If it submits current form data → answer 'yes'

            Answer ONLY 'yes' or 'no'."""
            
            response = self.ai_helper.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=10,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )
            
            answer = response.content[0].text.strip().upper()
            is_submission = answer.startswith("YES")
            
            print(f"[Server] AI: Button '{button_text}' → {answer}")
            return is_submission
            
        except Exception as e:
            print(f"[Server] ❌ AI error: {e}")
            return False
    
    def create_form_folder(self, project_name: str, form: Dict[str, Any]):
        """
        Server creates folder for discovered form (no files inside)
        
        Args:
            project_name: Project name
            form: Form dictionary with form_name, navigation_steps, is_modal, etc.
        """
        import json
        from pathlib import Path
        from agent_form_pages_utils import get_project_base_dir, sanitize_filename
        
        form_name = form["form_name"]
        form_slug = sanitize_filename(form_name)
        
        # Track this form name
        if form_name not in self.created_form_names:
            self.created_form_names.append(form_name)
        
        # Create ONLY the form folder, no files inside
        project_base = get_project_base_dir(project_name)
        form_folder = project_base / form_slug
        form_folder.mkdir(parents=True, exist_ok=True)
        print(f"[Server] 📁 Created folder: {form_folder}")
        
        # Update form_relationships.json with AI-found parent fields
        relationships_path = project_base / "form_relationships.json"
        
        # Load existing or create new
        if relationships_path.exists():
            with open(relationships_path, "r", encoding="utf-8") as f:
                relationships = json.load(f)
        else:
            relationships = {
                "project_name": project_name,
                "total_forms": 0,
                "forms": {}
            }
        
        # Extract parent field names from AI results (stage 3.5)
        ai_parent_fields = [field["field_name"] for field in self.current_form_parent_fields]
        
        # Extract FULL navigation steps (complete objects with xpath, type, description, etc.)
        navigation_steps = form.get("navigation_steps", [])
        
        # Add/update this form's entry
        relationships["forms"][form_name] = {
            "url": form["form_url"],
            "navigation_steps": navigation_steps,  # Full navigation step objects
            "id_fields": ai_parent_fields,  # Use AI-found parent fields
            "parents": [],
            "children": []
        }
        
        relationships["total_forms"] = len(relationships["forms"])
        
        # Save
        with open(relationships_path, "w", encoding="utf-8") as f:
            json.dump(relationships, f, indent=2)
        
        print(f"[Server] ✅ Updated: form_relationships.json with {len(ai_parent_fields)} parent fields")
    
    def extract_form_name(self, context_data: Dict[str, Any], page_html: str = "", screenshot_base64: str = None) -> str:
        """
        Agent calls this to extract form name using AI
        
        Args:
            context_data: Dictionary with url, url_path, button_clicked, page_title, headers, form_labels
            page_html: Full page HTML/DOM from agent
            screenshot_base64: Base64-encoded screenshot of the form page for AI vision
            
        Returns:
            Clean form name as string
        """
        if not self.ai_helper:
            print("[Server] ⚠️ AI not available - returning default")
            return "unknown_form"
        
        try:
            # Add existing form names to context
            existing_names_str = ""
            if self.created_form_names:
                existing_names_str = f"""
    EXISTING FORM NAMES (don't use these):
    {', '.join(self.created_form_names)}"""
            
            context_str = f"""URL: {context_data['url']}
    URL Path: {context_data['url_path']}
    Button Clicked: {context_data['button_clicked']}
    Page Title: {context_data['page_title']}
    Headers: {', '.join(context_data['headers']) if context_data['headers'] else 'None'}
    Form Labels: {', '.join(context_data['form_labels']) if context_data['form_labels'] else 'None'}{existing_names_str}"""

            prompt = f"""You are analyzing a form page to determine its proper name for a test automation framework.

            Context about the page:
            {context_str}

            Based on this context, what is the BEST name for this form?

            Rules:
            1. Focus on the ENTITY (thing) being managed, NOT the action
               - ✅ Good: "Employee", "Leave_Type", "Performance_Review"
               - ❌ Bad: "Employee_Search", "Leave_Type_List", "Search_Performance"

            2. Remove action/operation words:
               - Remove: search, view, list, add, create, edit, update, delete, manage, management, configure, configuration, define, tracker, log
               - Exception: Keep action words ONLY if they're part of the entity name itself (e.g., "Leave_Entitlement")

            3. Simplify compound names:
               - "performance_tracker_log" → "Performance"
               - "candidate_search" → "Candidate"  
               - "system_users_admin" → "System_User"
               - "leave_type_list" → "Leave_Type"

            4. Use Title_Case_With_Underscores (e.g., "Performance_Review", "Leave_Type")

            5. Use singular or plural based on context:
               - For forms managing ONE item: use singular (e.g., "Employee", "Project")
               - For forms managing LISTS/MULTIPLE: keep plural if it's the entity name (e.g., "Leave_Entitlements" if that's the actual feature name)

            6. Be concise: 1-3 words maximum

            7. Remove technical suffixes: .htm, .php, _page, _form, etc.

            8. Choose a name that does NOT exist in EXISTING FORM NAMES list above

            Examples:
            - URL: /employee/search → Name: "Employee"
            - URL: /performance/tracker/log → Name: "Performance"
            - URL: /leave/types/list → Name: "Leave_Type"
            - URL: /candidate/view → Name: "Candidate"

            Respond with ONLY the form name, nothing else.

            Form name:"""

            print(f"[Server] AI: Analyzing page context for form name...")
            print(f"[Server] AI:   - URL: {context_data['url_path']}")
            print(f"[Server] AI:   - Title: {context_data['page_title']}")
            if self.created_form_names:
                print(f"[Server] AI:   - Existing: {self.created_form_names}")

            response = self.ai_helper.client.messages.create(
                model="claude-3-5-haiku-20241022",
                max_tokens=30,
                temperature=0,
                messages=[{"role": "user", "content": prompt}]
            )

            form_name = response.content[0].text.strip()
            form_name = form_name.lower()
            form_name = form_name.strip('"\'` ')

            print(f"[Server] AI: ✅ Determined form name: '{form_name}'")
            
            # Store page_html and screenshot for later saving to form folder
            self.current_form_page_html = page_html
            self.current_form_screenshot_base64 = screenshot_base64
            
            # Extract parent reference fields (stage 3.5)
            print(f"[Server] AI: Extracting parent reference fields...")
            self.current_form_parent_fields = self.ai_helper.extract_parent_reference_fields(form_name, page_html, screenshot_base64)
            print(f"[Server] AI: ✅ Found {len(self.current_form_parent_fields)} parent reference fields")
            
            return form_name
            
        except Exception as e:
            print(f"[Server] ❌ AI error: {e}")
            return "unknown_form"
    
    # ============================================================
    # AGENT CONTROL METHODS - Server calls these to control agent
    # ============================================================
    
    def start_crawl(
        self,
        agent,  # Agent instance
        start_url: str,
        project_name: str,
        username: str = None,
        password: str = None,
        logged_in: bool = True,
        target_form_pages: Optional[List[str]] = None,
        max_pages: int = 50,
        max_depth: int = 20,
        discovery_only: bool = True,
        slow_mode: bool = True,
        headless: bool = False,
        hidden: bool = False
    ):
        """
        Server tells agent to start crawling
        
        Args:
            agent: Agent instance to control
            start_url: URL to start crawling from
            project_name: Project name for organization
            username: Login username (optional)
            password: Login password (optional)
            logged_in: Whether user is already logged in
            target_form_pages: Specific forms to find (empty = discover all)
            max_pages: Maximum pages to crawl
            max_depth: Maximum navigation depth
            discovery_only: Only discover forms, don't fill them
            slow_mode: Add delays for observation
            headless: Run browser in headless mode
            hidden: Use undetected chromedriver
        """
        print("\n" + "="*70)
        print("🖥️  SERVER → AGENT: Starting crawl operation")
        print("="*70)
        print(f"[Server] Project: {project_name}")
        print(f"[Server] Start URL: {start_url}")
        print(f"[Server] Discovery Only: {discovery_only}")
        print(f"[Server] AI Enabled: {self.ai_helper is not None}")
        print("="*70 + "\n")
        
        # Tell agent to start driver
        agent.start_driver(headless=headless, hidden=hidden)
        
        # Tell agent to run crawler (agent will call back to server for AI)
        agent.run_crawler(
            start_url=start_url,
            project_name=project_name,
            username=username,
            password=password,
            logged_in=logged_in,
            use_ai=(self.ai_helper is not None),
            target_form_pages=target_form_pages or [],
            server=self,  # Pass server reference so agent can call back
            max_pages=max_pages,
            max_depth=max_depth,
            discovery_only=discovery_only,
            slow_mode=slow_mode
        )
        
        # Tell agent to stop driver
        agent.stop_driver()
        
        print("\n" + "="*70)
        print("🖥️  SERVER: Crawl completed")
        print("="*70)
        
        # Show AI costs
        if self.ai_helper:
            self.print_ai_cost_summary()
    
    def update_form_verification(self, project_name: str, form_name: str, navigation_steps: List[Dict[str, Any]], verification_attempts: int = 1):
        """
        Update form_relationships.json with verified navigation steps
        Called by Agent after Stage 8 (verification)
        
        Args:
            project_name: Project name
            form_name: Form name
            navigation_steps: Verified navigation steps
            verification_attempts: Number of attempts it took to verify
        """
        import json
        from pathlib import Path
        from agent_form_pages_utils import get_project_base_dir
        from datetime import datetime
        
        project_base = get_project_base_dir(project_name)
        relationships_path = project_base / "form_relationships.json"
        
        if not relationships_path.exists():
            print(f"[Server] ⚠️  form_relationships.json not found")
            return
        
        # Load existing relationships
        with open(relationships_path, "r", encoding="utf-8") as f:
            relationships = json.load(f)
        
        # Update the form's navigation steps and verification metadata
        if form_name in relationships["forms"]:
            relationships["forms"][form_name]["navigation_steps"] = navigation_steps
            relationships["forms"][form_name]["verification_attempts"] = verification_attempts
            relationships["forms"][form_name]["last_verified"] = datetime.now().isoformat()
            
            # Save
            with open(relationships_path, "w", encoding="utf-8") as f:
                json.dump(relationships, f, indent=2)
            
            print(f"[Server] ✅ Updated verification data in form_relationships.json for '{form_name}'")
        else:
            print(f"[Server] ⚠️  Form '{form_name}' not found in relationships")
    
    def build_hierarchy(self, project_name: str) -> Dict[str, Any]:
        """
        Build parent-child relationships from form_relationships.json
        Called by Agent after all forms are discovered (Stage 10)
        
        Args:
            project_name: Project name
            
        Returns:
            Updated hierarchy dict
        """
        import json
        from agent_form_pages_utils import get_project_base_dir
        
        project_base = get_project_base_dir(project_name)
        relationships_path = project_base / "form_relationships.json"
        
        if not relationships_path.exists():
            print("[Server] ⚠️  No form_relationships.json found!")
            return {}
        
        print("\n" + "=" * 70)
        print("🔗 SERVER: BUILDING PARENT-CHILD RELATIONSHIPS")
        print("=" * 70)
        
        # Load the JSON (already has ID fields from discovery)
        with open(relationships_path, "r", encoding="utf-8") as f:
            hierarchy = json.load(f)
        
        print(f"[Server] Analyzing {hierarchy['total_forms']} forms...\n")
        
        relationships_found = 0
        
        # Build parent-child relationships based on ID fields
        for form_name, form_data in hierarchy["forms"].items():
            id_fields = form_data.get("id_fields", [])
            
            if not id_fields:
                continue
            
            for id_field in id_fields:
                # Extract potential parent name from ID field
                # e.g., "employee_id" -> "employee"
                potential_parent_base = (id_field
                                         .replace("_id", "")
                                         .replace("id", "")
                                         .replace("-", "")
                                         .replace("_", "")
                                         .strip()
                                         .lower())
                
                if not potential_parent_base:
                    continue
                
                # Find matching parent form
                for parent_name in hierarchy["forms"].keys():
                    if parent_name == form_name:
                        continue
                    
                    parent_name_normalized = parent_name.replace("_", "").replace("-", "").lower()
                    
                    # Check if ID field matches parent form name
                    if potential_parent_base in parent_name_normalized or parent_name_normalized in potential_parent_base:
                        print(f"  🔗 {form_name} is child of {parent_name} (via {id_field})")
                        
                        relationships_found += 1
                        
                        # Add parent relationship
                        if parent_name not in form_data["parents"]:
                            form_data["parents"].append(parent_name)
                        
                        # Add child relationship
                        if form_name not in hierarchy["forms"][parent_name]["children"]:
                            hierarchy["forms"][parent_name]["children"].append(form_name)
                        
                        break  # Only match to one parent per ID field
        
        # Mark which forms are roots (no parents)
        for form_name, form_data in hierarchy["forms"].items():
            form_data["is_root"] = len(form_data["parents"]) == 0
        
        # Save updated JSON with relationships
        with open(relationships_path, "w", encoding="utf-8") as f:
            json.dump(hierarchy, f, indent=2)
        
        print(f"\n[Server] ✅ Found {relationships_found} parent-child relationships")
        print(f"[Server] ✅ Updated: {relationships_path}")
        print("=" * 70 + "\n")
        
        return hierarchy
    
    def health_check(self) -> Dict[str, Any]:
        """
        Check server health status (useful for future network communication)
        
        Returns:
            Health status dictionary
        """
        return {
            "status": "ok",
            "ai_available": self.ai_helper is not None,
            "has_api_key": self.api_key is not None
        }
