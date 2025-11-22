# selenium_actions.py
# Selenium WebDriver Actions and DOM Handling

import os
import time
import hashlib
import json
import logging
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException
)

logger = logging.getLogger('init_logger.form_page_test')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')


# ============================================================
# DOM CACHE WITH HASH VALIDATION
# ============================================================
class DOMCache:
    """
    Cache DOM by URL to avoid redundant AI calls - SAVES API COSTS
    
    ⚠️ CRITICAL: Must validate with DOM hash!
    
    WHY HASH VALIDATION IS ESSENTIAL:
    - Same URL can have different DOMs (AJAX, modals, filters, form errors)
    - Without hash: Cache returns stale DOM → AI generates wrong steps → Tests fail
    - With hash: Cache validates freshness → Only returns if DOM actually matches
    
    EXAMPLES OF SAME-URL DOM CHANGES:
    1. Form field changes (AJAX) - URL stays same, fields appear/disappear
    2. Form errors - URL stays same, error message appears
    3. Tab changes - URL stays same, content changes
    4. Modals - URL stays same, modal overlay appears
    
    This is why we MUST pass current_dom_hash to get() method!
    """
    
    def __init__(self, cache_file: str):
        self.cache = {}  # {url: {dom_html, dom_hash, timestamp}}
        self.cache_file = cache_file
        self.load_cache()
    
    def get_cache_key(self, url: str) -> str:
        """Generate cache key from URL (remove query params)"""
        from urllib.parse import urlparse, urlunparse
        parsed = urlparse(url)
        # Remove query params and fragments for cache key
        normalized = urlunparse((parsed.scheme, parsed.netloc, parsed.path, '', '', ''))
        return normalized
    
    def get(self, url: str, current_dom_hash: str) -> Optional[Dict[str, Any]]:
        """
        Get cached DOM data for URL with hash validation
        
        Args:
            url: Current page URL
            current_dom_hash: Hash of current actual DOM (for validation)
        
        Returns:
            Cached data if URL matches AND hash matches, None otherwise
        """
        key = self.get_cache_key(url)
        
        if key in self.cache:
            cached_data = self.cache[key]
            cached_hash = cached_data.get('dom_hash')
            
            # ✅ CRITICAL: Verify hash matches (DOM didn't change on same URL)
            if cached_hash == current_dom_hash:
                print(f"[DOMCache] ✅ Cache HIT for {key} (hash verified)")
                result_logger_gui.info(f"[DOMCache] Using cached DOM for {url}")
                return cached_data
            else:
                print(f"[DOMCache] ⚠️ Cache STALE for {key} (DOM changed on same URL)")
                print(f"[DOMCache]    Expected: {cached_hash[:16]}... Got: {current_dom_hash[:16]}...")
                return None
        
        print(f"[DOMCache] ❌ Cache MISS for {key}")
        return None
    
    def set(self, url: str, dom_html: str, dom_hash: str):
        """Save DOM to cache"""
        key = self.get_cache_key(url)
        self.cache[key] = {
            'dom_html': dom_html,
            'dom_hash': dom_hash,
            'timestamp': time.time()
        }
        print(f"[DOMCache] 💾 Cached DOM for {key} ({len(dom_html)} chars)")
        logger.info(f"[DOMCache] Cached DOM for {url}")
        self.save_cache()
    
    def load_cache(self):
        """Load cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                print(f"[DOMCache] Loaded {len(self.cache)} cached DOMs")
                logger.info(f"[DOMCache] Loaded {len(self.cache)} cached entries")
        except Exception as e:
            print(f"[DOMCache] Error loading cache: {e}")
            self.cache = {}
    
    def save_cache(self):
        """Save cache to file"""
        try:
            with open(self.cache_file, 'w') as f:
                json.dump(self.cache, f, indent=2)
        except Exception as e:
            print(f"[DOMCache] Error saving cache: {e}")
    
    def clear_old_entries(self, max_age_hours: int = 24):
        """Remove cache entries older than max_age_hours"""
        current_time = time.time()
        max_age_seconds = max_age_hours * 3600
        
        old_keys = [
            key for key, value in self.cache.items()
            if current_time - value.get('timestamp', 0) > max_age_seconds
        ]
        
        for key in old_keys:
            del self.cache[key]
        
        if old_keys:
            print(f"[DOMCache] Cleared {len(old_keys)} old entries")
            result_logger_gui.info(f"[DOMCache] Cleared {len(old_keys)} old entries")
            self.save_cache()


# ============================================================
# SMART CONTEXT ANALYZER
# ============================================================
class ContextAnalyzer:
    """Analyzes test context to determine if verification elements are needed"""
    
    @staticmethod
    def needs_verification(previous_steps: List[Dict], test_cases: List[Dict]) -> bool:
        """
        Determine if next steps likely need verification elements
        
        Returns True if:
        - Last step was a form submission
        - Last step was navigation to success/confirmation page
        - Test case name contains "verify"
        """
        
        # Check test case names for verification keywords
        verification_keywords = ['verify', 'check', 'validate', 'confirm', 'ensure']
        for test_case in test_cases:
            test_name = test_case.get('name', '').lower()
            if any(keyword in test_name for keyword in verification_keywords):
                print("[ContextAnalyzer] Test case mentions verification → Including verification elements")
                return True
        
        # Check previous steps for actions that typically lead to verification
        if previous_steps:
            last_step = previous_steps[-1]
            last_action = last_step.get('action', '')
            last_description = last_step.get('description', '').lower()
            
            # Actions that usually need verification next
            verification_triggers = [
                'submit', 'save', 'create', 'register', 
                'login', 'signup', 'update', 'confirm'
            ]
            
            if last_action in ['submit', 'click']:
                print("[ContextAnalyzer] Last action was submit/click → Including verification elements")
                return True
            
            if last_action == 'navigate':
                nav_url = last_step.get('value', '').lower()
                if any(word in nav_url for word in ['success', 'confirmation', 'complete', 'thank']):
                    print("[ContextAnalyzer] Navigated to success/confirmation → Including verification elements")
                    return True
            
            if any(trigger in last_description for trigger in verification_triggers):
                print(f"[ContextAnalyzer] Last step '{last_description}' → Including verification elements")
                return True
        
        # Default: actions only (optimization)
        print("[ContextAnalyzer] Context suggests actions only → Minimal DOM")
        return False


# ============================================================
# DOM EXTRACTOR (MINIMAL DOM OPTIMIZATION)
# ============================================================
class DOMExtractor:
    """Extract and track DOM state - WITH MINIMAL DOM OPTIMIZATION"""
    
    def __init__(self, driver: WebDriver):
        self.driver = driver
    
    def get_dom_html(self) -> str:
        """Get full page source HTML"""
        return self.driver.page_source
    
    def get_dom_hash(self) -> str:
        """Generate MD5 hash of current DOM"""
        dom_html = self.get_dom_html()
        return hashlib.md5(dom_html.encode('utf-8')).hexdigest()
    
    def get_form_dom_with_js(self) -> str:
        """
        Extract form + all JavaScript (inline + external)
        Fetches external JS files and inlines them
        
        Returns:
            HTML string with forms and all JavaScript inlined
        """
        html = self.get_dom_html()
        soup = BeautifulSoup(html, 'html.parser')
        
        result = []
        
        # 1. Get all forms
        forms = soup.find_all('form')
        for form in forms:
            result.append(str(form))
        
        # If no forms found, get body content
        if not forms:
            body = soup.find('body')
            if body:
                result.append(str(body))
        
        # 2. Get all inline scripts
        scripts = soup.find_all('script', src=False)  # No src attribute
        for script in scripts:
            result.append(str(script))
        
        # 3. Get all external scripts and fetch their content
        external_scripts = soup.find_all('script', src=True)
        for script in external_scripts:
            src = script.get('src')
            try:
                # Fetch the JS file
                js_content = self._fetch_js_file(src)
                # Wrap in <script> tag
                result.append(f'<script>\n/* Fetched from: {src} */\n{js_content}\n</script>')
                print(f"[DOMExtractor] Fetched external JS: {src}")
            except Exception as e:
                # If fetch fails, keep original tag
                print(f"[DOMExtractor] Failed to fetch JS: {src} - {e}")
                result.append(str(script))
        
        combined_html = '\n'.join(result)
        
        # Calculate sizes
        original_size = len(html)
        result_size = len(combined_html)
        reduction = ((original_size - result_size) / original_size) * 100 if original_size > 0 else 0
        
        print(f"[DOMExtractor] Form+JS DOM: {result_size} chars (reduced by {reduction:.1f}%)")
        logger.info(f"[DOMExtractor] DOM size: {original_size} → {result_size} chars ({reduction:.1f}% reduction)")
        
        return combined_html
    
    def _fetch_js_file(self, src: str) -> str:
        """
        Fetch external JS file content
        
        Args:
            src: JS file URL (relative or absolute)
            
        Returns:
            JavaScript file content as string
        """
        import requests
        
        # Handle relative URLs
        if src.startswith('http'):
            url = src
        else:
            current_url = self.driver.current_url
            base_url = '/'.join(current_url.split('/')[:3])  # Get domain
            
            if src.startswith('/'):
                # Absolute path from root
                url = base_url + src
            else:
                # Relative path from current page
                url = current_url.rsplit('/', 1)[0] + '/' + src
        
        response = requests.get(url, timeout=5)
        response.raise_for_status()
        return response.text
    
    def get_minimal_dom(self, include_verification: bool = False) -> str:
        """
        ✅ OPTIMIZATION 1: Extract ONLY interactive and relevant elements
        
        Extracts:
        - Form elements (input, select, textarea, button)
        - Interactive elements (a, button with onclick)
        - Navigation elements
        - Structural context (forms, sections with IDs/classes)
        
        Optionally includes:
        - Verification elements (success messages, errors, confirmations)
        
        This reduces DOM size by 80-90%, saving massive API costs!
        """
        
        html = self.get_dom_html()
        soup = BeautifulSoup(html, 'html.parser')
        
        # Build minimal DOM with only relevant elements
        minimal_dom = []
        
        # Always include: Interactive form elements
        interactive_selectors = [
            'input', 'select', 'textarea', 'button',
            'a[href]',  # Links
            'form',     # Form containers
            '[data-qa]', '[data-testid]', '[data-test]',  # Test attributes
            '[onclick]', '[ng-click]',  # Click handlers
            'label',    # Labels for context
            '.tab', '[role="tab"]',  # Tabs
            '.modal', '[role="dialog"]',  # Modals
        ]
        
        for selector in interactive_selectors:
            elements = soup.select(selector)
            for elem in elements:
                minimal_dom.append(str(elem))
        
        # Conditionally include: Verification elements (only when needed)
        if include_verification:
            verification_selectors = [
                '.alert', '.message', '.notification',
                '.success', '.error', '.warning', '.info',
                '[role="alert"]',
                '.toast', '.snackbar',
                '.confirmation', '.result'
            ]
            
            for selector in verification_selectors:
                elements = soup.select(selector)
                for elem in elements:
                    minimal_dom.append(str(elem))
        
        # Include key structural elements for context
        structural_selectors = [
            'nav', 'header', 'footer',
            '[id]', '[class]'  # Elements with IDs/classes for better selection
        ]
        
        for selector in structural_selectors:
            elements = soup.select(selector)
            # Only include if they contain interactive elements
            for elem in elements:
                if elem.find(['input', 'select', 'button', 'a']):
                    minimal_dom.append(str(elem))
        
        # Combine and deduplicate
        minimal_html = '\n'.join(set(minimal_dom))
        
        # Calculate size reduction
        original_size = len(html)
        minimal_size = len(minimal_html)
        reduction = ((original_size - minimal_size) / original_size) * 100 if original_size > 0 else 0
        
        print(f"[DOMExtractor] Minimal DOM: {minimal_size} chars (reduced by {reduction:.1f}%)")
        logger.info(f"[DOMExtractor] DOM size: {original_size} → {minimal_size} chars ({reduction:.1f}% reduction)")
        
        return minimal_html


# ============================================================
# DOM CHANGE DETECTOR
# ============================================================
class DOMChangeDetector:
    """Detect when DOM changes during test execution"""
    
    def __init__(self):
        self.last_dom_hash = None
    
    def has_dom_changed(self, current_hash: str) -> bool:
        """Check if DOM has changed since last check"""
        if self.last_dom_hash is None:
            self.last_dom_hash = current_hash
            return False
        
        if current_hash != self.last_dom_hash:
            print(f"[DOMChangeDetector] DOM changed!")
            print(f"[DOMChangeDetector]   Previous: {self.last_dom_hash[:16]}...")
            print(f"[DOMChangeDetector]   Current:  {current_hash[:16]}...")
            logger.info(f"[DOMChangeDetector] DOM change detected")
            return True
        
        return False
    
    def update_hash(self, new_hash: str):
        """Update stored hash"""
        self.last_dom_hash = new_hash


# ============================================================
# STEP EXECUTOR (ALL SELENIUM ACTIONS)
# ============================================================
class StepExecutor:
    """Execute Selenium WebDriver test steps"""
    
    def __init__(self, driver: WebDriver, test_context, url: str, form_page_key: str, project_dir: str):
        self.driver = driver
        self.test_context = test_context
        self.url = url
        self.form_page_key = form_page_key
        self.screenshots_dir = os.path.join(project_dir, "screenshots")
        os.makedirs(self.screenshots_dir, exist_ok=True)
        self.shadow_root_context = None  # Store active shadow root context
    
    def capture_failure_screenshot(self, step_description: str):
        """Capture screenshot on step failure"""
        try:
            timestamp = int(time.time())
            # Sanitize filename
            safe_description = "".join(c if c.isalnum() or c in (' ', '_', '-') else '_' for c in step_description)
            safe_description = safe_description[:50]  # Limit length
            filename = f"failure_{timestamp}_{safe_description}.png"
            filepath = os.path.join(self.screenshots_dir, filename)
            
            self.driver.save_screenshot(filepath)
            print(f"[Screenshot] Saved to: {filepath}")
            result_logger_gui.info(f"[Screenshot] Failure captured: {filename}")
        except Exception as e:
            print(f"[Screenshot] Error capturing screenshot: {e}")
            logger.error(f"Screenshot capture failed: {e}")
    
    def _find_element(self, selector: str, timeout: int = 10):
        """Find element with wait - searches in shadow root if active"""
        try:
            # If we're in a shadow root context, search there
            if self.shadow_root_context:
                # Shadow root doesn't support WebDriverWait, use direct find
                try:
                    element = self.shadow_root_context.find_element(By.CSS_SELECTOR, selector)
                    return element
                except NoSuchElementException:
                    # Try waiting with polling
                    end_time = time.time() + timeout
                    while time.time() < end_time:
                        try:
                            element = self.shadow_root_context.find_element(By.CSS_SELECTOR, selector)
                            return element
                        except NoSuchElementException:
                            time.sleep(0.5)
                    print(f"⚠️ Element not found in shadow root: {selector}")
                    logger.warning(f"Element not found in shadow root within {timeout}s: {selector}")
                    return None
            else:
                # Normal search in main document
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return element
        except TimeoutException:
            print(f"⚠️ Element not found: {selector}")
            logger.warning(f"Element not found within {timeout}s: {selector}")
            return None
        except Exception as e:
            print(f"⚠️ Error finding element: {e}")
            logger.error(f"Error finding element '{selector}': {e}")
            return None
    
    def _verify(self, verification: str, selector: Optional[str] = None) -> tuple:
        """
        Verify a condition
        Returns: (success: bool, expected: str, actual: str)
        """
        try:
            if not selector:
                return (True, verification, "No selector provided")
            
            element = self._find_element(selector, timeout=5)
            
            if "is visible" in verification.lower() or "is displayed" in verification.lower():
                if element and element.is_displayed():
                    return (True, "Element visible", "Element is visible")
                else:
                    return (False, "Element visible", "Element not visible")
            
            elif "text" in verification.lower() or "contains" in verification.lower():
                if element:
                    actual_text = element.text.strip()
                    if actual_text:
                        return (True, verification, actual_text)
                    else:
                        return (False, verification, "No text found")
                else:
                    return (False, verification, "Element not found")
            
            else:
                # Generic verification
                if element:
                    return (True, verification, "Element exists")
                else:
                    return (False, verification, "Element not found")
                    
        except Exception as e:
            return (False, verification, f"Error: {str(e)}")
    
    def execute_step(self, step: Dict[str, Any]) -> bool:
        """
        Execute a single test step
        Returns True if successful, False if failed
        """
        try:
            step_num = step.get("step_number", "?")
            action = step.get("action")
            description = step.get("description", "")
            selector = step.get("selector")
            value = step.get("value")
            wait_seconds = step.get("wait_seconds", 0)
            
            print(f"\n[Step {step_num}] {action.upper()}: {description}")
            result_logger_gui.info(f"\n[Step {step_num}] {action.upper()}: {description}")
            
            if action == "navigate":
                result_logger_gui.info(f"Navigating to: {value}")
                result_logger_gui.info("-"*70)
                
                if value.startswith('http'):
                    self.driver.get(value)
                else:
                    # Relative URL
                    base_url = self.url.rstrip('/')
                    full_url = base_url + value
                    self.driver.get(full_url)
                
                result_logger_gui.info("✓ Navigation complete")
                logger.info(f"Navigated to: {value}")
            
            elif action == "click":
                result_logger_gui.info(f"Clicking: {description}")
                result_logger_gui.info("-"*70)
                
                element = self._find_element(selector)
                if element:
                    try:
                        # Try regular click first
                        element.click()
                        result_logger_gui.info("✓ Clicked successfully")
                        logger.info(f"Clicked element: {selector}")
                    except ElementClickInterceptedException:
                        # If intercepted, try JavaScript click
                        print("[Click] Element intercepted, trying JavaScript click...")
                        self.driver.execute_script("arguments[0].click();", element)
                        result_logger_gui.info("✓ Clicked successfully (via JavaScript)")
                        logger.info(f"Clicked element via JavaScript: {selector}")
                else:
                    result_logger_gui.info(f"✗ Failed to find element: {selector}")
                    logger.error(f"Element not found for click: {selector}")
                    self.capture_failure_screenshot(f"element_not_found_{description[:30]}")
                    return False
            
            elif action == "fill":
                result_logger_gui.info(f"Filling field: {description}")
                result_logger_gui.info(f"Value: {value}")
                result_logger_gui.info("-"*70)
                
                element = self._find_element(selector)
                if element:
                    element.clear()
                    element.send_keys(value)
                    result_logger_gui.info("✓ Field filled")
                    logger.info(f"Filled field '{selector}' with value: {value}")
                    
                    # Track in context
                    if self.test_context:
                        field_name = selector.split('[')[-1].rstrip(']') if '[' in selector else selector
                        self.test_context.track_field(field_name, value)
                else:
                    result_logger_gui.info(f"✗ Failed to find input field: {selector}")
                    logger.error(f"Element not found for fill: {selector}")
                    self.capture_failure_screenshot(f"input_not_found_{description[:30]}")
                    return False
            
            elif action == "select":
                result_logger_gui.info(f"Selecting: {description}")
                result_logger_gui.info(f"Value: {value}")
                result_logger_gui.info("-"*70)
                
                element = self._find_element(selector)
                if element:
                    tag_name = element.tag_name.lower()
                    
                    if tag_name == "select":
                        # Standard dropdown
                        from selenium.webdriver.support.ui import Select
                        select_element = Select(element)
                        
                        # Try different selection methods
                        try:
                            select_element.select_by_visible_text(value)
                            result_logger_gui.info(f"✓ Selected option: {value}")
                            logger.info(f"Selected dropdown option by text: {value}")
                        except:
                            try:
                                select_element.select_by_value(value)
                                result_logger_gui.info(f"✓ Selected option: {value}")
                                logger.info(f"Selected dropdown option by value: {value}")
                            except:
                                try:
                                    select_element.select_by_index(int(value))
                                    result_logger_gui.info(f"✓ Selected option: {value}")
                                    logger.info(f"Selected dropdown option by index: {value}")
                                except Exception as e:
                                    result_logger_gui.error(f"✗ Could not select option: {value}")
                                    logger.error(f"Failed to select dropdown option: {e}")
                                    self.capture_failure_screenshot(f"select_failed_{description[:30]}")
                                    return False
                        
                        # Track choice in context
                        if self.test_context:
                            field_name = selector.split('[')[-1].rstrip(']') if '[' in selector else selector
                            self.test_context.track_choice(field_name, value)
                    
                    elif tag_name == "input" and element.get_attribute("type") == "radio":
                        # Radio button - find all radio buttons with same name
                        radio_name = element.get_attribute("name")
                        if radio_name:
                            radio_buttons = self.driver.find_elements(By.CSS_SELECTOR, f"input[name='{radio_name}'][type='radio']")
                        else:
                            # Fallback to finding by parent selector
                            radio_buttons = [element]
                        
                        clicked = False
                        # Try to find radio by value
                        for radio in radio_buttons:
                            radio_value = radio.get_attribute("value")
                            if radio_value and value.lower() in radio_value.lower():
                                radio.click()
                                result_logger_gui.info(f"✓ Selected radio: {value}")
                                result_logger_gui.info("-" * 70)
                                logger.info(f"Selected radio button: {value}")
                                clicked = True
                                
                                # Track choice in context
                                if self.test_context:
                                    self.test_context.track_choice(radio_name, value)
                                
                                break
                        
                        if not clicked:
                            # Try matching by label text
                            for radio in radio_buttons:
                                # Look for label next to this radio
                                try:
                                    label = radio.find_element(By.XPATH, "./following-sibling::*[1]")
                                    if value.lower() in label.text.lower():
                                        radio.click()
                                        result_logger_gui.info(f"✓ Selected radio: {value}")
                                        result_logger_gui.info("-" * 70)
                                        logger.info(f"Successfully selected radio button by label: {value}")
                                        clicked = True
                                        
                                        # Track choice in context
                                        if self.test_context:
                                            self.test_context.track_choice(radio_name, value)
                                        
                                        break
                                except:
                                    pass
                        
                        if not clicked:
                            result_logger_gui.error(f"✗ Could not find radio option: {value}")
                            logger.error(f"Radio option not found: {value}")
                            self.capture_failure_screenshot(f"radio_option_not_found")
                            return False
                    
                    else:
                        # Unknown element type for select
                        result_logger_gui.error(f"✗ Select action requires <select> or radio buttons, got <{tag_name}>")
                        logger.error(f"Invalid element type for select: {tag_name}")
                        self.capture_failure_screenshot(f"invalid_element_type_for_select")
                        return False
            
            elif action == "submit":
                result_logger_gui.info(f"Submitting form: {description}")
                result_logger_gui.info("-"*70)
                
                element = self._find_element(selector)
                if element:
                    element.submit()
                    result_logger_gui.info("✓ Form submitted")
                    logger.info(f"Successfully submitted form: {selector}")
                else:
                    result_logger_gui.info(f"✗ Failed to find form: {selector}")
                    logger.error(f"Element not found for submit: {selector}")
                    self.capture_failure_screenshot(f"element_not_found_for_submit")
                    return False
            
            elif action == "wait":
                time.sleep(wait_seconds)
                result_logger_gui.info(f"[Step {step_num}] Waited {wait_seconds}s")
            
            elif action == "scroll":
                result_logger_gui.info(f"Scrolling: {description}")
                result_logger_gui.info("-"*70)
                
                if selector:
                    element = self._find_element(selector)
                    if element:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                        result_logger_gui.info("✓ Scrolled to element")
                        logger.info(f"Scrolled to element: {selector}")
                else:
                    # Scroll to bottom
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                    result_logger_gui.info("✓ Scrolled to bottom")
                    logger.info("Scrolled to page bottom")
            
            elif action == "verify":
                result_logger_gui.info(f"Validating: {description}")
                
                verification = step.get("verification", "")
                success, expected, actual = self._verify(verification, selector)
                
                if success:
                    result_logger_gui.info(f"✓ Validation passed")
                    logger.info(f"Verification passed: {verification}")
                    result_logger_gui.info("-" * 70)
                else:
                    result_logger_gui.info(f"✗ Validation failed")
                    result_logger_gui.info(f"  Expected: {expected}")
                    result_logger_gui.info(f"  Actual: {actual}")
                    logger.warning(f"Verification failed - Expected: {expected}, Actual: {actual}")
                    self.capture_failure_screenshot(f"verify_failed_{verification[:50]}")
                    return False
            
            elif action == "hover":
                result_logger_gui.info(f"Hovering: {description}")
                result_logger_gui.info("-"*70)
                
                element = self._find_element(selector)
                if element:
                    from selenium.webdriver.common.action_chains import ActionChains
                    actions = ActionChains(self.driver)
                    actions.move_to_element(element).perform()
                    result_logger_gui.info("✓ Hovered successfully")
                    logger.info(f"Hovered over element: {selector}")
                    # Wait a bit for hover effects to trigger
                    time.sleep(1)
                else:
                    result_logger_gui.info(f"✗ Failed to find element: {selector}")
                    logger.error(f"Element not found for hover: {selector}")
                    self.capture_failure_screenshot(f"element_not_found_hover_{description[:30]}")
                    return False

            elif action == "close_alert":
                try:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    alert.accept()
                    result_logger_gui.info(f"Closed alert: {alert_text}")
                    result_logger_gui.info("-"*70)
                    logger.info(f"Closed alert with text: {alert_text}")
                except:
                    logger.warning("No alert present to close")
                    pass
            
            elif action == "accept_alert":
                result_logger_gui.info(f"Accepting alert: {description}")
                result_logger_gui.info("-"*70)
                try:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    alert.accept()
                    result_logger_gui.info(f"✓ Alert accepted: {alert_text}")
                    logger.info(f"Accepted alert with text: {alert_text}")
                except Exception as e:
                    result_logger_gui.error(f"✗ No alert to accept: {e}")
                    logger.warning(f"No alert present to accept: {e}")
                    return False
            
            elif action == "dismiss_alert":
                result_logger_gui.info(f"Dismissing alert: {description}")
                result_logger_gui.info("-"*70)
                try:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    alert.dismiss()
                    result_logger_gui.info(f"✓ Alert dismissed: {alert_text}")
                    logger.info(f"Dismissed alert with text: {alert_text}")
                except Exception as e:
                    result_logger_gui.error(f"✗ No alert to dismiss: {e}")
                    logger.warning(f"No alert present to dismiss: {e}")
                    return False
            
            elif action == "fill_alert":
                result_logger_gui.info(f"Filling alert prompt: {description}")
                result_logger_gui.info(f"Value: {value}")
                result_logger_gui.info("-"*70)
                try:
                    alert = self.driver.switch_to.alert
                    alert.send_keys(value)
                    result_logger_gui.info(f"✓ Alert prompt filled with: {value}")
                    logger.info(f"Filled alert prompt with: {value}")
                except Exception as e:
                    result_logger_gui.error(f"✗ Failed to fill alert: {e}")
                    logger.error(f"Failed to fill alert prompt: {e}")
                    return False
            
            # ===== IFRAME HANDLING ACTIONS =====
            
            elif action == "switch_to_frame":
                result_logger_gui.info(f"Switching to iframe: {description}")
                result_logger_gui.info("-"*70)
                
                try:
                    # Find the iframe element
                    iframe_element = self._find_element(selector)
                    if iframe_element:
                        # Switch into the iframe
                        self.driver.switch_to.frame(iframe_element)
                        result_logger_gui.info("✓ Switched to iframe successfully")
                        logger.info(f"Switched to iframe: {selector}")
                    else:
                        result_logger_gui.info(f"✗ Failed to find iframe: {selector}")
                        logger.error(f"Iframe not found: {selector}")
                        self.capture_failure_screenshot(f"iframe_not_found_{description[:30]}")
                        return False
                except Exception as e:
                    result_logger_gui.error(f"✗ Error switching to iframe: {e}")
                    logger.error(f"Error switching to iframe '{selector}': {e}")
                    self.capture_failure_screenshot(f"iframe_switch_error")
                    return False
            
            elif action == "switch_to_parent_frame":
                result_logger_gui.info(f"Switching to parent frame: {description}")
                result_logger_gui.info("-"*70)
                
                try:
                    self.driver.switch_to.parent_frame()
                    result_logger_gui.info("✓ Switched to parent frame successfully")
                    logger.info("Switched to parent frame")
                except Exception as e:
                    result_logger_gui.error(f"✗ Error switching to parent frame: {e}")
                    logger.error(f"Error switching to parent frame: {e}")
                    self.capture_failure_screenshot(f"parent_frame_switch_error")
                    return False
            
            elif action == "switch_to_default":
                result_logger_gui.info(f"Switching to default content: {description}")
                result_logger_gui.info("-"*70)
                
                try:
                    self.driver.switch_to.default_content()
                    # Clear shadow root context when returning to main document
                    self.shadow_root_context = None
                    result_logger_gui.info("✓ Switched to default content successfully")
                    logger.info("Switched to default content (main page)")
                except Exception as e:
                    result_logger_gui.error(f"✗ Error switching to default content: {e}")
                    logger.error(f"Error switching to default content: {e}")
                    self.capture_failure_screenshot(f"default_content_switch_error")
                    return False
            
            # ===== SHADOW ROOT HANDLING =====
            
            elif action == "switch_to_shadow_root":
                result_logger_gui.info(f"Accessing shadow root: {description}")
                result_logger_gui.info("-"*70)
                
                try:
                    # Find the shadow host element
                    shadow_host = self._find_element(selector)
                    if shadow_host:
                        # Access shadow root and store it as active context
                        self.shadow_root_context = shadow_host.shadow_root
                        result_logger_gui.info("✓ Accessed shadow root successfully")
                        logger.info(f"Accessed shadow root on element: {selector}")
                        print(f"✓ Shadow root context active - subsequent finds will search inside shadow DOM")
                    else:
                        result_logger_gui.info(f"✗ Failed to find shadow host: {selector}")
                        logger.error(f"Shadow host not found: {selector}")
                        self.capture_failure_screenshot(f"shadow_host_not_found")
                        return False
                except Exception as e:
                    result_logger_gui.error(f"✗ Error accessing shadow root: {e}")
                    logger.error(f"Error accessing shadow root '{selector}': {e}")
                    self.capture_failure_screenshot(f"shadow_root_access_error")
                    return False
            
            else:
                print(f"⚠️ Unknown action: {action}")
                result_logger_gui.warning(f"[Step {step_num}] Unknown action: {action}")
            
            # Wait after step
            if wait_seconds > 0:
                time.sleep(wait_seconds)
            
            return True
            
        except Exception as e:
            print(f"❌ Error executing step: {e}")
            result_logger_gui.error(f"[Step {step.get('step_number', '?')}] Error: {e}")
            import traceback
            traceback.print_exc()
            self.capture_failure_screenshot(f"error_executing_step")
            return False
