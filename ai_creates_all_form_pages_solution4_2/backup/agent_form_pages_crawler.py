# form_pages_crawler.py
# Version 6 - With comprehensive debug logging

import os
import json
import time
from typing import List, Tuple, Any, Dict, Set
from urllib.parse import urlparse


from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait

from agent_form_pages_utils import (
    OUT_MASTER_PAGES, OUT_DIR_HIER, get_project_base_dir, create_form_page_folder,
    wait_dom_ready, safe_click, page_has_form_fields, sanitize_filename, visible_text,
    dismiss_all_popups_and_overlays,
)
from server_form_pages_ai_helper import AIHelper

import logging

class RecursiveNavigationState:
    """Tracks navigation state during recursive exploration"""
    def __init__(self, url: str, path: List[Dict], depth: int):
        self.url = url
        self.path = path
        self.depth = depth

class FormPagesCrawler:
    """Recursive form page crawler with discovery_only mode"""

    def __init__(
        self,
        driver,
        start_url: str,
        base_url: str,
        project_name: str = "default_project",
        max_pages: int = 20,
        max_depth: int = 5,
        use_ai: bool = True,
        target_form_pages: List[str] = None,
        api_key: str = None,
        discovery_only: bool = False,
        slow_mode: bool = False,
        server=None
    ):
        self.driver = driver
        self.server = server

        self.logger = logging.getLogger('init_logger')
        self.result_logger_gui = logging.getLogger('init_result_logger_gui')

        self.start_url = start_url
        self.base_url = base_url
        self.max_pages = max_pages
        self.max_depth = max_depth
        self.project_name = project_name
        self.use_ai = use_ai
        self.target_form_pages = target_form_pages or []
        self.discovery_only = discovery_only
        self.master: List[Dict[str, Any]] = []
        
        # Track visited states
        self.visited_urls: Set[str] = set()
        self.visited_states: Set[str] = set()

        self.clicked_form_buttons: Set[str] = set()


        # NEW: Store global navigation items (captured at depth 0)
        self.global_navigation_items: Set[str] = set()
        self.global_locators: Set[str] = set()

        # Entry point keywords (buttons that OPEN forms)
        self.strict_form_keywords = [
            # Creation/Addition
            "add", "create", "new", "insert",
            # Edit mode
            "edit", "modify", "change", "revise", "amend",
            # Initiation
            "rate", "review", "feedback", "survey", "open", "start", "begin", "launch",
            # Assignment/Management
            "assign",
            # Applications/Registration
            "register", "sign up", "signup", "join", "enroll", "subscribe",
            "apply", "file", "claim", "request",
            # Financial transactions
            "pay", "transfer", "deposit", "withdraw", "buy", "purchase", "donate", "invest",
            # Booking
            "book", "reserve", "schedule",
            # Communication
            "send message", "contact", "share", "invite", "comment", "reply",
            # Plus variations
            "+ add", "+ new", "+ create", "+ edit"
        ]

        self.plus_symbols = ["+", "➕"]
        # Window management
        self.main_window_handle = None
        self.button_blacklist = [
            # Commercial
            "upgrade", "pricing",
            "checkout", "order",
            
            # Navigation/Info
            "logout", "log out", "sign out", "about", "help", "support",
            "contact", "faq", "documentation", "docs", "tutorial",
            "guide", "feedback", "report", "terms", "privacy",
            
            # Actions
            "download", "export", "import", "print", "share", "save as",
            "copy", "delete", "remove", "cancel", "close", "reset", "clear", "clean"
            
            # Social/External
            "facebook", "twitter", "linkedin", "instagram", "youtube",
            "social", "follow", "like", "subscribe",
            
            # Settings
            "preferences", "settings", "profile", "account", "notifications",

            # Password-related
            "password", "change password", "update password", "reset password",
            "forgot password", "new password",

            # Other
            "back", "home", "previous", "next page", "search", "filter",
            "×", "✓", "✕", "close", "dismiss",  # ← ADD THIS LINE
        ]
        
        self.base_domain = urlparse(self.start_url).netloc
        
        if self.use_ai:
            try:
                self.ai_helper = AIHelper(api_key=api_key)
                print("[Crawler] 🤖 AI-powered recursive exploration enabled")
            except Exception as e:
                print(f"[Crawler] Warning: Could not initialize AI: {e}")
                self.use_ai = False
                self.ai_helper = None
        else:
            self.ai_helper = None
            print("[Crawler] Using keyword-based exploration")
        
        self.project_base = get_project_base_dir(project_name)
        self.master_pages_path = self.project_base / "form_pages.json"
        self.hierarchy_path = self.project_base / "form_hierarchy.json"
        relationships_path = self.project_base / "form_relationships.json"
        self.existing_form_urls = set()
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
                        self.existing_form_urls.add(url_base)

                print(
                    f"[Resume] 📂 Loaded {len(self.existing_form_urls)} existing form URLs from form_relationships.json")
            except Exception as e:
                print(f"[Resume] ⚠️ Could not load form_relationships.json: {e}")
                self.existing_form_urls = set()
        else:
            print("[Resume] No existing form_relationships.json found - starting fresh")
            self.existing_form_urls = set()
        
        print(f"[Crawler] Project base: {self.project_base}")
        print(f"[Crawler] Max forms: {self.max_pages}")
        print(f"[Crawler] Max depth: {self.max_depth} levels")
        
        if self.discovery_only:
            print(f"[Crawler] 🔍 MODE: DISCOVERY ONLY (Phase 1)")
            print(f"[Crawler]    → Will find forms and create JSONs")
            print(f"[Crawler]    → Will skip field exploration")
        else:
            print(f"[Crawler] 🚀 MODE: FULL EXPLORATION (Phase 2)")
            print(f"[Crawler]    → Will discover forms AND explore fields")
        
        if self.target_form_pages:
            print(f"[Crawler] FILTERING: {self.target_form_pages}")
        else:
            print(f"[Crawler] No filter - discovering ALL forms")

        # Configure timeout based on mode
        if slow_mode:
            self.element_wait_timeout = 15
            self.navigation_wait = 2.0
            print("[Crawler] 🐢 SLOW MODE enabled - using 15 second timeouts")
        else:
            self.element_wait_timeout = 5
            self.navigation_wait = 0.5
            print("[Crawler] 🐢 SLOW MODE disabled")

    def _check_dropdown_opened(self) -> bool:
        """Check if a dropdown/menu appeared using common patterns"""
        time.sleep(0.3)

        dropdown_selectors = [
            # Bootstrap
            ".dropdown-menu.show",
            ".dropdown-menu[style*='display: block']",
            ".dropdown-menu[style*='display:block']",

            # OrangeHRM specific
            ".oxd-dropdown-menu",

            # Material UI
            ".MuiMenu-paper",
            ".MuiPopover-paper",

            # Generic patterns
            "[role='menu']:not([style*='display: none'])",
            "[role='menu']:not([style*='display:none'])",
            "ul.menu.open",
            "ul.submenu[style*='display: block']",
            ".nav-dropdown.active",
            "*[class*='menu'][class*='open']",
            "*[class*='dropdown'][class*='show']",
            "ul[style*='display: block']",
            "ul[style*='display:block']"
        ]

        for selector in dropdown_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed() and el.size['height'] > 0:
                        print(f"    [Dropdown] ✅ Detected with: {selector}")
                        return True
            except:
                continue

        return False

    def _check_if_modal_opened(self) -> bool:
        """Check if a modal/dialog/popup is currently open"""
        modal_selectors = [
            ".modal.show",
            ".modal.in",
            ".modal[style*='display: block']",
            "[role='dialog'][style*='display: block']",
            "[role='dialog']:not([style*='display: none'])",
            ".dialog[open]",
            ".popup[style*='display: block']",
            ".overlay.active",
            ".ant-modal-wrap",
            ".MuiDialog-root",
            "[class*='modal'][class*='open']",
            "[class*='dialog'][class*='open']"
        ]

        try:
            for selector in modal_selectors:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        # Additional check: modal should have some content
                        if el.text.strip() or len(el.find_elements(By.CSS_SELECTOR, "*")) > 3:
                            return True
            return False
        except Exception as e:
            return False

    def _close_modal(self) -> bool:
        """Close any open modal/dialog"""
        close_selectors = [
            ".modal.show .close",
            ".modal.show [data-dismiss='modal']",
            ".modal.show button[aria-label='Close']",
            "[role='dialog'] .close",
            "[role='dialog'] button[aria-label='Close']",
            "[role='dialog'] [class*='close']",
            ".dialog[open] .close",
            ".popup .close",
            ".ant-modal-close",
            ".MuiDialog-root button[aria-label='close']",
            "button.cancel",
            "button:has-text('Cancel')",
            "button:has-text('Close')"
        ]

        # Try clicking close buttons
        for selector in close_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        safe_click(self.driver, el)
                        time.sleep(0.3)
                        print(f"[Modal] ✓ Closed via: {selector}")
                        return True
            except:
                continue

        # Try ESC key
        try:
            from selenium.webdriver.common.keys import Keys
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.3)
            print(f"[Modal] ✓ Closed via ESC key")
            return True
        except:
            pass

        # Try clicking backdrop/overlay
        try:
            overlays = self.driver.find_elements(By.CSS_SELECTOR,
                                                 ".modal-backdrop, .overlay, [class*='backdrop'], [class*='overlay']")
            for overlay in overlays:
                if overlay.is_displayed():
                    safe_click(self.driver, overlay)
                    time.sleep(0.3)
                    print(f"[Modal] ✓ Closed via backdrop click")
                    return True
        except:
            pass

        print(f"[Modal] ⚠️ Could not close modal")
        return False

    def _find_dropdown_items(self) -> List[Dict[str, Any]]:
        """Find clickable items inside the opened dropdown"""
        dropdown_items = []

        # Form-opening keywords (same categories as _find_form_opening_buttons)
        form_opening_keywords = [
            'add', 'create', 'new', 'edit', 'modify', 'insert',
            'register', 'book', 'schedule', 'apply', 'request',
            'pay', 'transfer', 'buy', 'donate', 'invest', 'rate',
            'review', 'feedback', 'survey', 'open', 'start'
        ]

        dropdown_selectors = [
            ".dropdown-menu.show",
            ".dropdown-menu[style*='display: block']",
            "[role='menu']",
            ".oxd-dropdown-menu",
            "ul.menu.open",
            "*[class*='menu'][class*='open']"
        ]

        for selector in dropdown_selectors:
            try:
                dropdowns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for dropdown in dropdowns:
                    if not dropdown.is_displayed():
                        continue

                    items = dropdown.find_elements(By.CSS_SELECTOR, "a, button, li[onclick], [role='menuitem'], li")

                    seen_texts = set()

                    for item in items:
                        if not item.is_displayed():
                            continue

                        text = visible_text(item).strip()
                        if not text or len(text) > 50:
                            continue

                        if any(blocked in text.lower() for blocked in self.button_blacklist):
                            continue

                        if text.lower() in seen_texts:
                            continue
                        seen_texts.add(text.lower())

                        # Check if this dropdown item likely opens a form
                        text_lower = text.lower()
                        likely_opens_form = any(keyword in text_lower for keyword in form_opening_keywords)

                        dropdown_items.append({
                            'element': item,
                            'text': text,
                            'selector': self._get_unique_selector(item),
                            'type': 'dropdown_item',
                            'likely_opens_form': likely_opens_form
                        })

                    if dropdown_items:
                        # Highlight items that likely open forms
                        form_items = [d['text'] for d in dropdown_items if d.get('likely_opens_form')]
                        if form_items:
                            print(f"    [Dropdown] 🎯 Items that likely open forms: {form_items}")
                        print(f"    [Dropdown] Found {len(dropdown_items)} items total")
                        return dropdown_items
            except:
                continue

        return dropdown_items

    def _navigate_efficiently(self, path: List[dict]) -> bool:
        """
        Navigate using optimized algorithm: always try to jump to the end,
        fall back to earlier steps only when needed.
        Does NOT modify the path - only uses it for navigation.
        """
        if not path:
            return True

        clicked_up_to = -1  # Index of last successfully clicked element (-1 = at dashboard)
        target = len(path) - 1  # Index of final element we want to reach

        max_attempts = len(path) * 2  # Safety limit to prevent infinite loops
        attempts = 0

        while clicked_up_to < target and attempts < max_attempts:
            attempts += 1
            found = False

            # Try to click from target backwards to (clicked_up_to + 1)
            for i in range(target, clicked_up_to, -1):
                step = path[i]
                element = self._find_element_by_selector_or_text(
                    step.get('selector', ''),
                    step.get('text', '')
                )

                if element and element.is_displayed():
                    try:
                        if safe_click(self.driver, element):
                            time.sleep(0.3)
                            clicked_up_to = i
                            found = True
                            break
                    except:
                        continue

            if not found:
                # Couldn't click any element - navigation failed
                return False

        # Check if we reached the target
        return clicked_up_to == target

    def _matches_target(self, form_name: str) -> bool:
        """Check if form matches target filter"""
        if not self.target_form_pages:
            return True
        
        form_name_lower = form_name.lower()
        for target in self.target_form_pages:
            target_lower = target.lower()
            if target_lower in form_name_lower or form_name_lower in target_lower:
                print(f"[Filter] ✓ MATCH: '{form_name}' matches '{target}'")
                return True
        
        print(f"[Filter] ✗ SKIP: '{form_name}'")
        return False

    def _should_skip_element(self, element) -> bool:
        """Check if element should be skipped"""
        try:
            if not element or not element.is_displayed():
                return True

            text = visible_text(element).lower()

            if '\n' in text:
                words = text.split()
                for word in words:
                    if word.strip() in self.button_blacklist:
                        print(f"[Protection] 🚫 Skipping: '{word}'")
                        return True
                return False

            if any(blocked in text for blocked in self.button_blacklist):
                print(f"[Protection] 🚫 Skipping: '{text[:50]}'")
                return True

            href = element.get_attribute("href")
            if href:
                if any(ext in href.lower() for ext in ['.pdf', '.zip', '.exe']):
                    print(f"[Protection] 🚫 Skipping download: {href[:50]}")
                    return True

                if href.startswith('http'):
                    link_domain = urlparse(href).netloc
                    if link_domain and link_domain != self.base_domain:
                        print(f"[Protection] 🚫 Skipping external: {link_domain}")
                        return True

            return False
        except:
            return True

    def _extract_form_name_from_page(self) -> str:
        """Extract form name from current page"""
        try:
            title = self.driver.title
            if title and len(title) < 100:
                return title
            for tag in ['h1', 'h2']:
                headers = self.driver.find_elements(By.TAG_NAME, tag)
                if headers and headers[0].is_displayed():
                    text = visible_text(headers[0])
                    if text and len(text) < 100:
                        return text
            return "Unknown Form"
        except:
            return "Unknown Form"

    def _extract_form_name_from_context(self, url: str, button_text: str) -> str:
        """Extract entity name from form page - single word or underscore format"""

        action_words = [
            'add', 'create', 'new', 'edit', 'update', 'register',
            'view', 'show', 'display', 'define', 'verify', 'configure',
            'manage', 'setup', 'set', 'assign', 'apply', 'save', 'insert',
            'open', 'start', 'begin', 'launch', 'modify', 'change', 'revise',
            'amend'
        ]

        try:
            # PRIORITY 1: Extract from URL (most reliable!)
            import re
            path_parts = [p for p in url.split('/') if p and not p.isdigit()]

            # Get the LAST meaningful part
            if path_parts:
                last_part = path_parts[-1]

                # Remove action prefixes from camelCase
                for action in action_words:
                    last_part = re.sub(f'^{action}', '', last_part, flags=re.IGNORECASE)

                # Convert camelCase to words
                words = re.findall('[A-Z][a-z]*|[a-z]+', last_part)

                # Remove any remaining action words
                cleaned_words = [w for w in words if w.lower() not in action_words]

                if cleaned_words:
                    if len(cleaned_words) == 1:
                        return cleaned_words[0].capitalize()
                    else:
                        return '_'.join(w.capitalize() for w in cleaned_words)

            # FALLBACK 2: Try headers
            for tag in ['h1', 'h2', 'h3']:
                headers = self.driver.find_elements(By.TAG_NAME, tag)
                for header in headers:
                    if header.is_displayed():
                        text = visible_text(header).strip()
                        if text and len(text) < 100:
                            entity = text.lower()
                            for action in action_words:
                                entity = entity.replace(f'{action} ', '').replace(f' {action}', '').strip()

                            if entity:
                                words = entity.split()
                                if len(words) == 1:
                                    return words[0].capitalize()
                                elif len(words) > 1:
                                    return '_'.join(w.capitalize() for w in words)

            # FALLBACK 3: Try page title
            title = self.driver.title
            if title and title != "OrangeHRM":
                entity = title.replace("OrangeHRM", "").strip().lower()
                for action in action_words:
                    entity = entity.replace(f'{action} ', '').replace(f' {action}', '').strip()

                if entity:
                    words = entity.split()
                    if len(words) == 1:
                        return words[0].capitalize()
                    elif len(words) > 1:
                        return '_'.join(w.capitalize() for w in words)

            # FALLBACK 4: Clean button text
            entity = button_text.lower()
            for action in action_words:
                entity = entity.replace(action, '').strip()

            if entity:
                words = entity.split()
                if words:
                    return '_'.join(w.capitalize() for w in words) if len(words) > 1 else words[0].capitalize()

            return button_text

        except:
            return button_text

    def _is_constrained_field(self, element) -> bool:
        """Check if field has constrained values (dropdown, autocomplete) vs free text"""
        tag = element.tag_name.lower()

        if tag == 'select':
            return True

        if tag == 'input':
            if element.get_attribute('list'):
                return True

            role = element.get_attribute('role') or ''
            if 'combobox' in role.lower():
                return True

            if element.get_attribute('aria-autocomplete'):
                return True

            # CHECK CLASS NAME for autocomplete patterns  ← ADD THIS
            class_name = element.get_attribute('class') or ''
            if any(keyword in class_name.lower() for keyword in ['autocomplete', 'typeahead', 'suggest', 'hint']):
                return True

            if element.get_attribute('readonly'):
                return True

        return False

    def _extract_id_fields_from_dom(self) -> List[str]:
        """Extract ID fields by analyzing HTML attributes AND labels"""
        print(f"        [DEBUG ID EXTRACTION] ⭐ Starting field extraction...")
        id_fields = []

        try:
            # Entity keywords to look for
            entity_keywords = [
                'user', 'employee', 'customer', 'project', 'vacancy',
                'candidate', 'supervisor', 'manager', 'reviewer',
                'location', 'department', 'job', 'position',
                'nationality', 'skill', 'category', 'status',
                'performance', 'tracker', 'timesheet', 'leave',
                'attendance', 'shift', 'work', 'termination', 'role'
            ]

            # FIRST: Check labels (most reliable)
            labels = self.driver.find_elements(By.TAG_NAME, 'label')
            print(f"        [DEBUG ID EXTRACTION] Found {len(labels)} label elements")
            for label in labels:
                if not label.is_displayed():
                    continue

                label_text = (label.text or "").lower().strip()
                if not label_text:
                    continue

                # Check if label contains entity keywords
                for keyword in entity_keywords:
                    if keyword in label_text:
                        # Found entity reference in label
                        if keyword not in id_fields:
                            id_fields.append(keyword)
                            print(f"        [ID Field] Found from label: '{label.text}' → {keyword}")
                        break

            # SECOND: Check form elements
            form_elements = self.driver.find_elements(By.CSS_SELECTOR,
                                                      "input, select, textarea")
            
            print(f"        [DEBUG ID EXTRACTION] Found {len(form_elements)} form elements (input/select/textarea)")

            # NEW: Track top dropdown/autocomplete fields (potential foreign keys)
            top_dropdowns = []
            field_count = 0
            visible_count = 0

            for element in form_elements:
                if not element.is_displayed():
                    continue
                
                visible_count += 1
                field_count += 1
                
                # Get field details for debugging
                element_type = element.get_attribute("type") or element.tag_name.lower()
                field_name = (element.get_attribute("name") or 
                             element.get_attribute("id") or "").lower()
                
                print(f"        [DEBUG ID EXTRACTION] Field #{field_count}: type={element_type}, name={field_name}")
                
                # NEW: Capture top 4 dropdown/autocomplete fields
                if field_count <= 4:
                    # Check if it's a dropdown or has autocomplete
                    is_dropdown = element.tag_name.lower() == 'select'
                    has_autocomplete = element.get_attribute("autocomplete") or element.get_attribute("list")
                    
                    print(f"        [DEBUG ID EXTRACTION]   → is_dropdown={is_dropdown}, has_autocomplete={has_autocomplete}")
                    
                    if (is_dropdown or has_autocomplete) and field_name:
                        if field_name not in top_dropdowns:
                            top_dropdowns.append(field_name)
                            print(f"        [Potential FK] Top field #{field_count}: {field_name} ({'dropdown' if is_dropdown else 'autocomplete'})")

                # Get various attributes
                field_name = (element.get_attribute("name") or
                              element.get_attribute("id") or "").lower()
                field_class = (element.get_attribute("class") or "").lower()
                placeholder = (element.get_attribute("placeholder") or "").lower()

                # Check data-* attributes
                for attr_name in ['data-entity', 'data-parent', 'data-source',
                                  'data-reference', 'data-foreign-key', 'data-model']:
                    attr_value = element.get_attribute(attr_name)
                    if attr_value:
                        attr_value = attr_value.lower()
                        if attr_value not in id_fields:
                            id_fields.append(attr_value)
                            print(f"        [ID Field] Found from {attr_name}: {attr_value}")

                if not field_name or len(field_name) < 2:
                    continue

                # Check if field name contains "id"
                if "id" in field_name and field_name not in id_fields:
                    if self._is_constrained_field(element):
                        id_fields.append(field_name)
                        print(f"        [ID Field] Found: {field_name} (constrained)")
                    else:
                        print(f"        [ID Field] Skipped: {field_name} (free text)")

                # Check if field name, class, or placeholder contains entity keywords
                for keyword in entity_keywords:
                    if (keyword in field_name or keyword in field_class or keyword in placeholder):
                        if keyword not in id_fields and self._is_constrained_field(element):
                            id_fields.append(keyword)
                            print(f"        [ID Field] Entity reference: {keyword} (constrained)")
                        break

                # Check dropdown option values
                if element.tag_name.lower() == 'select':
                    try:
                        options = element.find_elements(By.TAG_NAME, 'option')
                        for option in options[:5]:
                            value = (option.get_attribute('value') or "").lower()
                            for keyword in entity_keywords:
                                if keyword in value:
                                    entity_name = f"{keyword}_id"
                                    if entity_name not in id_fields:
                                        id_fields.append(entity_name)
                                        print(f"        [ID Field] Entity from dropdown: {entity_name}")
                                    break
                    except:
                        pass

            print(f"        [DEBUG ID EXTRACTION] Visible fields: {visible_count}, Top dropdowns found: {len(top_dropdowns)}")
            
            # NEW: Add top dropdowns to id_fields (they're potential foreign keys)
            for dropdown in top_dropdowns:
                if dropdown not in id_fields:
                    id_fields.append(dropdown)
                    print(f"        [ID Field] Added top dropdown: {dropdown}")

            print(f"        [DEBUG ID EXTRACTION] ✅ Extraction complete. Total fields: {len(id_fields)}")
            print(f"        [DEBUG ID EXTRACTION] Final list: {id_fields}")

        except Exception as e:
            print(f"        [ID Field] Error extracting: {e}")
            import traceback
            traceback.print_exc()

        return id_fields

    def _update_relationships_json(self, form_name: str, form_url: str, id_fields: List[str]):
        """Update form_relationships.json immediately when form is discovered"""
        relationships_path = self.project_base / "form_relationships.json"

        # Load existing JSON or create new
        if relationships_path.exists():
            with open(relationships_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = {
                "project_name": self.project_name,
                "total_forms": 0,
                "forms": {}
            }

        # Add/update this form's info
        data["forms"][form_name] = {
            "url": form_url,
            "id_fields": id_fields,
            "parents": [],
            "children": []
        }

        data["total_forms"] = len(data["forms"])

        # Save immediately
        with open(relationships_path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2)

        print(f"        [Relationships] Updated JSON with {form_name}")


    def _manage_windows(self, current_path: List[Dict] = None) -> List[Dict[str, Any]]:
        """Check tabs for forms, then close them"""
        discovered_forms = []
        try:
            all_handles = self.driver.window_handles
            if len(all_handles) > 1:
                print(f"[Window] 🔍 Detected {len(all_handles)} tabs")
                for handle in all_handles:
                    if handle != self.main_window_handle:
                        try:
                            self.driver.switch_to.window(handle)
                            time.sleep(0.5)
                            wait_dom_ready(self.driver)
                            tab_url = self.driver.current_url
                            tab_domain = urlparse(tab_url).netloc

                            if tab_domain != self.base_domain:
                                print(f"[Window]   ✗ External: {tab_domain}")
                                self.driver.close()
                                continue

                            if page_has_form_fields(self.driver, self._is_submission_button_ai):
                                form_name = self._extract_form_name_with_ai(tab_url, "")

                                # Check if URL already exists (normalize for comparison)
                                url_base = tab_url.split('#')[0].split('?')[0]
                                if url_base in self.existing_form_urls:
                                    print(f"[Window]   ⏭️  Form URL already discovered - skipping (URL: {url_base})")
                                    self.driver.close()
                                    continue

                                print(f"[Window]   ✅ Found form: {form_name}")
                                full_path = (current_path or []) + [{
                                    'action': 'click', 'text': 'opens_in_new_tab',
                                    'selector': '', 'description': f"Opens '{form_name}' in new tab"
                                }]
                                discovered_forms.append({
                                    "form_name": form_name, "form_url": tab_url,
                                    "navigation_steps": self._convert_path_to_steps(full_path),
                                    "navigation_depth": len(full_path),
                                    "immediate_first_page": False, "opened_in_new_tab": True
                                })
                            self.driver.close()
                        except Exception as e:
                            print(f"[Window]   ✗ Error: {e}")
                            try:
                                self.driver.close()
                            except:
                                pass
                self.driver.switch_to.window(self.main_window_handle)
                print(f"[Window] ↩️  Returned to main window")
        except Exception as e:
            print(f"[Window] Error: {e}")
            try:
                self.driver.switch_to.window(self.main_window_handle)
            except:
                pass
        return discovered_forms

    def _safe_click_with_protection(self, element, current_path: List[Dict] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """Click with protection and new tab detection"""
        discovered_forms = []
        if self._should_skip_element(element):
            return False, discovered_forms

        current_windows = len(self.driver.window_handles)

        if not safe_click(self.driver, element):
            return False, discovered_forms

        wait_dom_ready(self.driver)
        time.sleep(0.2)  # Small buffer


        new_windows = len(self.driver.window_handles)
        if new_windows > current_windows:
            print(f"[Click] 🔍 New tab opened")
            discovered_forms = self._manage_windows(current_path)

        new_url = self.driver.current_url
        new_domain = urlparse(new_url).netloc
        if new_domain != self.base_domain:
            print(f"[Protection] 🚫 External redirect, going back")
            self.driver.back()
            wait_dom_ready(self.driver)
            return False, discovered_forms

        return True, discovered_forms

    def _gather_all_form_pages(self) -> List[Dict[str, Any]]:
        """RECURSIVE EXPLORATION"""
        all_forms: List[Dict[str, Any]] = []
        
        print("\n" + "="*70)
        if self.discovery_only:
            print("🔍 PHASE 1: DISCOVERING ALL FORM PAGES")
        else:
            print("🚀 STARTING RECURSIVE EXPLORATION")
        print("="*70)
        print(f"Strategy: Click everything up to {self.max_depth} levels deep")
        print(f"Looking for: 'Add', 'Create', 'New' buttons that open forms")
        if self.discovery_only:
            print(f"Mode: Discovery only - will skip field exploration")
        print("="*70 + "\n")
        
        self.driver.get(self.start_url)
        self.main_window_handle = self.driver.current_window_handle

        print("[Crawler] Checking for popups...")
        dismiss_all_popups_and_overlays(self.driver)
        time.sleep(0.5)

        wait_dom_ready(self.driver)
        time.sleep(2)
        
        initial_state = RecursiveNavigationState(
            url=self.start_url,
            path=[],
            depth=0
        )
        
        queue = [initial_state]
        explored_count = 0

        while queue and explored_count < self.max_pages * 3:
            # Use DFS: Pop from END to explore children before siblings
            state = queue.pop()  # ← Changed from pop(0) to pop()
            
            print(f"\n{'='*60}")
            print(f"[DEBUG] Popped from queue:")
            print(f"  URL: {state.url}")
            print(f"  Path: {[s.get('text', '') for s in state.path]}")
            print(f"  Depth: {state.depth}")
            print(f"  Queue size: {len(queue)}")
            print(f"{'='*60}")

            state_key = self._get_state_key(state)
            print(f"[DEBUG] State key: {state_key[:100]}")
            
            if state_key in self.visited_states:
                print(f"[DEBUG] ❌ Already visited - SKIPPING")
                continue

            self.visited_states.add(state_key)
            explored_count += 1
            print(f"[DEBUG] ✅ New state - exploring (count: {explored_count})")

            new_tab_forms = self._manage_windows(state.path)
            if new_tab_forms:
                for form in new_tab_forms:
                    if self._matches_target(form["form_name"]):
                        all_forms.append(form)

                        # NEW: Create folder + JSONs immediately
                        if self.discovery_only:
                            self._create_minimal_json_for_form(all_forms[-1])

                        print(f"{indent}    ✅ Form #{len(all_forms)}: {form['form_name']} (new tab)")
                        if len(all_forms) >= self.max_pages:
                            self.master = all_forms[:]
                            self._save_forms_list(all_forms)
                            return all_forms
            
            if state.depth > self.max_depth:
                print(f"[DEBUG] ❌ Max depth exceeded - SKIPPING")
                continue
            
            indent = "  " * state.depth
            print(f"\n{indent}[Depth {state.depth}] Exploring: {state.url[:60]}")
            print(f"{indent}[DEBUG] Navigating with path: {[s.get('text', '') for s in state.path]}")
            
            if not self._navigate_to_state(state):
                print(f"{indent}[DEBUG] ❌ Navigation FAILED")
                continue
            
            print(f"{indent}[DEBUG] ✅ Navigation succeeded")
            print(f"{indent}[DEBUG] Current URL: {self.driver.current_url}")

            # NEW: Check if the last click opened a dropdown
            if state.path:  # We clicked something to get here
                time.sleep(0.5)
                if self._check_dropdown_opened():
                    last_clicked = state.path[-1].get('text', '')
                    print(f"{indent}[Dropdown] ✅ Detected after clicking '{last_clicked}'")

                    # ✅ MARK the last step as opening a dropdown (so path optimizer keeps it paired)
                    state.path[-1]['description'] = f"Click '{last_clicked}' (opens dropdown)"

                    dropdown_items = self._find_dropdown_items()
                    for item in dropdown_items:
                        item_text = item.get('text', '')[:40]
                        selector = item.get('selector', '')

                        # Check if selector already seen (use text+selector as unique key)
                        unique_key = f"{item_text}|{selector}"
                        if selector and unique_key in self.global_locators:
                            print(f"{indent}[DEBUG]   Skipping dropdown item '{item_text}' - selector already seen: {selector}")
                            continue

                        # Queue dropdown item (no global_locators check - parent already passed)
                        new_path = state.path + [{
                            'action': 'click',
                            'text': item.get('text', ''),
                            'selector': selector,
                            'description': f"Click '{item_text}' (dropdown item)"
                        }]

                        new_state = RecursiveNavigationState(
                            url=f"{state.url}#dropdown#{last_clicked}#{item_text}",
                            path=new_path,
                            depth=state.depth + 1
                        )

                        queue.append(new_state)

                        # Mark as seen AFTER queuing (same as regular clickables)
                        if selector:
                            unique_key = f"{item_text}|{selector}"
                            self.global_locators.add(unique_key)


                        print(f"{indent}[DEBUG]   Queued dropdown item: '{item_text}' (depth {state.depth + 1}) [{selector[:80]}...]")

                    continue



            # Check if we landed directly on a form page (no "Add" button needed)
            if page_has_form_fields(self.driver, self._is_submission_button_ai):
                form_url = self.driver.current_url
                form_name = self._extract_form_name_with_ai(form_url, "")

                # Skip password-related forms
                if "password" in form_name.lower():
                    print(f"{indent}⚠️  Skipping password form: {form_name}")
                    continue

                if self._matches_target(form_name):
                    if not any(f["form_url"] == form_url for f in all_forms):
                        print(f"{indent}✅ Direct form page: {form_name}")

                        # ✅ EXTRACT ID FIELDS FROM DOM
                        id_fields = self._extract_id_fields_from_dom()

                        all_forms.append({
                            "form_name": form_name,
                            "form_url": form_url,
                            "navigation_steps": self._convert_path_to_steps(state.path),
                            "navigation_depth": state.depth,
                            "immediate_first_page": state.depth == 0,
                            "direct_form_page": True,
                            "id_fields": id_fields  # ✅ ADD THIS LINE
                        })

                        # ✅ UPDATE JSON IMMEDIATELY
                        self._update_relationships_json(form_name, form_url, id_fields)

                        # NEW: Create folder + JSONs immediately
                        if self.discovery_only:
                            self._create_minimal_json_for_form(all_forms[-1])


                        if len(all_forms) >= self.max_pages:
                            self.master = all_forms[:]
                            self._save_forms_list(all_forms)
                            return all_forms

                    # Already on a form page - skip further exploration of this page
                    print(f"{indent}[DEBUG] Already on form page - skipping button/clickable exploration")
                    continue

            # Track which buttons we've already tested (by text)
            clicked_button_texts = set()
            found_any_forms = False

            # Keep re-finding buttons until no new ones to click
            while True:
                # Re-find form buttons on current page (fresh WebElements!)
                form_buttons = self._find_form_opening_buttons()

                if not form_buttons:
                    break

                # Filter out buttons we've already clicked
                unclicked_buttons = [b for b in form_buttons if b.get('text', '') not in clicked_button_texts]

                if not unclicked_buttons:
                    print(f"{indent}  ✅ All form buttons tested")
                    break

                button = unclicked_buttons[0]
                button_text = button.get('text', 'Unknown')

                import datetime
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                print(
                    f"[{timestamp}] [DEBUG] Clicking form button: '{button_text}' ({len(clicked_button_texts) + 1}/{len(form_buttons)})")

                clicked_button_texts.add(button_text)


                # ✅ Mark this button's selector as seen so it won't be queued as a regular clickable
                button_selector = button.get('selector', '')
                if button_selector:
                    unique_key = f"{button_text}|{button_selector}"
                    self.global_locators.add(unique_key)
                    print(
                        f"{indent}    [Global] Added form button to global_locators: '{button_text}' | {button_selector[:80]}...")


                screenshots_folder = self.project_base / "debug_screenshots"
                screenshots_folder.mkdir(exist_ok=True)
                self.driver.save_screenshot(
                    str(screenshots_folder / f"form_before_click_{button_text}_{timestamp}.png"))

                url_before = self.driver.current_url

                success, new_tab_forms = self._safe_click_with_protection(
                    button.get('element'),
                    state.path
                )

                if success:
                    wait_dom_ready(self.driver)
                    time.sleep(0.5)

                    url_after = self.driver.current_url
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    print(f"[{timestamp}] [DEBUG] URL before: {url_before}")
                    print(f"[{timestamp}] [DEBUG] URL after:  {url_after}")

                    self.driver.save_screenshot(
                        str(screenshots_folder / f"form_after_click_{button_text}_{timestamp}.png"))

                    if url_before == url_after:
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        print(f"[{timestamp}] {indent}    ⚠️  URL didn't change - checking for modal...")

                        # Check if a modal opened
                        if self._check_if_modal_opened():
                            print(f"{indent}    [Modal] ✅ Detected modal/popup after clicking '{button_text}'")

                            # Check if modal has form fields + submission button
                            if page_has_form_fields(self.driver, self._is_submission_button_ai):
                                print(f"{indent}    [Modal] ✅ Modal contains a form!")

                                # Extract form information
                                form_url = url_after  # Use the page URL that triggered the modal

                                # Get form name from AI or URL
                                form_name = self._extract_form_name_with_ai(form_url, button_text)

                                # Check if URL already exists (normalize for comparison)
                                url_base = form_url.split('#')[0].split('?')[0]
                                if url_base in self.existing_form_urls:
                                    print(f"{indent}    ⏭️  Form URL already discovered - skipping (URL: {url_base})")
                                    self._close_modal()
                                    self._navigate_to_state(state)
                                    continue



                                if "password" in form_name.lower():
                                    print(f"{indent}    ⚠️  Skipping password form: {form_name}")
                                    self._close_modal()
                                    self._navigate_to_state(state)
                                    continue

                                # Create form entry
                                form_entry = {
                                    "form_name": form_name,
                                    "form_url": form_url + "#modal",
                                    "navigation_steps": state.path + [{
                                        'action': 'click',
                                        'text': button_text,
                                        'selector': button.get('selector', ''),
                                        'description': f"Click '{button_text}' (opens modal form)"
                                    }],
                                    "is_modal": True,
                                    "modal_trigger": button_text
                                }

                                # Check for duplicates
                                if not any(f["form_name"] == form_name for f in all_forms):
                                    all_forms.append(form_entry)

                                    if self.discovery_only:
                                        self._create_minimal_json_for_form(form_entry)

                                    print(f"{indent}    ✅ Form #{len(all_forms)}: {form_name} (modal)")
                                else:
                                    print(f"{indent}    ⚠️  Modal form '{form_name}' already discovered - skipping")
                            else:
                                print(f"{indent}    [Modal] ❌ Modal does not contain a valid form")

                            # Close the modal
                            self._close_modal()
                            time.sleep(0.5)
                            wait_dom_ready(self.driver)
                        else:
                            print(f"{indent}    ⚠️  No modal detected - truly no navigation happened")

                        # Navigate back to original state
                        self._navigate_to_state(state)
                        continue

                    for form in new_tab_forms:
                        if self._matches_target(form["form_name"]):
                            all_forms.append(form)
                            if self.discovery_only:
                                self._create_minimal_json_for_form(all_forms[-1])
                            print(f"{indent}    ✅ Form #{len(all_forms)}: {form['form_name']} (new tab)")

                    time.sleep(1.5)
                    wait_dom_ready(self.driver)

                    time.sleep(1.5)
                    wait_dom_ready(self.driver)

                    # ✅ CHECK DUPLICATE URL IMMEDIATELY (before expensive AI calls)
                    form_url = self.driver.current_url
                    form_url_base = form_url.split('?')[0].split('#')[0]

                    if any(f["form_url"].split('?')[0].split('#')[0] == form_url_base for f in all_forms):
                        print(f"{indent}      ⚠️  Form URL already discovered - skipping duplicate")
                        self._navigate_to_state(state)
                        continue

                    # Now check form fields (only for new URLs)
                    if page_has_form_fields(self.driver, self._is_submission_button_ai):
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        print(f"[{timestamp}] [DEBUG] ✅ page_has_form_fields = TRUE")

                        form_name = self._extract_form_name_with_ai(form_url, button_text)

                        url_base = form_url.split('#')[0].split('?')[0]
                        if url_base in self.existing_form_urls:
                            print(f"{indent}    ⏭️  Form URL already discovered - skipping (URL: {url_base})")
                            self._navigate_to_state(state)
                            continue

                        if "password" in form_name.lower():
                            print(f"{indent}    ⚠️  Skipping password form: {form_name}")
                            self._navigate_to_state(state)
                            continue

                        full_path = state.path + [{
                            'action': 'click',
                            'text': button_text,
                            'selector': button.get('selector', ''),
                            'description': f"Click '{button_text}' to open form"
                        }]

                        if self._matches_target(form_name):
                            found_any_forms = True

                            if any(f["form_url"] == form_url for f in all_forms):
                                print(f"{indent}    ⚠️  Duplicate form URL - skipping")
                                self._navigate_to_state(state)
                                continue

                            print(f"{indent}    ✅ Form #{len(all_forms) + 1}: {form_name}")

                            # ✅ EXTRACT ID FIELDS FROM DOM
                            id_fields = self._extract_id_fields_from_dom()

                            nav_steps = self._convert_path_to_steps(state.path)
                            nav_steps.append({
                                "action": "click",
                                "selector": button.get('selector', ''),
                                "locator_text": button_text,
                                "is_form_button": True,
                                "description": f"Click '{button_text}' button to open form"
                            })

                            all_forms.append({
                                "form_name": form_name,
                                "form_url": form_url,
                                "navigation_steps": nav_steps,
                                "navigation_depth": state.depth + 1,
                                "immediate_first_page": False,
                                "id_fields": id_fields  # ✅ ADD THIS LINE
                            })

                            # ✅ UPDATE JSON IMMEDIATELY
                            self._update_relationships_json(form_name, form_url, id_fields)

                            if self.discovery_only:
                                self._create_minimal_json_for_form(all_forms[-1])

                            if len(all_forms) >= self.max_pages:
                                print(f"\n{indent}[Explore] Reached max pages ({self.max_pages}), stopping")
                                self.master = all_forms[:]
                                self._save_forms_list(all_forms)
                                return all_forms
                    else:
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        print(f"[{timestamp}] [DEBUG] ❌ page_has_form_fields = FALSE")
                        self.driver.save_screenshot(
                            str(screenshots_folder / f"form_NOT_detected_{button_text}_{timestamp}.png"))
                else:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    print(f"[{timestamp}] [DEBUG] ❌ Click on '{button_text}' failed")

                print(f"{indent}[DEBUG] Going back to: {state.url}")
                self._navigate_to_state(state)
                wait_dom_ready(self.driver)
                time.sleep(0.5)

            print(f"{indent}[DEBUG] found_any_forms = {found_any_forms}")

            clickables = self._find_all_clickables()


            # Capture global navigation at depth 0
            if state.depth == 0 and not self.global_navigation_items:
                for c in clickables:
                    text = c.get('text', '').lower()
                    if text:
                        self.global_navigation_items.add(text)
                print(f"[Navigation] 🌐 Captured {len(self.global_navigation_items)} global nav items")

            if clickables:
                print(f"{indent}  → Found {len(clickables)} clickable(s)")

                # Unified logic for ALL depths
                for clickable in clickables:
                    try:
                        click_text = clickable.get('text', '')[:40]

                        # Check for circular navigation
                        if any(step.get('text', '').lower() == click_text.lower() for step in state.path):
                            print(f"{indent}[DEBUG]   Skipping '{click_text}' - already in path (circular)")
                            continue

                        # Skip user dropdowns
                        if self._is_likely_user_dropdown(clickable):
                            print(f"{indent}[DEBUG]   Skipping '{click_text}' - user dropdown")
                            continue

                        # Check if selector already seen
                        # Check if selector already seen (use text+selector as unique key)
                        selector = clickable.get('selector', '')
                        unique_key = f"{click_text}|{selector}"
                        if selector and unique_key in self.global_locators:
                            print(f"{indent}[DEBUG]   Skipping '{click_text}' - selector already seen: {selector}")
                            continue

                        # Queue it
                        new_path = state.path + [{
                            'action': 'click',
                            'text': clickable.get('text', ''),
                            'selector': selector,
                            'description': f"Click '{click_text}'"
                        }]

                        new_state = RecursiveNavigationState(
                            url=f"{state.url}#{clickable.get('id', '')}",
                            path=new_path,
                            depth=state.depth + 1
                        )

                        queue.append(new_state)

                        # Mark as seen AFTER queuing
                        if selector:
                            unique_key = f"{click_text}|{selector}"
                            self.global_locators.add(unique_key)

                        print(f"{indent}[DEBUG]   Queued: '{click_text}' (depth {state.depth + 1}) [{selector[:80]}...]")

                    except Exception as e:
                        print(f"{indent}[DEBUG]   Error processing clickable: {e}")
                        continue


        print(f"\n[Explore] Exploration complete. Explored {explored_count} states.")
        print(f"[Explore] Found {len(all_forms)} form pages\n")
        
        self.master = all_forms[:]
        
        if self.server:
            self.server.save_forms_list(self.project_name, all_forms)
        else:
            self._save_forms_list(all_forms)
        
        return all_forms

    def _simple_form_name_cleanup(self, url: str, button_text: str) -> str:
        """Simple fallback - just removes .htm and cleans up"""
        if url:
            name = url.split('/')[-1].split('?')[0]
            for suffix in ['.htm', '.html', '_htm', '_html']:
                name = name.replace(suffix, '')
            name = name.replace('_', ' ').replace('-', ' ').title().replace(' ', '_')
            if name:
                return name.lower()

        if button_text:
            return button_text.replace(' ', '_').title().lower()

        return "unknown_form"


    def _extract_form_name_with_ai(self, url: str, button_text: str = "") -> str:
        """
        Use AI to determine the best form name by analyzing ALL available context:
        - URL structure
        - Button text clicked
        - Page title
        - Headers on the page
        - Any visible form labels

        Returns a clean, professional form name like "Bill_Pay" or "Request_Loan"
        """
        try:
            # Gather ALL context from the page
            context_data = {}

            # 1. URL
            context_data['url'] = url
            context_data['url_path'] = url.split('/')[-1] if '/' in url else url

            # 2. Button text (if clicked to get here)
            context_data['button_clicked'] = button_text if button_text else 'N/A'

            # 3. Page title
            try:
                context_data['page_title'] = self.driver.title
            except:
                context_data['page_title'] = 'N/A'

            # 4. Headers (h1, h2, h3)
            headers = []
            for tag in ['h1', 'h2', 'h3']:
                try:
                    elements = self.driver.find_elements(By.TAG_NAME, tag)
                    for el in elements[:3]:  # Only first 3 of each type
                        if el.is_displayed():
                            text = visible_text(el).strip()
                            if text and len(text) < 100:
                                headers.append(text)
                except:
                    pass
            context_data['headers'] = headers if headers else []

            # 5. Form field labels (gives hints about form purpose)
            labels = []
            try:
                label_elements = self.driver.find_elements(By.TAG_NAME, 'label')
                for label in label_elements[:5]:  # Only first 5 labels
                    if label.is_displayed():
                        text = visible_text(label).strip()
                        if text and len(text) < 50:
                            labels.append(text)
            except:
                pass
            context_data['form_labels'] = labels if labels else []

            # Call server to extract form name
            if self.server:
                return self.server.extract_form_name(context_data)
            else:
                # Fallback: direct API call if no server
                context_str = f"""URL: {context_data['url']}
    URL Path: {context_data['url_path']}
    Button Clicked: {context_data['button_clicked']}
    Page Title: {context_data['page_title']}
    Headers: {', '.join(context_data['headers']) if context_data['headers'] else 'None'}
    Form Labels: {', '.join(context_data['form_labels']) if context_data['form_labels'] else 'None'}"""

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

            Examples:
            - URL: /employee/search → Name: "Employee"
            - URL: /performance/tracker/log → Name: "Performance"
            - URL: /leave/types/list → Name: "Leave_Type"
            - URL: /candidate/view → Name: "Candidate"

            Respond with ONLY the form name, nothing else.

            Form name:"""

                print(f"    [AI Extract] Analyzing page context...")
                print(f"    [AI Extract]   - URL: {context_data['url_path']}")
                print(f"    [AI Extract]   - Title: {context_data['page_title']}")
                print(f"    [AI Extract]   - Headers: {context_data['headers']}")
                print(f"    [AI Extract]   - Labels: {context_data['form_labels']}")

                response = self.ai_helper.client.messages.create(
                    model="claude-3-5-haiku-20241022",
                    max_tokens=30,
                    temperature=0,
                    messages=[{"role": "user", "content": prompt}]
                )

                form_name = response.content[0].text.strip()
                form_name = form_name.lower()
                form_name = form_name.strip('"\'` ')

                print(f"    [AI Extract] ✅ Determined form name: '{form_name}'")
                return form_name

        except Exception as e:
            print(f"    [AI Extract] ⚠️ Error: {e}")
            # Fallback to basic extraction
            fallback = self._simple_form_name_cleanup(url, button_text)
            print(f"    [AI Extract] Using fallback: '{fallback}'")
            return fallback

    def _is_submission_button_ai(self, button_text: str) -> bool:
        """
        Use AI to determine if button text represents a form submission action.
        First checks a whitelist of known submission keywords.
        Only uses AI when uncertain.
        """
        # Whitelist of known submission button keywords
        submission_keywords = [
            'submit', 'save', 'update', 'create', 'apply', 'send',
            'transfer', 'register', 'confirm', 'process', 'complete',
            'pay', 'purchase', 'buy', 'checkout', 'continue',
            'post', 'publish', 'upload', 'book',
            'reserve', 'schedule', 'enroll', 'subscribe', 'donate'
        ]

        text_lower = button_text.lower().strip()

        # ✅ CHECK BLACKLIST FIRST - return False immediately if blacklisted
        if any(blocked in text_lower for blocked in self.button_blacklist):
            print(f"    [Blacklist] Button '{button_text}' → Blacklisted → ❌ NO (not a submission button)")
            return False

        # Check whitelist first - skip AI if we're confident
        for keyword in submission_keywords:
            if keyword in text_lower:
                print(f"    [Whitelist] Button '{button_text}' → Matched '{keyword}' → ✅ YES (no AI needed)")
                return True

        # Not in whitelist - ask server AI for uncertain cases
        if self.server:
            print(f"    [AI] Button '{button_text}' → Not in whitelist, asking server AI...")
            return self.server.is_submission_button(button_text)
        else:
            # Fallback: direct API call if no server
            try:
                print(f"    [AI] Button '{button_text}' → Not in whitelist, asking AI...")

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

                print(f"    [AI] Button '{button_text}' → AI says {answer}")
                return is_submission

            except Exception as e:
                print(f"    [AI] ⚠️  Error: {e}, defaulting to False")
                return False


    def _wait_for_page_stable(self, timeout: float = None):
        """Wait for page to be fully loaded and stable"""
        if timeout is None:
            timeout = self.navigation_wait * 3  # Use slow_mode setting

        wait_dom_ready(self.driver)

        # Wait for body to have content (not blank page)
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: len(d.find_element(By.TAG_NAME, 'body').text.strip()) > 50
            )
        except:
            pass

        # Small buffer for JS to finish
        time.sleep(0.2)

    def _save_forms_list(self, forms: List[Dict[str, Any]]):
        """Save master forms list"""
        with open(self.master_pages_path, "w", encoding="utf-8") as f:
            json.dump(forms, f, indent=2)
        print(f"✅ Saved master form pages list: {self.master_pages_path}")

    def _is_likely_user_dropdown(self, clickable: Dict) -> bool:
        """
        Detect if a clickable is likely a user dropdown (username in top-right)
        by checking its position and characteristics
        """
        try:
            element = clickable.get('element')
            text = clickable.get('text', '').lower()

            # User dropdowns are typically in top-right corner
            location = element.location
            x = location.get('x', 0)
            y = location.get('y', 0)

            # Get viewport width
            viewport_width = self.driver.execute_script("return window.innerWidth;")

            # Check if in top-right area (right 30% of screen, top 200px)
            is_top_right = x > (viewport_width * 0.7) and y < 200

            # Check if it has "user" in the text or matches common username patterns
            has_user_keyword = 'user' in text

            # Check if element has user-related classes
            classes = element.get_attribute('class') or ''
            has_user_class = 'user' in classes.lower()

            return is_top_right and (has_user_keyword or has_user_class)

        except Exception as e:
            return False


    def _get_state_key(self, state: RecursiveNavigationState) -> str:
        """State key based on navigation path, not URL"""
        # Create key from the path of clicks
        if not state.path:
            return self.start_url

        # Use the sequence of texts clicked
        path_key = " > ".join([step.get('text', '') for step in state.path])
        return path_key

    def _navigate_to_state(self, state: RecursiveNavigationState) -> bool:
        """Navigate to a specific state"""
        import datetime

        try:
            # Create screenshots folder
            screenshots_folder = self.project_base / "debug_screenshots"
            screenshots_folder.mkdir(exist_ok=True)

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            print(f"[{timestamp}] [Nav] Starting navigation to state: {self._get_state_key(state)[:80]}")
            self.driver.save_screenshot(str(screenshots_folder / f"nav_start_{timestamp}.png"))

            self.driver.get(self.start_url)
            dismiss_all_popups_and_overlays(self.driver)
            #wait_dom_ready(self.driver)
            #time.sleep(self.navigation_wait)
            self._wait_for_page_stable()

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            print(f"[{timestamp}] [Nav] At dashboard, about to navigate {len(state.path)} steps")
            self.driver.save_screenshot(str(screenshots_folder / f"nav_dashboard_{timestamp}.png"))

            # Navigate through each step sequentially
            for idx, step in enumerate(state.path, 1):
                step_text = step.get('text', '')[:30]
                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                print(f"[{timestamp}] [Nav] Step {idx}/{len(state.path)}: Looking for '{step_text}'")

                element = self._find_element_by_selector_or_text(
                    step.get('selector', ''),
                    step.get('text', '')
                )

                if not element:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    print(f"[{timestamp}] [Nav] ❌ Step {idx} FAILED: Element '{step_text}' NOT FOUND")
                    self.driver.save_screenshot(str(screenshots_folder / f"nav_notfound_step{idx}_{timestamp}.png"))
                    return False

                timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                print(f"[{timestamp}] [Nav] ✅ Step {idx}: Found '{step_text}', attempting click")
                self.driver.save_screenshot(str(screenshots_folder / f"nav_before_click_step{idx}_{timestamp}.png"))

                try:

                    if not safe_click(self.driver, element):
                        timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                        print(f"[{timestamp}] [Nav] ❌ Step {idx} FAILED: Click on '{step_text}' returned False")
                        self.driver.save_screenshot(str(screenshots_folder / f"nav_click_failed_step{idx}_{timestamp}.png"))
                        return False

                    #wait_dom_ready(self.driver)
                    #time.sleep(self.navigation_wait)  # Small buffer for animations
                    self._wait_for_page_stable()


                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    print(f"[{timestamp}] [Nav] ✅ Step {idx}: Clicked '{step_text}' successfully")



                    self.driver.save_screenshot(str(screenshots_folder / f"nav_after_click_step{idx}_{timestamp}.png"))

                except Exception as e:
                    timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
                    print(f"[{timestamp}] [Nav] ❌ Step {idx} EXCEPTION: '{step_text}': {e}")
                    self.driver.save_screenshot(str(screenshots_folder / f"nav_exception_step{idx}_{timestamp}.png"))
                    return False

            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            print(f"[{timestamp}] [Nav] ✅ Navigation SUCCESS - all {len(state.path)} steps completed")
            self.driver.save_screenshot(str(screenshots_folder / f"nav_success_{timestamp}.png"))
            return True

        except Exception as e:
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S_%f")
            print(f"[{timestamp}] [Nav] ❌ OUTER EXCEPTION: {e}")
            self.driver.save_screenshot(str(screenshots_folder / f"nav_outer_exception_{timestamp}.png"))
            return False

    def _find_shortest_path(self, path: List[dict]) -> List[dict]:
        """
        Find the shortest path by testing which intermediate steps are actually needed.
        Always keeps the first step, then optimizes the rest.
        IMPORTANT: Keeps dropdown openers with their items.
        Returns optimized path for JSON storage.
        """
        if len(path) <= 1:
            return path

        # Mark which steps are dropdown items (must keep their opener)
        dropdown_pairs = []
        for i in range(len(path)):
            step = path[i]
            desc = step.get('description', '').lower()

            # This step opens a dropdown
            if 'dropdown' in desc and i < len(path) - 1:
                # Next step is the dropdown item
                dropdown_pairs.append((i, i + 1))

        # Go back to dashboard
        self.driver.get(self.start_url)
        dismiss_all_popups_and_overlays(self.driver)
        wait_dom_ready(self.driver)
        time.sleep(1)

        # ALWAYS keep the first step (e.g., 'Performance')
        first_step = path[0]

        # Click the first step
        element = self._find_element_by_selector_or_text(
            first_step.get('selector', ''),
            first_step.get('text', ''),
            timeout=5
        )

        if not element or not safe_click(self.driver, element):
            # If first step fails, return original path
            return path

        wait_dom_ready(self.driver)
        time.sleep(0.5)

        # Now optimize the remaining steps (skip first)
        remaining_path = path[1:]
        shortest = [first_step]  # Start with first step
        clicked_up_to = -1  # Index in remaining_path
        target = len(remaining_path) - 1

        max_attempts = len(remaining_path) * 2
        attempts = 0

        while clicked_up_to < target and attempts < max_attempts:
            attempts += 1
            found = False

            # Try from target backwards
            for i in range(target, clicked_up_to, -1):
                # Check if this is a dropdown item that needs its opener
                needs_opener = False
                opener_idx = -1

                for pair in dropdown_pairs:
                    opener, item = pair
                    # Adjust indices (since we skipped first step)
                    opener -= 1
                    item -= 1

                    if i == item and opener > clicked_up_to:
                        # This is a dropdown item and we haven't clicked its opener yet
                        needs_opener = True
                        opener_idx = opener
                        break

                if needs_opener:
                    # Must click opener first
                    opener_step = remaining_path[opener_idx]
                    opener_elem = self._find_element_by_selector_or_text(
                        opener_step.get('selector', ''),
                        opener_step.get('text', ''),
                        timeout=5
                    )

                    if opener_elem and opener_elem.is_displayed():
                        try:
                            if safe_click(self.driver, opener_elem):
                                time.sleep(0.5)  # Wait for dropdown to open
                                shortest.append(opener_step)
                                clicked_up_to = opener_idx

                                # Now try clicking the dropdown item
                                item_step = remaining_path[i]
                                item_elem = self._find_element_by_selector_or_text(
                                    item_step.get('selector', ''),
                                    item_step.get('text', ''),
                                    timeout=5
                                )

                                if item_elem and item_elem.is_displayed():
                                    if safe_click(self.driver, item_elem):
                                        time.sleep(0.3)
                                        shortest.append(item_step)
                                        clicked_up_to = i
                                        found = True
                                        break
                        except:
                            continue
                else:
                    # Regular step - no dropdown dependency
                    step = remaining_path[i]
                    selector = step.get('selector', '')
                    text = step.get('text', '')

                    if not selector:
                        continue

                    element = self._find_element_by_selector_or_text(
                        selector,
                        text,
                        timeout=5
                    )

                    if element and element.is_displayed():
                        try:
                            if safe_click(self.driver, element):
                                time.sleep(0.3)
                                shortest.append(step)
                                clicked_up_to = i
                                found = True
                                break
                        except:
                            continue

            if not found:
                # Fallback to original path
                return path

        return shortest if clicked_up_to == target else path

    def _find_form_opening_buttons(self) -> List[Dict[str, Any]]:
        """Find buttons/links that open forms"""
        print(f"[DEBUG] 🔍 Starting _find_form_opening_buttons()")

        # ✅ NEW: Pre-identify ALL table containers once
        print("    [Performance] Pre-scanning for table containers...")
        table_containers = []

        try:
            table_containers.extend(self.driver.find_elements(By.TAG_NAME, "table"))
            table_containers.extend(self.driver.find_elements(By.CSS_SELECTOR, "[role='table']"))
            table_containers.extend(self.driver.find_elements(By.CSS_SELECTOR, "[role='grid']"))
            table_containers.extend(self.driver.find_elements(By.CSS_SELECTOR, ".oxd-table, [class$='table'], [class^='data-table']"))
            print(f"    [Performance] Found {len(table_containers)} table containers to skip")
        except:
            pass

        # Updated keywords - buttons that OPEN forms
        strict_form_keywords = self.strict_form_keywords
        plus_symbols = self.plus_symbols
        buttons = []
        seen = set()

        checked_count = 0
        skipped_count = 0
        matched_count = 0

        # Check multiple element types
        button_selectors = [
            "button",
            "a",
            "input[type='button']",
            "input[type='submit']",
            "[role='button']"
        ]

        for selector in button_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                print(f"[DEBUG]   Found {len(elements)} '{selector}' elements")

                for el in elements:
                    try:
                        checked_count += 1

                        if self._should_skip_element(el):
                            skipped_count += 1
                            continue

                        if not el.is_displayed():
                            skipped_count += 1
                            continue

                        # ✅ FAST: Check if element is inside any pre-identified table container
                        is_in_table = False
                        try:
                            for table in table_containers:
                                try:
                                    if self.driver.execute_script("return arguments[0].contains(arguments[1])",
                                                                  table, el):
                                        is_in_table = True
                                        break
                                except:
                                    continue
                        except:
                            pass

                        if is_in_table:
                            skipped_count += 1
                            continue  # Skip without logging

                        try:
                            direct_text = self.driver.execute_script("""
                                var element = arguments[0];
                                var text = '';
                                for (var i = 0; i < element.childNodes.length; i++) {
                                    var node = element.childNodes[i];
                                    if (node.nodeType === 3) {
                                        text += node.textContent;
                                    }
                                }
                                return text.trim();
                            """, el)
                        except:
                            direct_text = visible_text(el)

                        aria_label = el.get_attribute("aria-label") or ""
                        value_attr = el.get_attribute("value") or ""
                        text = (direct_text or aria_label or value_attr).strip()

                        if not text or len(text) < 1 or len(text) > 20 or '\n' in text:
                            continue

                        text_lower = text.lower()
                        is_form_button = False

                        print(f"[DEBUG]     Checking button text: '{text}' (lowercase: '{text_lower}')")

                        if text in plus_symbols:
                            is_form_button = True
                            print(f"[DEBUG]       ✅ Matched plus symbol!")

                        for keyword in strict_form_keywords:
                            if text_lower == keyword or text_lower.startswith(keyword + " "):
                                is_form_button = True
                                print(f"[DEBUG]       ✅ Matched keyword: '{keyword}'")
                                break

                        if is_form_button:
                            matched_count += 1
                            loc = el.location
                            key = (text, loc.get('x', 0), loc.get('y', 0))
                            if key not in seen:
                                seen.add(key)
                                print(f"    🎯 Found form button: '{text}'")
                                buttons.append({
                                    'element': el,
                                    'text': text,
                                    'selector': self._get_unique_selector(el),
                                    'tag': el.tag_name.lower()
                                })
                        else:
                            print(f"[DEBUG]       ❌ No match for: '{text}'")

                    except (StaleElementReferenceException, Exception) as e:
                        print(f"[DEBUG]     Error processing element: {e}")
                        continue
            except Exception as e:
                print(f"[DEBUG]   Error finding '{selector}' elements: {e}")
                continue

        print(f"[DEBUG] 🎯 Form button detection complete:")
        print(f"[DEBUG]   - Checked: {checked_count} elements")
        print(f"[DEBUG]   - Skipped: {skipped_count} elements")
        print(f"[DEBUG]   - Matched: {matched_count} form buttons")
        print(f"[DEBUG]   - Final: {len(buttons)} unique form buttons")

        buttons.sort(key=lambda b: b['element'].location.get('y', 0))
        return buttons

    def _find_all_clickables(self) -> List[Dict[str, Any]]:
        """Find ALL clickable elements"""
        clickables = []
        seen = set()

        # ✅ Step 1: Pre-identify ALL table containers
        print("    [Performance] Pre-scanning for table containers...")
        table_containers = []

        try:
            # Find HTML tables
            table_containers.extend(self.driver.find_elements(By.TAG_NAME, "table"))

            # Find ARIA role tables
            table_containers.extend(self.driver.find_elements(By.CSS_SELECTOR, "[role='table']"))
            table_containers.extend(self.driver.find_elements(By.CSS_SELECTOR, "[role='grid']"))

            # Find CSS class-based tables
            table_containers.extend(self.driver.find_elements(By.CSS_SELECTOR, ".oxd-table, [class$='table'], [class^='data-table']"))

            print(f"    [Performance] Found {len(table_containers)} table containers")

            # ✅ Step 2: Mark all descendants of tables with temporary attribute
            if table_containers:
                print("    [Performance] Marking table descendants...")
                for table in table_containers:
                    try:
                        self.driver.execute_script("""
                            var table = arguments[0];
                            var descendants = table.querySelectorAll('*');
                            descendants.forEach(function(el) {
                                el.setAttribute('data-inside-table', 'true');
                            });
                            table.setAttribute('data-inside-table', 'true');
                        """, table)
                    except:
                        pass
                print(f"    [Performance] ✅ Marked descendants of {len(table_containers)} tables")
        except:
            pass

        clickable_selectors = [
            "a:not([data-inside-table])",
            "button:not([data-inside-table])",
            "[onclick]:not([data-inside-table])",
            "[role='button']:not([data-inside-table])",
            "[role='tab']:not([data-inside-table])",
            "[role='menuitem']:not([data-inside-table])",
            "li:not([data-inside-table])",
            ".dropdown-toggle:not([data-inside-table])",
            ".tab:not([data-inside-table])",
            ".menu-item:not([data-inside-table])",
            "[class*='click']:not([data-inside-table'])",
            "[class*='button']:not([data-inside-table])",
            "[class*='link']:not([data-inside-table])",
            "[class*='nav']:not([data-inside-table])",
            "[class*='menu']:not([data-inside-table])",
            "[class*='tab']:not([data-inside-table])",
        ]

        for selector in clickable_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)

                for el in elements:
                    try:
                        if self._should_skip_element(el):
                            continue

                        if not el.is_displayed():
                            continue



                        text = visible_text(el).strip()

                        # NEW: Skip global navigation items (works for any web app)
                        if text and text.lower() in self.global_navigation_items:
                            continue

                        if text in ['1', '2', '3', '4', '5', '6', '7', '8', '9', '0',
                                    '«', '»', '‹', '›', '<', '>', 'next', 'prev', 'previous']:
                            continue



                        # Skip already-seen locators (by selector) - NEW STRICT CHECK
                        better_selector = self._get_unique_selector(el)
                        unique_key = f"{text}|{better_selector}"
                        if better_selector and unique_key in self.global_locators:
                            self.logger.info(
                                f"    [DEBUG] Skipping '{text[:40]}' - selector already seen: {better_selector}")
                            continue

                        if not text or len(text) > 100:
                            continue

                        if '\n' in text:
                            continue
                        
                        tag = el.tag_name.lower()
                        has_href = el.get_attribute("href")
                        has_onclick = el.get_attribute("onclick")
                        has_cursor = False
                        try:
                            cursor = el.value_of_css_property("cursor")
                            has_cursor = cursor in ["pointer", "hand"]
                        except:
                            pass
                        
                        is_clickable = (
                            tag in ["a", "button"] or 
                            has_href or 
                            has_onclick or 
                            has_cursor or
                            ("click" in (el.get_attribute("class") or "").lower())
                        )
                        
                        if is_clickable:
                            # Get where this element navigates to
                            try:
                                href = el.get_attribute("href") or ""
                                onclick = el.get_attribute("onclick") or ""

                                # Deduplicate by: text + where it goes (not just position)
                                key = (text.lower(), href, onclick)
                            except:
                                # Fallback to position
                                loc = el.location
                                key = (text.lower(), loc.get('x', 0), loc.get('y', 0))

                            if key not in seen:
                                seen.add(key)
                                print(f"    🔘 Found clickable: '{text[:40]}'")

                                # Get unique selector to avoid clicking duplicates
                                better_selector = self._get_unique_selector(el)

                                try:
                                    location = el.location
                                    pos_y = location.get('y', 0)
                                    pos_x = location.get('x', 0)
                                except:
                                    pos_y = 0
                                    pos_x = 0

                                if 'soumya' in text.lower():
                                    print(
                                        f"    [DEBUG] 🔍 Found 'soumya vande': tag={el.tag_name}, visible={el.is_displayed()}, selector={better_selector}")

                                clickables.append({
                                    'element': el,
                                    'text': text,
                                    'selector': better_selector,
                                    'tag': tag,
                                    'id': f"{tag}_{text[:20]}_{len(clickables)}",
                                    'pos_y': pos_y,
                                    'pos_x': pos_x
                                })
                    
                    except (StaleElementReferenceException, Exception):
                        continue
            
            except Exception:
                continue

        clickables.sort(key=lambda c: (c.get('pos_y', 0), c.get('pos_x', 0)))

        # ✅ Step 4: Clean up - remove temporary attributes
        if table_containers:
            try:
                print("    [Performance] Cleaning up table marks...")
                self.driver.execute_script("""
                            var marked = document.querySelectorAll('[data-inside-table]');
                            marked.forEach(function(el) {
                                el.removeAttribute('data-inside-table');
                            });
                        """)
            except:
                pass

        filtered_clickables = []
        for clickable in clickables:
            selector = clickable.get('selector', '')
            text = clickable.get('text', '')

            # Check if this element is a parent/child of something already in filtered list
            is_duplicate = False
            for i, existing in enumerate(filtered_clickables):
                existing_selector = existing.get('selector', '')
                existing_text = existing.get('text', '')

                # Only check if text matches
                if text == existing_text:
                    # If new selector is child of existing (more specific), replace existing with new
                    if selector.startswith(existing_selector + '/'):
                        filtered_clickables.pop(i)
                        break  # Will add the new (more specific) one below
                    # If new selector is parent of existing (less specific), skip new
                    if existing_selector.startswith(selector + '/'):
                        is_duplicate = True
                        break

            if not is_duplicate:
                filtered_clickables.append(clickable)

        clickables = filtered_clickables

        return clickables[:50]

    def _find_element_by_selector_or_text(self, selector: str, text: str, timeout: int = None):
        """Find element with explicit wait"""
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        if timeout is None:
            timeout = self.element_wait_timeout  # Use default (5 or 15 seconds)

        try:
            if selector:
                if selector.startswith("xpath:") or selector.startswith("xpath="):
                    xpath = selector.replace("xpath:", "").replace("xpath=", "")
                    try:
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((By.XPATH, xpath))
                        )
                        if not self._should_skip_element(element):
                            return element
                    except:
                        pass
                else:
                    try:
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        if not self._should_skip_element(element):
                            return element
                    except:
                        pass
        except Exception:
            pass

        # Fallback to text search with wait
        if text:
            try:
                xpath = f"//*[contains(text(), '{text}')]"
                wait = WebDriverWait(self.driver, timeout)
                wait.until(EC.presence_of_element_located((By.XPATH, xpath)))

                elements = self.driver.find_elements(By.XPATH, xpath)
                for el in elements:
                    if el.is_displayed() and text in visible_text(el) and not self._should_skip_element(el):
                        return el
            except Exception:
                pass

        return None

    def _click_element(self, element, current_path: List[Dict] = None) -> bool:
        """Safely click"""
        success, _ = self._safe_click_with_protection(element, current_path)
        return success

    def _get_selector_for_element(self, el) -> str:
        """Get CSS selector"""
        try:
            _id = el.get_attribute("id")
            if _id:
                return f"#{_id}"
            
            classes = el.get_attribute("class")
            if classes:
                class_list = ".".join([c for c in classes.split() if c and len(c) < 30])
                if class_list:
                    return f"{el.tag_name}.{class_list}"
            
            return el.tag_name
        except Exception:
            return "div"

    def _get_unique_selector(self, el) -> str:
        """Get a unique selector using XPath position from DOM root"""
        try:
            # Always use full XPath from root for consistency
            # (Don't use IDs - they might not be unique across different pages)

            script = """
            function getXPath(element) {
                // Don't use ID - need full path for uniqueness
                if (element === document.body)
                    return '/html/body';

                var ix = 0;
                var siblings = element.parentNode.childNodes;
                for (var i = 0; i < siblings.length; i++) {
                    var sibling = siblings[i];
                    if (sibling === element)
                        return getXPath(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                        ix++;
                }
            }
            return getXPath(arguments[0]).toLowerCase();
            """

            xpath = self.driver.execute_script(script, el)
            return f"xpath={xpath}"

        except Exception:
            return self._get_selector_for_element(el)

    def _get_css_preferred_selector(self, el) -> str:
        """
        Get selector for JSON storage, preferring CSS over XPath.
        Used during path verification/fixing stage.
        """
        try:
            # Try ID first (best CSS selector)
            _id = el.get_attribute("id")
            if _id:
                return f"#{_id}"

            # Try data attributes
            for attr in ['data-test', 'data-testid', 'data-automation-id', 'name']:
                attr_value = el.get_attribute(attr)
                if attr_value:
                    return f"[{attr}='{attr_value}']"

            # Try class combinations (CSS)
            classes = el.get_attribute("class")
            if classes:
                class_list = classes.split()
                unique_classes = [c for c in class_list if c and len(c) < 30][:3]
                if unique_classes:
                    selector = f"{el.tag_name}.{'.'.join(unique_classes)}"
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                        if len(elements) == 1:
                            return selector
                    except:
                        pass

            # Fallback: XPath with "xpath:" prefix
            script = """
            function getXPath(element) {
                if (element.id !== '')
                    return 'id("' + element.id + '")';
                if (element === document.body)
                    return element.tagName;

                var ix = 0;
                var siblings = element.parentNode.childNodes;
                for (var i = 0; i < siblings.length; i++) {
                    var sibling = siblings[i];
                    if (sibling === element)
                        return getXPath(element.parentNode) + '/' + element.tagName + '[' + (ix + 1) + ']';
                    if (sibling.nodeType === 1 && sibling.tagName === element.tagName)
                        ix++;
                }
            }
            return getXPath(arguments[0]).toLowerCase();
            """
            xpath = self.driver.execute_script(script, el)
            return f"xpath:{xpath}"

        except Exception:
            return self._get_selector_for_element(el)

    def _convert_path_to_steps(self, path: List[Dict]) -> List[Dict[str, Any]]:
        """Convert path to steps with CSS selectors for JSON"""
        # Find shortest path
        shortest = self._find_shortest_path(path)

        steps = []
        for step in shortest:
            selector = step.get('selector', '')
            text = step.get('text', '')

            # Convert XPath to CSS by re-finding element
            if selector and (selector.startswith('xpath:') or selector.startswith('xpath=')):
                try:
                    element = self._find_element_by_selector_or_text(selector, text, timeout=3)
                    if element:
                        css_selector = self._get_css_preferred_selector(element)
                        # Only use CSS if conversion succeeded (doesn't start with xpath:)
                        if not css_selector.startswith('xpath:'):
                            selector = css_selector
                except:
                    pass  # Keep original XPath if conversion fails

            steps.append({
                "action": step.get('action', 'click'),
                "selector": selector,
                "locator_text": text,
                "description": step.get('description', '')
            })


        return steps

    def _verify_form_path(self, form: Dict) -> Tuple[bool, int]:
        """
        Verify that the saved navigation path actually works.
        Returns (success, failed_step_index)
        """
        print(f"  🔍 Verifying path to: {form['form_name']}")

        # Go to dashboard
        self.driver.get(self.start_url)
        dismiss_all_popups_and_overlays(self.driver)
        wait_dom_ready(self.driver)
        time.sleep(1)

        steps = form.get('navigation_steps', [])

        for idx, step in enumerate(steps):
            if step.get('action') == 'wait_for_load':
                continue

            selector = step.get('selector', '')
            text = step.get('locator_text', '')

            element = self._find_element_by_selector_or_text(selector, text)

            if not element:
                print(f"    ❌ Step {idx + 1} failed: Cannot find '{text}'")
                return False, idx

            if not safe_click(self.driver, element):
                print(f"    ❌ Step {idx + 1} failed: Click failed on '{text}'")
                return False, idx

            time.sleep(0.8)
            wait_dom_ready(self.driver)

        # Check if we reached the correct URL
        current_url = self.driver.current_url
        expected_url = form.get('form_url', '')

        if current_url == expected_url:
            print(f"    ✅ Path verified successfully!")
            return True, None
        else:
            print(f"    ❌ Wrong destination: {current_url}")
            return False, len(steps) - 1

    def _fix_failing_step(self, form: Dict, failed_step_index: int) -> bool:
        """
        Try to fix a failing step by finding a better selector.
        """
        print(f"  🔧 Fixing step {failed_step_index + 1}...")

        # Navigate to the step before the failing one
        self.driver.get(self.start_url)
        dismiss_all_popups_and_overlays(self.driver)
        wait_dom_ready(self.driver)
        time.sleep(1)

        steps = form.get('navigation_steps', [])

        # Navigate to the step before the failing one
        for idx in range(failed_step_index):
            step = steps[idx]
            if step.get('action') == 'wait_for_load':
                continue

            selector = step.get('selector', '')
            text = step.get('locator_text', '')
            element = self._find_element_by_selector_or_text(selector, text)

            if element:
                safe_click(self.driver, element)
                time.sleep(0.8)
                wait_dom_ready(self.driver)

        # Now try to find a better selector for the failing step
        failing_step = steps[failed_step_index]
        text = failing_step.get('locator_text', '')

        # Try to find element by text
        element = self._find_element_by_selector_or_text('', text)

        if element:
            # Get a better selector
            new_selector = self._get_css_preferred_selector(element)
            print(f"    ✅ Found new selector: {new_selector}")

            # Update the step
            failing_step['selector'] = new_selector
            return True
        else:
            print(f"    ❌ Cannot find element with text: '{text}'")
            return False

    def _verify_and_fix_form(self, form: dict, max_attempts: int = 3) -> bool:
        """Verify and fix navigation path to form"""
        form_name = form["form_name"]
        steps = form["navigation_steps"]

        for attempt in range(1, max_attempts + 1):
            print(f"  🔄 Verification attempt {attempt}/{max_attempts}")
            print(f"  🔍 Verifying path to: {form_name}")

            try:
                self.driver.get(self.start_url)
                dismiss_all_popups_and_overlays(self.driver)
                wait_dom_ready(self.driver)
                time.sleep(0.5)

                failed_step = None

                # Navigate through each step
                for i, step in enumerate(steps, 1):

                    # Skip wait_for_load actions
                    if step.get('action') == 'wait_for_load':
                        continue

                    step_text = step.get("locator_text", "")
                    is_form_button = step.get("is_form_button", False)

                    if is_form_button:
                        # This is the form-opening button (like "Add")
                        print(f"    Step {i}/{len(steps)}: Looking for form button '{step_text}'")

                        # Try to find the button on the current page
                        buttons = self.driver.find_elements(By.CSS_SELECTOR, "button, a, input[type='button']")
                        found = False

                        for btn in buttons:
                            if btn.is_displayed() and btn.text.strip().lower() == step_text.lower():
                                if safe_click(self.driver, btn):
                                    print(f"    ✅ Found and clicked form button '{step_text}'")
                                    wait_dom_ready(self.driver)
                                    time.sleep(0.5)
                                    found = True
                                    break

                        if not found:
                            print(f"    ❌ Step {i} failed: Cannot find form button '{step_text}'")
                            failed_step = i
                            break

                    else:
                        # Regular navigation step
                        print(f"    Step {i}/{len(steps)}: Looking for '{step_text}'")

                        element = self._find_element_by_selector_or_text(
                            step.get("selector", ""),
                            step_text
                        )

                        if not element:
                            print(f"    ❌ Step {i} failed: Cannot find '{step_text}'")
                            failed_step = i
                            break

                        print(f"    ✅ Step {i}: Found '{step_text}', attempting click")

                        if not safe_click(self.driver, element):
                            print(f"    ❌ Step {i} failed: Could not click '{step_text}'")
                            failed_step = i
                            break

                        print(f"    ✅ Step {i}: Clicked '{step_text}' successfully")
                        wait_dom_ready(self.driver)
                        time.sleep(0.3)

                if failed_step is None:
                    # All steps clicked - now verify we reached the form page
                    wait_dom_ready(self.driver)
                    time.sleep(0.5)

                    current_url = self.driver.current_url
                    expected_url = form.get("form_url", "")

                    if current_url == expected_url:
                        print(f"    ✅ Path verified successfully!")
                        print(f"    ✅ Reached form page: {current_url}")
                        return True
                    else:
                        print(f"    ❌ Wrong destination!")
                        print(f"    Expected: {expected_url}")
                        print(f"    Got: {current_url}")
                        # Check if URLs match ignoring trailing slash
                        if current_url.rstrip('/') == expected_url.rstrip('/'):
                            print(f"    ✅ URLs match (ignoring trailing slash)")
                            return True
                        failed_step = len(steps) - 1
                        # Fall through to retry logic

                # Try to fix the failed step
                if attempt < max_attempts:
                    print(f"  🔧 Fixing step {failed_step}...")

                    if self._fix_failing_step(form, failed_step):
                        print(f"  ✅ Step {failed_step} fixed successfully")
                        # Save the updated form
                        self._update_form_json(form)
                        continue
                    else:
                        print(f"  ❌ Cannot fix step {failed_step}")

            except Exception as e:
                print(f"  ❌ Verification error: {e}")

        print(f"  ⚠️  Verification failed after {max_attempts} attempts")
        return False

    def _update_form_json(self, form: Dict):
        """Update the JSON files with the corrected navigation path"""
        form_name = form["form_name"]
        form_slug = sanitize_filename(form_name)

        from pathlib import Path
        project_base = get_project_base_dir(self.project_name)
        form_folder = project_base / form_slug

        # Update main_setup.json
        main_setup_path = form_folder / f"{form_slug}_main_setup.json"

        if main_setup_path.exists():
            with open(main_setup_path, "r", encoding="utf-8") as f:
                main_setup = json.load(f)

            # Rebuild gui_pre_create_actions with updated steps
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

            main_setup['gui_pre_create_actions'] = gui_pre_create_actions

            # Update system_values with modal info
            if 'system_values' not in main_setup:
                main_setup['system_values'] = []

            # Remove old modal entries if they exist
            main_setup['system_values'] = [sv for sv in main_setup['system_values']
                                           if sv.get('name') not in ['is_modal', 'modal_trigger']]

            # Add new modal entries
            main_setup['system_values'].extend([
                {"name": "is_modal", "value": is_modal},
                {"name": "modal_trigger", "value": modal_trigger}
            ])

            with open(main_setup_path, "w", encoding="utf-8") as f:
                json.dump(main_setup, f, indent=2)

            print(f"    ✅ Updated: {main_setup_path.name}")

    def _build_hierarchy(self, forms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build parent-child relationships from form_relationships.json"""

        relationships_path = self.project_base / "form_relationships.json"

        if not relationships_path.exists():
            print("⚠️  No form_relationships.json found!")
            return {}

        print("\n" + "=" * 70)
        print("🔗 BUILDING PARENT-CHILD RELATIONSHIPS")
        print("=" * 70)

        # Load the JSON (already has ID fields from discovery)
        with open(relationships_path, "r", encoding="utf-8") as f:
            hierarchy = json.load(f)

        print(f"Analyzing {hierarchy['total_forms']} forms...\n")

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

        print(f"\n✅ Found {relationships_found} parent-child relationships")
        print(f"✅ Updated: {relationships_path}")
        print("=" * 70 + "\n")

        return hierarchy

    def crawl(self):
        """Main crawl"""
        # ✅ PRINT AI BUDGET/COST INFO AT START
        if self.use_ai and self.ai_helper:
            print("\n" + "=" * 70)
            print("💰 AI BUDGET INFO")
            print("=" * 70)
            self.ai_helper.print_cost_summary()
            print("=" * 70 + "\n")

        all_forms = self._gather_all_form_pages()

        if not all_forms:
            print("\n" + "="*70)
            print("⚠️  NO MATCHING FORMS FOUND")
            print("="*70)
            if self.target_form_pages:
                print(f"Target filters: {self.target_form_pages}")
                print("Suggestion: Set target_form_pages=[] to discover ALL forms")
            print("="*70 + "\n")
            return

        # Build hierarchy to establish parent-child relationships
        hierarchy = self._build_hierarchy(all_forms)
        ordered_names = hierarchy.get("ordered_forms") or [f["form_name"] for f in all_forms]

        # ✅ FIX: In discovery_only mode, all work is done - exit early!
        if self.discovery_only:
            print("\n" + "=" * 70)
            print("✅ COMPLETE!")
            print("=" * 70)
            print(f"Created folders and JSONs for {len(all_forms)} forms")
            print(f"Forms: {ordered_names}")
            print("Next step: Run with discovery_only=False for field exploration")
            print("=" * 70 + "\n")

            if self.use_ai and self.ai_helper:
                self.ai_helper.print_cost_summary()

            return  # ← EXIT - Don't run the loop again!

        # ✅ Full exploration mode - process each form
        name_to_form = {f["form_name"]: f for f in all_forms}

        print("\n" + "=" * 70)
        print(f"🚀 STARTING FULL EXPLORATION FOR {len(ordered_names)} FORMS")
        print("=" * 70)
        print(f"Forms: {ordered_names}")
        print("=" * 70 + "\n")

        for idx, name in enumerate(ordered_names, 1):
            f = name_to_form.get(name)
            if not f:
                continue

            print(f"\n{'=' * 70}")
            print(f"📋 FORM {idx}/{len(ordered_names)}: {name}")
            print(f"{'=' * 70}\n")

            # Full exploration (only runs when discovery_only=False)
            # NOTE: FormRoutesExplorer removed - not needed for discovery
            print(f"  ⚠️ Full exploration not implemented (FormRoutesExplorer removed)")
            
            # OLD CODE - FormRoutesExplorer usage (commented out):
            # explorer = FormRoutesExplorer(
            #     self.driver,
            #     form_name=f["form_name"],
            #     start_url=f["form_url"],
            #     base_url=self.base_url,
            #     project_name=self.project_name,
            #     ai_helper=self.ai_helper if self.use_ai else None
            # )
            #
            # for step in f.get("navigation_steps", []):
            #     action_entry = {
            #         "update_type": "",
            #         "update_ai_stages": [step],
            #         "action_description": step.get("action", ""),
            #         "update_css": "",
            #         "update_css_playwright": "",
            #         "webdriver_sleep_before_action": "",
            #         "playwright_sleep_before_action": "",
            #         "non_editable_condition": {"operator": "or"},
            #         "validate_non_editable": False
            #     }
            #     explorer.gui_pre_create_actions.append(action_entry)
            #
            # self.driver.get(f["form_url"])
            # wait_dom_ready(self.driver)
            # explorer.explore_and_save_all_routes()
            #
            # self.driver.get(self.base_url)
            # wait_dom_ready(self.driver)

        # End of full exploration
        print("\n" + "=" * 70)
        print("✅ COMPLETE!")
        print("=" * 70)
        print(f"Fully explored {len(all_forms)} forms")
        print("=" * 70 + "\n")

        if self.use_ai and self.ai_helper:
            self.ai_helper.print_cost_summary()

    def _create_minimal_json_for_form(self, form: Dict[str, Any]):
        """Create folder and JSONs - calls server to do it"""
        if self.server:
            self.server.create_form_folder(self.project_name, form)
        else:
            print("  ⚠️  No server - cannot create folder")
        
        # Verify and fix the path
        print(f"\n  🔍 Verifying navigation path...")
        self._verify_and_fix_form(form)


    def close_logger(self):
        """Clean up logger at end of crawl"""
        if hasattr(self, 'log'):
            self.log.kill_logger()