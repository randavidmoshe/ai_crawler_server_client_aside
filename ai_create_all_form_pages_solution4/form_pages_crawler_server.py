# form_pages_crawler.py
# Server-side code - Handles AI analysis and file operations
# Communicates with agent for Selenium operations

import os
import json
import time
from typing import List, Tuple, Any, Dict, Set, Optional
from pathlib import Path

from form_utils import (
    get_project_base_dir, sanitize_filename
)
from ai_helper import AIHelper

import logging


class FormPagesCrawler:
    """
    Server-side crawler - handles AI analysis and file operations.
    Delegates all Selenium operations to agent.
    """
    
    def __init__(
        self,
        agent,  # Reference to agent object
        project_name: str = "default_project",
        use_ai: bool = True,
        api_key: str = None
    ):
        self.agent = agent  # Agent reference for callbacks
        self.project_name = project_name
        self.use_ai = use_ai
        
        # Initialize AI helper if enabled
        if self.use_ai:
            try:
                self.ai_helper = AIHelper(api_key=api_key)
                print("[Server] 🤖 AI-powered analysis enabled")
            except Exception as e:
                print(f"[Server] Warning: Could not initialize AI: {e}")
                self.use_ai = False
                self.ai_helper = None
        else:
            self.ai_helper = None
            print("[Server] AI disabled")
        
        self.project_base = get_project_base_dir(project_name)
        self.master_pages_path = self.project_base / "form_pages.json"
        self.hierarchy_path = self.project_base / "form_hierarchy.json"
        
        print(f"[Server] Project base: {self.project_base}")

    def get_existing_form_urls(self) -> Set[str]:
        """Load existing form URLs from form_relationships.json"""
        relationships_path = self.project_base / "form_relationships.json"
        existing_form_urls = set()
        
        if relationships_path.exists():
            try:
                with open(relationships_path, 'r', encoding='utf-8') as f:
                    relationships = json.load(f)

                # Build set of URLs (normalize for comparison)
                for form_name, form_data in relationships.items():
                    url = form_data.get("url", "")
                    # Normalize URL: remove #modal, remove query params
                    url_base = url.split('#')[0].split('?')[0]
                    if url_base:
                        existing_form_urls.add(url_base)

                print(f"[Server] 📂 Loaded {len(existing_form_urls)} existing form URLs")
            except Exception as e:
                print(f"[Server] ⚠️ Could not load form_relationships.json: {e}")
        else:
            print("[Server] No existing form_relationships.json found - starting fresh")
        
        return existing_form_urls

    def update_relationships_json(self, form_name: str, form_url: str, id_fields: List[str]):
        """Update form_relationships.json with ID fields"""
        relationships_path = self.project_base / "form_relationships.json"
        
        # Load existing relationships
        if relationships_path.exists():
            try:
                with open(relationships_path, 'r', encoding='utf-8') as f:
                    relationships = json.load(f)
            except:
                relationships = {}
        else:
            relationships = {}
        
        # Add/update this form
        if form_name not in relationships:
            relationships[form_name] = {}
        
        relationships[form_name]["url"] = form_url
        relationships[form_name]["id_fields"] = id_fields
        
        # Save back
        with open(relationships_path, 'w', encoding='utf-8') as f:
            json.dump(relationships, f, indent=2)

    def extract_form_name_with_ai(self, url: str, button_text: str = "") -> str:
        """
        Extract form name using AI analysis.
        Falls back to simple cleanup if AI fails.
        """
        if not self.use_ai or not self.ai_helper:
            return self._simple_form_name_cleanup(url, button_text)
        
        try:
            prompt = f"""Extract the entity name from this form page.

URL: {url}
Button that opened it: {button_text}

Rules:
1. Return ONLY the entity name (e.g., "Employee", "Project", "Invoice")
2. If compound, use underscore (e.g., "Job_Title", "Leave_Request")
3. Remove action words like "add", "create", "edit", "new"
4. Capitalize first letter of each word
5. Maximum 3 words

Return ONLY the entity name, nothing else."""

            response = self.ai_helper._call_claude(prompt)
            
            # Clean response
            form_name = response.strip().strip('"').strip("'")
            
            # Validate
            if form_name and len(form_name) < 50 and not any(c in form_name for c in ['/', '\\', '?', '*']):
                return form_name
            
            # Fallback
            return self._simple_form_name_cleanup(url, button_text)
            
        except Exception as e:
            print(f"[Server] AI form name extraction failed: {e}")
            return self._simple_form_name_cleanup(url, button_text)

    def _simple_form_name_cleanup(self, url: str, button_text: str) -> str:
        """Simple form name extraction - fallback when AI fails"""
        import re
        
        action_words = ['add', 'create', 'new', 'edit', 'view', 'manage']
        
        cleaned = button_text.lower()
        for word in action_words:
            cleaned = cleaned.replace(word, '').strip()
        
        if cleaned:
            words = cleaned.split()
            return '_'.join(w.capitalize() for w in words)
        
        return button_text

    def is_submission_button_ai(self, button_text: str) -> bool:
        """
        Check if button is a submission button using AI.
        Falls back to keyword matching if AI fails.
        """
        if not self.use_ai or not self.ai_helper:
            return self._is_submission_button_keyword(button_text)
        
        try:
            prompt = f"""Is this button text a submission button for a form?

Button text: "{button_text}"

Submission buttons include: Save, Submit, Create, Add, Update, Confirm, Send, Apply, Register, etc.
NOT submission buttons: Cancel, Close, Back, Delete, Remove, Export, etc.

Answer with ONLY "yes" or "no"."""

            response = self.ai_helper._call_claude(prompt).strip().lower()
            
            if 'yes' in response:
                return True
            elif 'no' in response:
                return False
            else:
                # Fallback to keyword
                return self._is_submission_button_keyword(button_text)
                
        except Exception as e:
            print(f"[Server] AI submission check failed: {e}")
            return self._is_submission_button_keyword(button_text)

    def _is_submission_button_keyword(self, button_text: str) -> bool:
        """Keyword-based submission button detection"""
        text_lower = button_text.lower()
        
        submission_keywords = [
            'save', 'submit', 'create', 'add', 'update', 'confirm',
            'send', 'apply', 'register', 'post', 'publish'
        ]
        
        for keyword in submission_keywords:
            if keyword in text_lower:
                return True
        
        return False

    def find_form_page_candidates(self, page_html: str, page_url: str) -> List[Dict[str, Any]]:
        """Use AI to find clickable elements that likely lead to form pages"""
        if not self.use_ai or not self.ai_helper:
            return []
        
        return self.ai_helper.find_form_page_candidates(page_html, page_url)

    def save_forms_list(self, forms: List[Dict[str, Any]]):
        """Save forms list to form_pages.json"""
        try:
            with open(self.master_pages_path, 'w', encoding='utf-8') as f:
                json.dump(forms, f, indent=2)
            print(f"[Server] ✅ Saved {len(forms)} forms to {self.master_pages_path}")
        except Exception as e:
            print(f"[Server] ❌ Error saving forms: {e}")

    def create_minimal_json_for_form(self, form: Dict[str, Any]):
        """Create folder and JSONs for discovered form"""
        form_name = form["form_name"]
        form_slug = sanitize_filename(form_name)

        # Create ONLY the form folder, no subfolders
        form_folder = self.project_base / form_slug
        form_folder.mkdir(parents=True, exist_ok=True)
        print(f"  📁 Created folder: {form_folder}")

        # Extract modal metadata
        is_modal = form.get("is_modal", False)
        modal_trigger = form.get("modal_trigger", "")

        gui_pre_create_actions = []
        for step in form.get("navigation_steps", []):
            action_entry = {
                "update_type": "",
                "update_ai_stages": [step],
                "action_description": step.get("description", ""),
                "update_css": "",
                "update_css_playwright": "",
                "webdriver_sleep_before_action": "",
                "playwright_sleep_before_action": "",
                "non_editable_condition": {"operator": "or"},
                "validate_non_editable": False
            }
            gui_pre_create_actions.append(action_entry)
        
        main_setup = {
            "gui_pre_create_actions": gui_pre_create_actions,
            "css_values": [],
            "gui_post_update_actions": [],
            "gui_post_create_actions": [],
            "gui_pre_update_actions": [],
            "gui_pre_verification_actions": [],
            "system_values": [
                {"name": "main_component_tab", "value": "main"},
                {"name": "is_sub_project", "value": False},
                {"name": "is_modal", "value": is_modal},
                {"name": "modal_trigger", "value": modal_trigger}
            ],
            "sub_components": [],
            "pre_fields_values": [],
            "non_editable_condition": {},
            "gui_fields": []
        }
        
        main_setup_path = form_folder / f"{form_slug}_main_setup.json"
        with open(main_setup_path, "w", encoding="utf-8") as f:
            json.dump(main_setup, f, indent=2)
        print(f"  ✅ Created: {main_setup_path.name}")
        
        setup = {
            "gui_pre_create_actions": [],
            "css_values": [],
            "all_sub_components_items_list": [form_name, f"{form_name}_main"],
            "gui_pre_verification_actions": [],
            "gui_pre_update_actions": [],
            "system_values": [
                {"name": "is_sub_project", "value": True},
                {"name": "is_modal", "value": is_modal},
                {"name": "modal_trigger", "value": modal_trigger}
            ],
            "sub_components": [{"type": "single", "name": "main"}],
            "gui_fields": []
        }
        
        setup_path = form_folder / f"{form_slug}_setup.json"
        with open(setup_path, "w", encoding="utf-8") as f:
            json.dump(setup, f, indent=2)
        print(f"  ✅ Created: {setup_path.name}")

        # Agent verifies and fixes the path
        print(f"\n  🔍 Verifying navigation path...")
        self.agent._verify_and_fix_form(form)

    def update_form_json(self, form: Dict):
        """Update form JSON files with corrected navigation steps"""
        form_name = form["form_name"]
        form_slug = sanitize_filename(form_name)
        form_folder = self.project_base / form_slug
        
        # Update main_setup.json with corrected steps
        main_setup_path = form_folder / f"{form_slug}_main_setup.json"
        
        if main_setup_path.exists():
            with open(main_setup_path, 'r', encoding='utf-8') as f:
                main_setup = json.load(f)
            
            # Update navigation steps
            gui_pre_create_actions = []
            for step in form.get("navigation_steps", []):
                action_entry = {
                    "update_type": "",
                    "update_ai_stages": [step],
                    "action_description": step.get("description", ""),
                    "update_css": "",
                    "update_css_playwright": "",
                    "webdriver_sleep_before_action": "",
                    "playwright_sleep_before_action": "",
                    "non_editable_condition": {"operator": "or"},
                    "validate_non_editable": False
                }
                gui_pre_create_actions.append(action_entry)
            
            main_setup["gui_pre_create_actions"] = gui_pre_create_actions
            
            # Save
            with open(main_setup_path, 'w', encoding='utf-8') as f:
                json.dump(main_setup, f, indent=2)
            
            print(f"  ✅ Updated: {main_setup_path.name}")

    def build_hierarchy(self, forms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build parent-child hierarchy based on ID fields.
        Returns hierarchy with ordered_forms list.
        """
        print("\n" + "="*70)
        print("🔗 BUILDING FORM HIERARCHY")
        print("="*70)
        
        relationships_path = self.project_base / "form_relationships.json"
        
        # Load existing relationships
        if not relationships_path.exists():
            print("  ⚠️  No form_relationships.json found")
            return {"ordered_forms": [f["form_name"] for f in forms]}
        
        with open(relationships_path, "r", encoding="utf-8") as f:
            hierarchy = json.load(f)
        
        # Initialize parents/children for all forms
        for form_name in hierarchy.keys():
            if "parents" not in hierarchy[form_name]:
                hierarchy[form_name]["parents"] = []
            if "children" not in hierarchy[form_name]:
                hierarchy[form_name]["children"] = []
        
        # Build relationships
        relationships_found = 0
        
        for form_name, form_data in hierarchy.items():
            id_fields = form_data.get("id_fields", [])
            
            if not id_fields:
                continue
            
            for id_field in id_fields:
                id_field_lower = id_field.lower()
                
                for potential_parent_name, potential_parent_data in hierarchy.items():
                    if potential_parent_name == form_name:
                        continue
                    
                    parent_name_variants = [
                        potential_parent_name.lower(),
                        potential_parent_name.lower().replace('_', ' '),
                        potential_parent_name.lower().replace('_', '')
                    ]
                    
                    matched = False
                    for variant in parent_name_variants:
                        if variant in id_field_lower:
                            matched = True
                            break
                    
                    if matched:
                        print(f"  🔗 {form_name} → child of → {potential_parent_name} (via '{id_field}')")
                        relationships_found += 1
                        
                        # Add parent relationship
                        if potential_parent_name not in form_data["parents"]:
                            form_data["parents"].append(potential_parent_name)

                        # Add child relationship
                        if form_name not in hierarchy[potential_parent_name]["children"]:
                            hierarchy[potential_parent_name]["children"].append(form_name)

                        break  # Only match to one parent per ID field

        # Mark which forms are roots (no parents)
        for form_name, form_data in hierarchy.items():
            form_data["is_root"] = len(form_data["parents"]) == 0

        # Save updated JSON with relationships
        with open(relationships_path, "w", encoding="utf-8") as f:
            json.dump(hierarchy, f, indent=2)

        print(f"\n✅ Found {relationships_found} parent-child relationships")
        print(f"✅ Updated: {relationships_path}")
        print("=" * 70 + "\n")

        return hierarchy

    def print_ai_cost_summary(self):
        """Print AI cost summary"""
        if self.use_ai and self.ai_helper:
            self.ai_helper.print_cost_summary()

    def close_logger(self):
        """Placeholder for logger cleanup"""
        pass
