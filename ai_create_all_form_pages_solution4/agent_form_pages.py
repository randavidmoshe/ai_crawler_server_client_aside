# agent_form_pages.py
# Agent-side code - Runs on customer desktop with Selenium
# Handles ALL Selenium/WebDriver operations
# Communicates with server for AI and file operations

import os
import json
import time
from typing import List, Tuple, Any, Dict, Set, Optional
from urllib.parse import urlparse

from selenium.webdriver.common.by import By
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import StaleElementReferenceException, NoSuchElementException
from selenium.webdriver.support.wait import WebDriverWait

from form_utils import (
    wait_dom_ready, safe_click, page_has_form_fields, sanitize_filename, visible_text,
    dismiss_all_popups_and_overlays,
)

import logging


class RecursiveNavigationState:
    """Tracks navigation state during recursive exploration"""
    def __init__(self, url: str, path: List[Dict], depth: int):
        self.url = url
        self.path = path
        self.depth = depth


class AgentFormPages:
    """
    Agent running on customer desktop - handles all Selenium operations.
    Calls back to server for AI analysis and file operations.
    """
    
    def __init__(
        self,
        driver,
        start_url: str,
        base_url: str,
        server,  # Reference to server object for callbacks
        project_name: str = "default_project",
        max_pages: int = 20,
        max_depth: int = 5,
        use_ai: bool = True,
        target_form_pages: List[str] = None,
        discovery_only: bool = False,
        slow_mode: bool = False
    ):
        self.driver = driver
        self.server = server  # Server callback reference

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
        
        # Track visited states (agent maintains these)
        self.visited_urls: Set[str] = set()
        self.visited_states: Set[str] = set()
        self.clicked_form_buttons: Set[str] = set()

        # Store global navigation items (captured at depth 0)
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
            "×", "✓", "✕", "close", "dismiss",
        ]
        
        self.base_domain = urlparse(self.start_url).netloc
        
        # Load existing form URLs from server
        self.existing_form_urls = self.server.get_existing_form_urls()
        
        print(f"[Agent] Project base: {project_name}")
        print(f"[Agent] Max forms: {self.max_pages}")
        print(f"[Agent] Max depth: {self.max_depth} levels")
        
        if self.discovery_only:
            print(f"[Agent] 🔍 MODE: DISCOVERY ONLY (Phase 1)")
            print(f"[Agent]    → Will find forms and create JSONs")
            print(f"[Agent]    → Will skip field exploration")
        else:
            print(f"[Agent] 🚀 MODE: FULL EXPLORATION (Phase 2)")
            print(f"[Agent]    → Will discover forms AND explore fields")
        
        if self.target_form_pages:
            print(f"[Agent] FILTERING: {self.target_form_pages}")
        else:
            print(f"[Agent] No filter - discovering ALL forms")

        # Configure timeout based on mode
        if slow_mode:
            self.element_wait_timeout = 15
            self.navigation_wait = 2.0
            print("[Agent] 🐢 SLOW MODE enabled - using 15 second timeouts")
        else:
            self.element_wait_timeout = 5
            self.navigation_wait = 0.5
            print("[Agent] 🐢 SLOW MODE disabled")

    def _check_dropdown_opened(self) -> bool:
        """Check if a dropdown/menu appeared using common patterns"""
        time.sleep(0.3)

        dropdown_selectors = [
            # Bootstrap
            ".dropdown-menu.show",
            ".dropdown-menu[style*='display: block']",
            ".dropdown-menu[style*='display:block']",
            
            # Material UI / Custom
            "[role='menu']",
            "[role='listbox']",
            "ul.menu",
            "ul.dropdown",
            ".menu-items",
            ".dropdown-content",
            
            # Visible and positioned
            "div[style*='position: absolute']",
            "div[style*='position:absolute']",
        ]

        for selector in dropdown_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        return True
            except:
                continue

        return False

    def _check_if_modal_opened(self) -> bool:
        """Check if a modal/dialog appeared using common patterns"""
        time.sleep(0.4)

        modal_selectors = [
            # Bootstrap
            ".modal.show", ".modal.fade.show",
            ".modal[style*='display: block']", ".modal[style*='display:block']",
            
            # General dialog
            "[role='dialog']", "[role='alertdialog']",
            ".dialog", ".popup", ".overlay",
            
            # Material UI
            ".MuiDialog-root", ".MuiModal-root",
            
            # Custom patterns
            "div[class*='modal']", "div[class*='dialog']", "div[class*='popup']",
        ]

        for selector in modal_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        return True
            except:
                continue

        return False

    def _close_modal(self) -> bool:
        """Attempt to close modal/dialog using common patterns"""
        close_selectors = [
            # Bootstrap close button
            ".modal .close", ".modal .btn-close",
            
            # Generic close buttons
            "button.close", "button[aria-label='Close']", "button[aria-label='close']",
            "[data-dismiss='modal']",
            
            # Icon-based close
            ".modal .fa-times", ".modal .fa-close",
            
            # Material UI
            ".MuiDialog-root button[aria-label='close']",
        ]

        for selector in close_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        if safe_click(self.driver, el):
                            time.sleep(0.3)
                            return True
            except:
                continue

        # Fallback: ESC key
        try:
            self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
            time.sleep(0.3)
            return True
        except:
            pass

        # Last resort: click backdrop
        try:
            overlays = self.driver.find_elements(By.CSS_SELECTOR,
                ".modal-backdrop, .overlay, [class*='backdrop']")
            for overlay in overlays:
                if overlay.is_displayed():
                    safe_click(self.driver, overlay)
                    time.sleep(0.3)
                    return True
        except:
            pass

        return False

    def _find_dropdown_items(self) -> List[Dict[str, Any]]:
        """Find items inside opened dropdown/menu"""
        dropdown_items = []

        item_selectors = [
            # Bootstrap
            ".dropdown-menu a.dropdown-item",
            ".dropdown-menu button.dropdown-item",
            
            # Generic
            "[role='menu'] [role='menuitem']",
            "[role='listbox'] [role='option']",
            "ul.dropdown li a", "ul.menu li a",
            
            # Material UI
            ".MuiMenu-list .MuiMenuItem-root",
        ]

        for selector in item_selectors:
            try:
                dropdowns = self.driver.find_elements(By.CSS_SELECTOR, selector)
                for dd in dropdowns:
                    if dd.is_displayed():
                        text = visible_text(dd)
                        if text:
                            dropdown_items.append({
                                'selector': self._get_unique_selector(dd),
                                'text': text,
                                'type': 'dropdown_item'
                            })
            except:
                continue

        return dropdown_items

    def _matches_target(self, form_name: str) -> bool:
        """Check if form_name matches any of the target filters"""
        if not self.target_form_pages:
            return True
        
        form_name_lower = form_name.lower()
        for target in self.target_form_pages:
            if target.lower() in form_name_lower:
                return True
        
        return False

    def _should_skip_element(self, element) -> bool:
        """Check if element should be skipped based on blacklist"""
        try:
            text = visible_text(element).strip().lower()
            if not text:
                return False
            
            for blacklist_term in self.button_blacklist:
                if blacklist_term in text:
                    return True
            
            return False
        except:
            return False

    def _is_constrained_field(self, element) -> bool:
        """Check if element is a constrained field (select, checkbox, radio)"""
        try:
            tag = element.tag_name.lower()
            if tag == 'select':
                return True
            
            if tag == 'input':
                input_type = element.get_attribute('type')
                if input_type in ['checkbox', 'radio']:
                    return True
            
            return False
        except:
            return False

    def _extract_id_fields_from_dom(self) -> List[str]:
        """
        Extract ID fields from current page by looking for:
        1. Labels containing 'ID' or 'Id' 
        2. Constrained fields (selects, checkboxes, radios) near those labels
        """
        id_fields = []

        try:
            labels = self.driver.find_elements(By.TAG_NAME, 'label')
            
            for label in labels:
                label_text = visible_text(label).strip()
                if not label_text:
                    continue
                
                if 'id' in label_text.lower() and len(label_text) < 50:
                    for_attr = label.get_attribute('for')
                    if for_attr:
                        try:
                            field = self.driver.find_element(By.ID, for_attr)
                            if self._is_constrained_field(field):
                                id_fields.append(label_text)
                        except:
                            pass
                    else:
                        try:
                            parent = label.find_element(By.XPATH, '..')
                            form_elements = parent.find_elements(By.CSS_SELECTOR,
                                'select, input[type="checkbox"], input[type="radio"]')
                            if form_elements:
                                id_fields.append(label_text)
                        except:
                            pass

        except Exception as e:
            print(f"  [Agent] Could not extract ID fields: {e}")

        return id_fields

    def _update_relationships_json(self, form_name: str, form_url: str, id_fields: List[str]):
        """Update form_relationships.json with ID fields - calls server"""
        # Server handles all file operations
        self.server.update_relationships_json(form_name, form_url, id_fields)

    def _manage_windows(self, current_path: List[Dict] = None) -> List[Dict[str, Any]]:
        """Handle new tabs/windows that might have opened"""
        new_tabs = []
        
        try:
            all_handles = self.driver.window_handles
            
            if len(all_handles) > 1:
                original_handle = self.driver.current_window_handle
                
                for handle in all_handles:
                    if handle != original_handle:
                        try:
                            self.driver.switch_to.window(handle)
                            time.sleep(0.5)
                            wait_dom_ready(self.driver)
                            tab_url = self.driver.current_url
                            
                            if urlparse(tab_url).netloc == self.base_domain:
                                if page_has_form_fields(self.driver, self._is_submission_button_ai):
                                    new_tabs.append({
                                        'url': tab_url,
                                        'path': current_path if current_path else []
                                    })
                                else:
                                    self.driver.close()
                            else:
                                self.driver.close()
                        except:
                            try:
                                self.driver.close()
                            except:
                                pass
                
                self.driver.switch_to.window(original_handle)
        
        except Exception as e:
            try:
                self.driver.switch_to.window(self.main_window_handle)
            except:
                pass
        
        return new_tabs

    def _safe_click_with_protection(self, element, current_path: List[Dict] = None) -> Tuple[bool, List[Dict[str, Any]]]:
        """Click with window/tab protection"""
        new_tabs = []
        
        current_windows = len(self.driver.window_handles)
        
        if not safe_click(self.driver, element):
            return False, []
        
        wait_dom_ready(self.driver)
        time.sleep(self.navigation_wait)
        
        new_windows = len(self.driver.window_handles)
        
        if new_windows > current_windows:
            new_tabs = self._manage_windows(current_path)
        
        new_url = self.driver.current_url
        
        if new_url != self.driver.current_url:
            self.driver.back()
            wait_dom_ready(self.driver)
            return False, []
        
        return True, new_tabs

    def _gather_all_form_pages(self) -> List[Dict[str, Any]]:
        """
        Main recursive crawler - discovers all form pages.
        Moved from crawler AS-IS, calls to AI go through self.server
        """
        print("\n" + "="*70)
        print("🔍 PHASE 1: DISCOVERING ALL FORM PAGES")
        print("="*70)
        
        self.driver.get(self.start_url)
        dismiss_all_popups_and_overlays(self.driver)
        wait_dom_ready(self.driver)
        time.sleep(1)
        
        self.main_window_handle = self.driver.current_window_handle
        
        initial_state = RecursiveNavigationState(
            url=self.driver.current_url,
            path=[],
            depth=0
        )
        
        stack = [initial_state]
        
        while stack and len(self.master) < self.max_pages:
            current_state = stack.pop()
            
            if current_state.depth > self.max_depth:
                continue
            
            state_key = self._get_state_key(current_state)
            if state_key in self.visited_states:
                continue
            
            self.visited_states.add(state_key)
            
            print(f"\n{'  ' * current_state.depth}📍 Depth {current_state.depth}: {current_state.url[:80]}")
            
            if not self._navigate_to_state(current_state):
                print(f"{'  ' * current_state.depth}  ❌ Navigation failed")
                continue
            
            if current_state.depth == 0:
                print(f"  🌐 At dashboard - capturing global navigation")
                global_buttons = self._find_form_opening_buttons()
                for btn in global_buttons:
                    self.global_navigation_items.add(btn['text'])
                    self.global_locators.add(btn['selector'])
            
            current_url = self.driver.current_url
            
            if current_url in self.visited_urls:
                print(f"{'  ' * current_state.depth}  ⏭️  Already visited this URL")
                continue
            
            self.visited_urls.add(current_url)
            
            if page_has_form_fields(self.driver, self._is_submission_button_ai):
                print(f"{'  ' * current_state.depth}  ✅ FORM PAGE FOUND!")
                
                # Extract form name using AI (server-side)
                button_text = current_state.path[-1]['text'] if current_state.path else ""
                form_name = self.server.extract_form_name_with_ai(current_url, button_text)
                
                if not self._matches_target(form_name):
                    print(f"{'  ' * current_state.depth}  ⏭️  Skipping '{form_name}' (doesn't match target filters)")
                    continue
                
                # Check if already exists
                url_base = current_url.split('#')[0].split('?')[0]
                if url_base in self.existing_form_urls:
                    print(f"{'  ' * current_state.depth}  ⏭️  Skipping '{form_name}' (already exists in form_relationships.json)")
                    continue
                
                is_modal = "#modal" in current_url.lower() or "modal" in current_url.lower()
                modal_trigger = button_text if is_modal else ""
                
                id_fields = self._extract_id_fields_from_dom()
                if id_fields:
                    print(f"{'  ' * current_state.depth}    🔑 ID Fields: {id_fields}")
                
                path_steps = self._convert_path_to_steps(current_state.path)
                
                form_entry = {
                    'form_name': form_name,
                    'form_url': current_url,
                    'navigation_steps': path_steps,
                    'depth': current_state.depth,
                    'id_fields': id_fields,
                    'is_modal': is_modal,
                    'modal_trigger': modal_trigger
                }
                
                self.master.append(form_entry)
                
                self._update_relationships_json(form_name, current_url, id_fields)
                
                # Server creates minimal JSON
                self.server.create_minimal_json_for_form(form_entry)
                
                print(f"{'  ' * current_state.depth}    📝 Saved: {form_name}")
                print(f"{'  ' * current_state.depth}    📊 Progress: {len(self.master)}/{self.max_pages} forms")
                
                if len(self.master) >= self.max_pages:
                    print(f"\n✅ Reached max forms limit ({self.max_pages})")
                    break
            
            buttons = self._find_form_opening_buttons()
            
            for btn in reversed(buttons):
                btn_text = btn['text']
                btn_selector = btn['selector']
                
                if btn_text in self.clicked_form_buttons:
                    continue
                
                new_path = current_state.path + [btn]
                new_depth = current_state.depth + 1
                
                new_state = RecursiveNavigationState(
                    url=current_url,
                    path=new_path,
                    depth=new_depth
                )
                
                stack.append(new_state)
        
        print("\n" + "="*70)
        print(f"✅ DISCOVERY COMPLETE - Found {len(self.master)} forms")
        print("="*70 + "\n")
        
        return self.master

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

    def _extract_form_name_with_ai(self, url: str, button_text: str = "") -> str:
        """
        Extract form name using AI - delegates to server
        """
        # AI processing happens on server side
        return self.server.extract_form_name_with_ai(url, button_text)

    def _is_submission_button_ai(self, button_text: str) -> bool:
        """
        Check if button is a submission button using AI - delegates to server
        """
        # AI processing happens on server side
        return self.server.is_submission_button_ai(button_text)

    def _wait_for_page_stable(self, timeout: float = None):
        """Wait for page to stabilize"""
        if timeout is None:
            timeout = self.element_wait_timeout
        
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script('return document.readyState') == 'complete'
            )
            time.sleep(0.3)
        except:
            pass

    def _save_forms_list(self, forms: List[Dict[str, Any]]):
        """Save forms list - delegates to server"""
        self.server.save_forms_list(forms)

    def _is_likely_user_dropdown(self, clickable: Dict) -> bool:
        """Check if element is likely a user dropdown"""
        text = clickable.get('text', '').lower()
        
        user_indicators = [
            'user', 'account', 'profile',
            'settings', 'my ',
            '@', '.com'
        ]
        
        for indicator in user_indicators:
            if indicator in text:
                return True
        
        selector = clickable.get('selector', '').lower()
        if any(x in selector for x in ['user', 'profile', 'account']):
            return True
        
        return False

    def _get_state_key(self, state: RecursiveNavigationState) -> str:
        """Generate unique key for navigation state"""
        path_str = '->'.join([step.get('text', '') for step in state.path])
        return f"{state.url}||{path_str}"

    def _navigate_to_state(self, state: RecursiveNavigationState) -> bool:
        """
        Navigate to a specific state by following its path.
        Returns True if successful, False otherwise.
        """
        if not state.path:
            self.driver.get(self.start_url)
            dismiss_all_popups_and_overlays(self.driver)
            wait_dom_ready(self.driver)
            time.sleep(0.5)
            return True
        
        self.driver.get(self.start_url)
        dismiss_all_popups_and_overlays(self.driver)
        wait_dom_ready(self.driver)
        time.sleep(0.5)
        
        optimized_path = self._find_shortest_path(state.path)
        
        for step in optimized_path:
            selector = step.get('selector', '')
            text = step.get('text', '')
            
            element = self._find_element_by_selector_or_text(selector, text)
            
            if not element:
                return False
            
            if not safe_click(self.driver, element):
                return False
            
            time.sleep(self.navigation_wait)
            wait_dom_ready(self.driver)
            
            if self._check_if_modal_opened():
                time.sleep(0.3)
            
            if self._check_dropdown_opened():
                time.sleep(0.3)
        
        return True

    def _find_shortest_path(self, path: List[dict]) -> List[dict]:
        """
        Optimize navigation path by trying to skip intermediate steps.
        Returns shortest working path.
        """
        if len(path) <= 1:
            return path
        
        for start_idx in range(len(path)):
            test_path = path[start_idx:]
            
            if len(test_path) == len(path):
                continue
            
            self.driver.get(self.start_url)
            dismiss_all_popups_and_overlays(self.driver)
            wait_dom_ready(self.driver)
            time.sleep(0.3)
            
            success = True
            for step in test_path:
                selector = step.get('selector', '')
                text = step.get('text', '')
                
                element = self._find_element_by_selector_or_text(selector, text, timeout=2)
                
                if not element:
                    success = False
                    break
                
                if not safe_click(self.driver, element):
                    success = False
                    break
                
                time.sleep(0.3)
                wait_dom_ready(self.driver)
            
            if success:
                return test_path
        
        return path

    def _find_form_opening_buttons(self) -> List[Dict[str, Any]]:
        """
        Find buttons that likely open forms.
        Uses AI if enabled, otherwise uses keywords.
        """
        if self.use_ai:
            # AI analysis happens on server
            page_html = self.driver.page_source
            page_url = self.driver.current_url
            candidates = self.server.find_form_page_candidates(page_html, page_url)
            
            result = []
            for candidate in candidates:
                selector = candidate.get('selector', '')
                text = candidate.get('text', '')
                
                element = self._find_element_by_selector_or_text(selector, text)
                if element and element.is_displayed():
                    result.append({
                        'selector': self._get_unique_selector(element),
                        'text': text,
                        'confidence': candidate.get('confidence', 'medium')
                    })
            
            return result
        else:
            # Keyword-based fallback
            return self._find_all_clickables()

    def _find_all_clickables(self) -> List[Dict[str, Any]]:
        """Find all clickable elements using keyword matching"""
        clickables = []
        
        button_selectors = [
            'button',
            'a',
            '[role="button"]',
            'input[type="button"]',
            'input[type="submit"]',
            '.btn',
            '[class*="button"]',
        ]
        
        for selector in button_selectors:
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                
                for el in elements:
                    if not el.is_displayed():
                        continue
                    
                    text = visible_text(el).strip()
                    if not text:
                        continue
                    
                    if self._should_skip_element(el):
                        continue
                    
                    text_lower = text.lower()
                    
                    matched = False
                    for keyword in self.strict_form_keywords:
                        if keyword in text_lower:
                            matched = True
                            break
                    
                    if not matched:
                        for symbol in self.plus_symbols:
                            if symbol in text:
                                matched = True
                                break
                    
                    if matched:
                        clickables.append({
                            'selector': self._get_unique_selector(el),
                            'text': text,
                            'type': 'button'
                        })
                        
            except Exception as e:
                continue
        
        return clickables

    def _find_element_by_selector_or_text(self, selector: str, text: str, timeout: int = None):
        """Find element by CSS selector or visible text"""
        if timeout is None:
            timeout = self.element_wait_timeout
        
        try:
            if selector:
                try:
                    element = WebDriverWait(self.driver, timeout).until(
                        lambda d: d.find_element(By.CSS_SELECTOR, selector)
                    )
                    if element and element.is_displayed():
                        return element
                except:
                    pass
            
            if text:
                try:
                    all_elements = self.driver.find_elements(By.XPATH, "//*")
                    for el in all_elements:
                        try:
                            if el.is_displayed() and visible_text(el).strip() == text:
                                return el
                        except:
                            continue
                except:
                    pass
            
            return None
            
        except Exception as e:
            return None

    def _get_selector_for_element(self, el) -> str:
        """Get CSS selector for element"""
        try:
            if el.get_attribute('id'):
                return f"#{el.get_attribute('id')}"
            
            return self._get_unique_selector(el)
        except:
            return ""

    def _get_unique_selector(self, el) -> str:
        """Generate unique CSS selector"""
        try:
            script = """
            function getSelector(el) {
                if (el.id) return '#' + el.id;
                if (el === document.body) return 'body';
                
                let path = [];
                while (el && el.nodeType === Node.ELEMENT_NODE) {
                    let selector = el.nodeName.toLowerCase();
                    if (el.className) {
                        selector += '.' + el.className.trim().split(/\\s+/).join('.');
                    }
                    path.unshift(selector);
                    el = el.parentNode;
                }
                return path.join(' > ');
            }
            return getSelector(arguments[0]);
            """
            return self.driver.execute_script(script, el)
        except:
            return el.tag_name

    def _get_css_preferred_selector(self, el) -> str:
        """Get best CSS selector for element"""
        try:
            if el.get_attribute('id'):
                return f"#{el.get_attribute('id')}"
            
            if el.get_attribute('name'):
                tag = el.tag_name.lower()
                name = el.get_attribute('name')
                return f"{tag}[name='{name}']"
            
            classes = el.get_attribute('class')
            if classes:
                class_list = classes.strip().split()
                if len(class_list) > 0:
                    tag = el.tag_name.lower()
                    return f"{tag}.{'.'.join(class_list[:3])}"
            
            return self._get_unique_selector(el)
        except:
            return ""

    def _convert_path_to_steps(self, path: List[Dict]) -> List[Dict[str, Any]]:
        """Convert navigation path to AI stages format"""
        steps = []
        
        for idx, item in enumerate(path):
            step = {
                'action': 'click',
                'selector': item.get('selector', ''),
                'locator_text': item.get('text', ''),
                'description': f"Click '{item.get('text', '')}'"
            }
            steps.append(step)
        
        return steps

    def _fix_failing_step(self, form: Dict, failed_step_index: int) -> bool:
        """
        Try to fix a failing navigation step by finding alternative selectors.
        Returns True if fix was successful, False otherwise.
        """
        print(f"    🔧 Attempting to fix step {failed_step_index + 1}...")
        
        steps = form.get('navigation_steps', [])
        if failed_step_index >= len(steps):
            return False
        
        failing_step = steps[failed_step_index]
        original_text = failing_step.get('locator_text', '')
        
        self.driver.get(self.start_url)
        dismiss_all_popups_and_overlays(self.driver)
        wait_dom_ready(self.driver)
        time.sleep(1)
        
        for i in range(failed_step_index):
            step = steps[i]
            element = self._find_element_by_selector_or_text(
                step.get('selector', ''),
                step.get('locator_text', '')
            )
            
            if not element or not safe_click(self.driver, element):
                return False
            
            time.sleep(0.8)
            wait_dom_ready(self.driver)
        
        all_elements = self.driver.find_elements(By.XPATH, "//*")
        for el in all_elements:
            try:
                if el.is_displayed() and visible_text(el).strip() == original_text:
                    new_selector = self._get_unique_selector(el)
                    print(f"    ✅ Found new selector: {new_selector}")
                    
                    failing_step['selector'] = new_selector
                    
                    return True
            except:
                continue
        
        print(f"    ❌ Could not find alternative for: {original_text}")
        return False

    def _verify_and_fix_form(self, form: dict, max_attempts: int = 3) -> bool:
        """
        Verify form navigation path and attempt fixes if needed.
        Returns True if path works, False if unfixable.
        """
        print(f"\n  🔍 Verifying navigation path...")
        
        for attempt in range(max_attempts):
            self.driver.get(self.start_url)
            dismiss_all_popups_and_overlays(self.driver)
            wait_dom_ready(self.driver)
            time.sleep(1)
            
            steps = form.get('navigation_steps', [])
            failed_at = None
            
            for idx, step in enumerate(steps):
                if step.get('action') == 'wait_for_load':
                    continue
                
                selector = step.get('selector', '')
                text = step.get('locator_text', '')
                
                element = self._find_element_by_selector_or_text(selector, text)
                
                if not element:
                    print(f"    ❌ Step {idx + 1} failed: Cannot find '{text}'")
                    failed_at = idx
                    break
                
                if not safe_click(self.driver, element):
                    print(f"    ❌ Step {idx + 1} failed: Click failed on '{text}'")
                    failed_at = idx
                    break
                
                time.sleep(0.8)
                wait_dom_ready(self.driver)
            
            if failed_at is None:
                current_url = self.driver.current_url
                expected_url = form.get('form_url', '')
                
                if current_url == expected_url:
                    print(f"    ✅ Path verified successfully!")
                    return True
                else:
                    print(f"    ❌ Wrong destination")
                    print(f"       Expected: {expected_url}")
                    print(f"       Got: {current_url}")
                    return False
            
            if attempt < max_attempts - 1:
                if self._fix_failing_step(form, failed_at):
                    print(f"    🔄 Retrying with fixed path (attempt {attempt + 2}/{max_attempts})...")
                    # Server updates the JSON file
                    self.server.update_form_json(form)
                else:
                    print(f"    ❌ Could not fix step {failed_at + 1}")
                    return False
            else:
                print(f"    ❌ Max attempts reached - path is broken")
                return False
        
        return False

    def _update_form_json(self, form: Dict):
        """Update form JSON with fixed path - delegates to server"""
        self.server.update_form_json(form)

    def _build_hierarchy(self, forms: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Build form hierarchy - delegates to server"""
        return self.server.build_hierarchy(forms)

    def crawl(self):
        """Main crawl entry point"""
        # Server handles AI cost tracking
        if self.use_ai:
            self.server.print_ai_cost_summary()
        
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
        
        # Server builds hierarchy
        hierarchy = self.server.build_hierarchy(all_forms)
        ordered_names = hierarchy.get("ordered_forms") or [f["form_name"] for f in all_forms]
        
        if self.discovery_only:
            print("\n" + "=" * 70)
            print("✅ COMPLETE!")
            print("=" * 70)
            print(f"Created folders and JSONs for {len(all_forms)} forms")
            print(f"Forms: {ordered_names}")
            print("Next step: Run with discovery_only=False for field exploration")
            print("=" * 70 + "\n")
            
            if self.use_ai:
                self.server.print_ai_cost_summary()
            
            return
        
        # Full exploration mode - not implemented in agent yet
        # This would require FormRoutesExplorer to be split similarly
        print("\n⚠️  Full exploration mode not yet implemented in agent")
        print("Run discovery_only=True for now")

    def close_logger(self):
        """Clean up logger at end of crawl"""
        if hasattr(self, 'log'):
            self.log.kill_logger()
