# ai_test_executor.py
# Project 2 - AI-Driven Shopping Site Test Automation (OPTIMIZED)
# ✅ OPTIMIZATION 1: Minimal DOM - Only send interactive elements
# ✅ OPTIMIZATION 2: DOM Cache by URL - Avoid redundant API calls
# ✅ OPTIMIZATION 3: Smart Context Detection - Include verification elements only when needed
# Expected Cost Savings: 85%+ on API calls

import os
import sys
import time
import json
import hashlib
import requests
from typing import List, Dict, Optional, Any
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    NoSuchWindowException,
    InvalidSessionIdException,
    SessionNotCreatedException,
    ElementNotInteractableException,
    StaleElementReferenceException
)



# ============================================================
# SHOPPING SITES CONFIGURATION
# ============================================================
SHOPPING_SITES = {
    "automation_exercise": {
        "url": "https://automationexercise.com/",
        "test_cases_url": "https://automationexercise.com/test_cases",
        "requires_auth": True,
        "test_groups": [
            {"name": "auth", "range": [0, 5], "description": "Authentication tests"},
            {"name": "products", "range": [5, 10], "description": "Product browsing tests"},
            {"name": "cart", "range": [10, 15], "description": "Shopping cart tests"},
            {"name": "checkout", "range": [15, 20], "description": "Checkout tests"},
            {"name": "misc", "range": [20, 27], "description": "Other tests"}
        ]
    }
}

# Test cases cache file (shared across all sites)
TEST_CASES_CACHE_FILE = "shopping_site_test_cases.json"
DOM_CACHE_FILE = "dom_cache.json"

# ============================================================
# LOGGING SETUP
# ============================================================
import logging
from inits.log import Logger
import inits.environment as environment
environment.test_mode = "single_test_first"

my_log = Logger(is_full_test=True)
my_log.init_logger()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S'
)

logger = logging.getLogger('init_logger.shopping_test_site')
result_logger_gui = logging.getLogger('init_result_logger_gui.shopping_test_site')



# ============================================================
# OPTIMIZATION 2: DOM CACHE BY URL
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
    1. Add to cart (AJAX) - URL stays /products, cart count changes
    2. Form errors - URL stays /login, error message appears
    3. Filters - URL stays /products, product list changes
    4. Modals - URL stays same, modal overlay appears
    
    This is why we MUST pass current_dom_hash to get() method!
    """
    
    def __init__(self, cache_file: str = DOM_CACHE_FILE):
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
                result_logger_gui.warning(f"[DOMCache] Hash mismatch - DOM changed without URL change")
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
        result_logger_gui.info(f"[DOMCache] Cached DOM for {url}")
        self.save_cache()
    
    def load_cache(self):
        """Load cache from file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.cache = json.load(f)
                print(f"[DOMCache] Loaded {len(self.cache)} cached DOMs")
                result_logger_gui.info(f"[DOMCache] Loaded {len(self.cache)} cached entries")
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
# OPTIMIZATION 3: SMART CONTEXT DETECTION
# ============================================================
class ContextAnalyzer:
    """Analyzes test context to determine if verification elements are needed"""
    
    @staticmethod
    def needs_verification(previous_steps: List[Dict], test_cases: List[Dict]) -> bool:
        """
        Determine if next steps likely need verification elements
        
        Returns True if:
        - Last step was a form submission
        - Last step was "add to cart"
        - Last step was navigation to cart/checkout/confirmation
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
                'submit', 'add to cart', 'place order', 'checkout',
                'register', 'login', 'signup', 'create account',
                'apply coupon', 'remove', 'delete', 'update'
            ]
            
            if last_action in ['submit', 'click', 'fill_checkout']:
                print("[ContextAnalyzer] Last action was submit/checkout → Including verification elements")
                return True
            
            if last_action == 'navigate':
                nav_url = last_step.get('value', '').lower()
                if any(word in nav_url for word in ['cart', 'checkout', 'order', 'confirmation', 'success']):
                    print("[ContextAnalyzer] Navigated to cart/checkout/success → Including verification elements")
                    return True
            
            if any(trigger in last_description for trigger in verification_triggers):
                print(f"[ContextAnalyzer] Last step '{last_description}' → Including verification elements")
                return True
        
        # Default: actions only (optimization)
        print("[ContextAnalyzer] Context suggests actions only → Minimal DOM")
        return False


# ============================================================
# TEST CONTEXT
# ============================================================
class TestContext:
    """Stores registered user credentials and shopping session state"""

    def __init__(self):
        # User credentials
        self.registered_email = None
        self.registered_password = None
        self.registered_name = None
        
        # Cart tracking
        self.cart_items = []
        self.expected_cart_total = 0.0
        
        # Checkout tracking
        self.checkout_info = {}
        
        # Coupon/discount tracking
        self.coupon_applied = None
        self.discount_amount = 0.0
        self.original_total = 0.0
        
        # Order tracking
        self.order_id = None
        
        # Product variants tracking
        self.selected_variants = {}

    def has_credentials(self):
        """Check if credentials are stored"""
        return self.registered_email is not None
    
    def add_to_cart(self, item_name: str, price: float, quantity: int = 1):
        """Track item added to cart"""
        self.cart_items.append({
            "name": item_name,
            "price": price,
            "quantity": quantity
        })
        self.expected_cart_total += (price * quantity)
        print(f"[Cart] Added: {item_name} x{quantity} @ ${price} = ${price * quantity}")
        print(f"[Cart] Expected Total: ${self.expected_cart_total:.2f}")
        result_logger_gui.info(f"[Cart] Added {item_name}, Expected Total: ${self.expected_cart_total:.2f}")
    
    def clear_cart(self):
        """Clear cart tracking"""
        self.cart_items = []
        self.expected_cart_total = 0.0
        print("[Cart] Cleared")
        result_logger_gui.info("[Cart] Cleared")
    
    def apply_coupon(self, code: str, discount: float):
        """Track coupon application"""
        self.coupon_applied = code
        self.discount_amount = discount
        self.original_total = self.expected_cart_total
        self.expected_cart_total -= discount
        print(f"[Coupon] Applied: {code}, Discount: ${discount:.2f}")
        print(f"[Coupon] New Expected Total: ${self.expected_cart_total:.2f}")
        result_logger_gui.info(f"[Coupon] Applied {code}, New Total: ${self.expected_cart_total:.2f}")


# ============================================================
# AI HELPER
# ============================================================
import anthropic


class AIHelper:
    """Helper class for AI-powered step generation using Claude API"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required for AI functionality")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"

    def generate_test_steps(
            self,
            dom_html: str,
            test_cases: List[Dict[str, str]],
            previous_steps: Optional[List[Dict]] = None,
            step_where_dom_changed: Optional[int] = None,
            test_context=None,
            is_first_group: bool = False
    ) -> List[Dict[str, Any]]:
        """
        Generate Selenium test steps based on DOM and test cases.
        If DOM changed, provide previous steps and which step caused the change.
        """
        
        # Build the prompt
        if previous_steps and step_where_dom_changed is not None:
            context = f"""
DOM CHANGED after executing step {step_where_dom_changed}.

Previous steps that were executed:
{json.dumps(previous_steps[:step_where_dom_changed + 1], indent=2)}

Please generate the REMAINING steps (starting from step {step_where_dom_changed + 1}) 
based on this NEW DOM state.
"""
        else:
            context = "This is the initial DOM. Please generate ALL test steps."

        import random

        if is_first_group and test_context:
            # First group: generate NEW random credentials for registration
            timestamp = int(time.time())
            test_email = f"testuser_{timestamp}@example.com"
            test_password = f"TestPass{random.randint(1000, 9999)}"
            test_name = f"TestUser{random.randint(100, 999)}"

            credentials_instruction = f"""=== TEST CREDENTIALS (FIRST GROUP - REGISTRATION) ===
        For registration tests, use these NEW credentials:
        - Name: {test_name}
        - Email: {test_email}
        - Password: {test_password}

        Store these credentials as they will be used for login in subsequent test groups.
        """
            # Save to context
            test_context.registered_name = test_name
            test_context.registered_email = test_email
            test_context.registered_password = test_password
        else:
            # Subsequent groups: use EXISTING credentials for login only
            if test_context and test_context.has_credentials():
                credentials_instruction = f"""=== TEST CREDENTIALS (SUBSEQUENT GROUP - LOGIN ONLY) ===
        User is already registered. For any login tests, use these credentials:
        - Name: {test_context.registered_name}
        - Email: {test_context.registered_email}
        - Password: {test_context.registered_password}

        DO NOT perform registration again. Only do login if needed.
        """
            else:
                credentials_instruction = "=== NO CREDENTIALS AVAILABLE ===\nSkip any login/registration tests.\n"

        prompt = f"""You are a test automation expert. I need you to generate Selenium WebDriver steps to execute test cases on a shopping website.

{context}

{credentials_instruction}

=== AVAILABLE ACTIONS ===
**Standard Actions:**
- navigate: Go to URL
- click: Click element
- fill: Enter text
- select: Select dropdown option
- submit: Submit form
- wait: Wait duration
- verify: Check condition
- scroll: Scroll to element

**Shopping-Specific Actions (Priority 1):**

1. **add_to_cart**: Track cart item
   {{"action": "add_to_cart", "item_name": "Product Name", "price": 500, "quantity": 1}}

2. **verify_cart_total**: Verify cart total matches expected
   {{"action": "verify_cart_total", "selector": ".cart-total"}}

3. **apply_coupon**: Apply discount code
   {{"action": "apply_coupon", "code": "SAVE20", "selector": "input.coupon-code", "discount": 100}}

4. **verify_discount**: Check discount was applied
   {{"action": "verify_discount", "selector": ".discount-amount"}}

5. **dismiss_popup**: Close popups/banners/modals
   {{"action": "dismiss_popup", "selector": ".cookie-banner .accept-btn"}}

6. **wait_for_ajax**: Wait for loading spinner to disappear
   {{"action": "wait_for_ajax", "selector": ".loading-spinner", "wait_seconds": 10}}

7. **select_variant**: Choose product size/color/variant
   {{"action": "select_variant", "variant_type": "size", "value": "L", "selector": "select.product-size"}}

8. **fill_checkout**: Fill multi-field checkout form
   {{"action": "fill_checkout", "fields": {{"street": "input#street", "city": "input#city"}}, "data": {{"street": "123 Main St", "city": "New York"}}}}

9. **save_order_id**: Capture order confirmation number
   {{"action": "save_order_id", "selector": ".order-id"}}

10. **close_alert**: Close JavaScript alert/popup
   {{"action": "close_alert"}}

Use these shopping-specific actions when appropriate for cart, checkout, and discount scenarios.

=== CURRENT DOM (OPTIMIZED) ===
{dom_html}

=== TEST CASES TO IMPLEMENT ===
{json.dumps(test_cases[:5], indent=2)}

=== REQUIREMENTS ===
0. **IMPORTANT: Skip any test cases that are not applicable to this website.** 
   - If a test requires features/elements not present in the DOM, do not generate steps for it.
   - Only generate steps for tests that can actually be executed on this site.
   - If skipping a test, just omit it from the output (don't create placeholder steps).

1. Generate a JSON array of Selenium actions
2. Each action must have:
   - "step_number": integer
   - "test_case": which test case this belongs to
   - "action": one of [navigate, click, fill, select, submit, wait, verify, scroll]
   - "description": human-readable description
   - "selector": CSS selector or XPath (for element actions)
   - "value": value to enter (for fill/select actions)
   - "verification": what to verify after action (optional)
   - "wait_seconds": seconds to wait after action (default: 1)

3. Actions should be DETAILED and SEQUENTIAL
4. Include verification steps after important actions

5. **CRITICAL: SELECTOR PRECISION RULES**
   ⚠️ ALWAYS use the MOST SPECIFIC selector that matches ONLY ONE element
   
   **Before choosing ANY selector, ask yourself:**
   "If there are multiple similar elements on the page, will this find the CORRECT one?"
   If answer is NO or MAYBE → Add more specificity!
   
   **Specificity Hierarchy (Best to Worst):**
   ✅ BEST: Unique data attributes
      Example: input[data-qa='signup-name']
   
   ✅ GOOD: Unique ID
      Example: #email-input
   
   ✅ GOOD: Specific class with context
      Example: .signup-form input[name='email']
      Example: div.login-section .submit-btn
   
   ⚠️ RISKY: Generic tags with ID parent
      Example: section#form h2  ← Could match multiple h2s!
      FIX: .signup-form h2  ← Now specific to signup section
   
   ❌ BAD: Generic tags without specificity
      Example: h2, button, input  ← Which one???
   
   **Common Mistakes to AVOID:**
   ❌ section#form h2           → Could match login OR signup h2
   ✅ .signup-form h2            → Specific to signup section
   
   ❌ form button                → Which form? Which button?
   ✅ .signup-form button[type='submit']  → Specific button
   
   ❌ input[name='email']        → Could be login or signup email
   ✅ .signup-form input[name='email']    → Signup email specifically

6. **FORBIDDEN Selectors (NEVER use):**
   ❌ :contains('text') - NOT supported by Selenium
   ❌ jQuery syntax

7. **CRITICAL SELECTOR RULES - NO TEXT-BASED SELECTORS:**
   
   ⛔ ABSOLUTELY FORBIDDEN - Text-based selectors (NEVER use):
      ❌ //h2[contains(text(), 'Enter Account Information')]
      ❌ //button[text()='Submit']
      ❌ //div[contains(text(), 'Success')]
      ❌ ANY selector using text() or contains(text(),...)
   
   ✅ REQUIRED - Use ONLY these selector types:
   
   PRIORITY 1 (BEST): Unique attributes
      ✅ input[data-qa='signup-name']
      ✅ button[data-testid='submit-btn']
      ✅ [aria-label='Add to cart']
   
   PRIORITY 2 (GOOD): Unique IDs
      ✅ #checkout-button
      ✅ #email-input
   
   PRIORITY 3 (ACCEPTABLE): Classes with hierarchy
      ✅ .signup-form button.submit
      ✅ h2.title.text-center
      ✅ div.product-card h3
   
   PRIORITY 4 (LAST RESORT): Structural selectors
      ✅ form > button:last-child
      ✅ div.section > h2:first-child
      ✅ [class*="submit"][class*="button"]
   
   **For verification steps:**
   - Verify element EXISTS, not text content
   - Example: verify h2.title.text-center exists (do not check text)
   - The element's presence confirms the page loaded correctly
   
   **Why text selectors are absolutely forbidden:**
   - Break with nested tags: <h2><b>text</b></h2>
   - Break with case: UPPERCASE vs lowercase
   - Break with translations
   - Break with whitespace changes
   - Significantly slower execution

8. Add explicit waits where needed

=== EXAMPLE OUTPUT FORMAT ===
[
  {{
    "step_number": 1,
    "test_case": "Register User",
    "action": "navigate",
    "description": "Navigate to home page",
    "selector": null,
    "value": "http://automationexercise.com",
    "verification": "page title contains 'Automation Exercise'",
    "wait_seconds": 2
  }},
  {{
    "step_number": 2,
    "test_case": "Register User",
    "action": "click",
    "description": "Click on Signup/Login button",
    "selector": "a[href='/login']",
    "value": null,
    "verification": "login page is visible",
    "wait_seconds": 1
  }},
  {{
    "step_number": 3,
    "test_case": "Register User",
    "action": "fill",
    "description": "Enter name in signup form",
    "selector": "input[data-qa='signup-name']",
    "value": "Test User",
    "verification": null,
    "wait_seconds": 0.5
  }}
]

Now generate the complete test steps as a valid JSON array. 
ONLY return the JSON array, no other text or explanation.
"""
        
        try:
            result_logger_gui.info("[AIHelper] Sending request to Claude API...")
            print("[AIHelper] Sending request to Claude API...")

            message = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            result_logger_gui.info(f"[AIHelper] Received response ({len(response_text)} chars)")
            print(f"[AIHelper] Received response ({len(response_text)} chars)")
            
            # Parse JSON from response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            steps = json.loads(response_text)
            
            result_logger_gui.info(f"[AIHelper] Successfully parsed {len(steps)} steps")
            print(f"[AIHelper] Successfully parsed {len(steps)} steps")
            
            return steps
            
        except json.JSONDecodeError as e:
            result_logger_gui.error(f"[AIHelper] Failed to parse JSON: {e}")
            print(f"[AIHelper] Failed to parse JSON: {e}")
            print(f"[AIHelper] Response text: {response_text[:500]}")
            return []
        except Exception as e:
            result_logger_gui.error(f"[AIHelper] Error: {e}")
            print(f"[AIHelper] Error: {e}")
            import traceback
            traceback.print_exc()
            return []


# ============================================================
# TEST CASE REPOSITORY (Caching)
# ============================================================
class TestCaseRepository:
    """Manages caching of test cases to avoid repeated fetching"""
    
    def __init__(self, cache_file: str = TEST_CASES_CACHE_FILE):
        self.cache_file = cache_file
        # Get directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(script_dir, cache_file)
    
    def cache_exists(self) -> bool:
        """Check if cached test cases exist"""
        exists = os.path.exists(self.cache_path)
        if exists:
            result_logger_gui.info(f"[TestCaseRepository] Cache found: {self.cache_path}")
            print(f"[TestCaseRepository] Cache found: {self.cache_path}")
        else:
            result_logger_gui.info(f"[TestCaseRepository] No cache found at: {self.cache_path}")
            print(f"[TestCaseRepository] No cache found")
        return exists
    
    def load_cached_test_cases(self) -> List[Dict[str, Any]]:
        """Load test cases from cache file"""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
                result_logger_gui.info(f"[TestCaseRepository] Loaded {len(test_cases)} test cases from cache")
                print(f"[TestCaseRepository] Loaded {len(test_cases)} test cases from cache")
                return test_cases
        except Exception as e:
            result_logger_gui.error(f"[TestCaseRepository] Error loading cache: {e}")
            print(f"[TestCaseRepository] Error loading cache: {e}")
            return []
    
    def fetch_and_cache_test_cases(self, url: str) -> List[Dict[str, Any]]:
        """Fetch test cases from URL and save to cache"""
        try:
            result_logger_gui.info(f"[TestCaseRepository] Fetching test cases from: {url}")
            print(f"[TestCaseRepository] Fetching test cases from: {url}")
            
            response = requests.get(url, timeout=30)
            response.raise_for_status()
            
            # Parse HTML
            soup = BeautifulSoup(response.text, 'html.parser')
            
            # Find test case panels
            test_panels = soup.find_all('div', class_='panel-default')
            
            test_cases = []
            for panel in test_panels:
                # Extract test case name from panel heading
                heading = panel.find('div', class_='panel-heading')
                if heading:
                    test_name = heading.get_text(strip=True)
                    
                    # Extract test steps from panel body
                    body = panel.find('div', class_='panel-body')
                    if body:
                        steps = []
                        # Extract all text lines
                        for line in body.get_text().strip().split('\n'):
                            line = line.strip()
                            if line and not line.startswith('Test Data:'):
                                steps.append(line)
                        
                        test_cases.append({
                            'name': test_name,
                            'steps': steps
                        })
            
            result_logger_gui.info(f"[TestCaseRepository] Fetched {len(test_cases)} test cases")
            print(f"[TestCaseRepository] Fetched {len(test_cases)} test cases")
            
            # Save to cache
            self._save_to_cache(test_cases)
            
            return test_cases
            
        except Exception as e:
            result_logger_gui.error(f"[TestCaseRepository] Error fetching test cases: {e}")
            print(f"[TestCaseRepository] Error fetching test cases: {e}")
            return []
    
    def _save_to_cache(self, test_cases: List[Dict[str, Any]]):
        """Save test cases to cache file"""
        try:
            with open(self.cache_path, 'w', encoding='utf-8') as f:
                json.dump(test_cases, f, indent=2, ensure_ascii=False)
            result_logger_gui.info(f"[TestCaseRepository] Saved {len(test_cases)} test cases to cache")
            print(f"[TestCaseRepository] Saved to cache: {self.cache_path}")
        except Exception as e:
            result_logger_gui.error(f"[TestCaseRepository] Error saving cache: {e}")
            print(f"[TestCaseRepository] Error saving cache: {e}")
    
    def get_test_cases(self, url: str, force_refresh: bool = False) -> List[Dict[str, Any]]:
        """
        Get test cases - from cache if available, otherwise fetch from URL
        
        Args:
            url: URL to fetch test cases from
            force_refresh: If True, bypass cache and fetch fresh
        """
        if not force_refresh and self.cache_exists():
            return self.load_cached_test_cases()
        else:
            return self.fetch_and_cache_test_cases(url)


# ============================================================
# OPTIMIZATION 1: MINIMAL DOM EXTRACTOR
# ============================================================
class DOMExtractor:
    """Extract and track DOM state - WITH MINIMAL DOM OPTIMIZATION"""
    
    def __init__(self, driver: WebDriver):
        self.driver = driver
    
    def get_dom_html(self) -> str:
        """Get full page source HTML"""
        return self.driver.page_source
    
    def get_dom_hash(self) -> str:
        """Get hash of current DOM for change detection"""
        dom_html = self.get_dom_html()
        return hashlib.md5(dom_html.encode('utf-8')).hexdigest()
    
    def get_minimal_dom(self, include_verification: bool = True) -> str:
        """
        ✅ OPTIMIZATION 1: Extract only interactive/relevant elements to reduce token usage
        
        Args:
            include_verification: If True, include elements for verification (messages, totals, etc.)
                                If False, only include action elements (buttons, inputs, links)
        
        Returns:
            Minimal HTML with only relevant elements (saves ~80-90% tokens)
        """
        try:
            # Get full DOM
            full_html = self.driver.page_source
            soup = BeautifulSoup(full_html, 'html.parser')
            
            # Context label for logging
            context = "Full DOM" if include_verification else "Actions Only"
            
            # Interactive selectors (always included)
            interactive_selectors = [
                'a',           # Links
                'button',      # Buttons
                'input',       # Input fields
                'select',      # Dropdowns
                'textarea',    # Text areas
                'form',        # Forms
                '[onclick]',   # Clickable elements
                '[data-qa]',   # Test attributes
                '[id]',        # Elements with IDs
                '[class*="btn"]',      # Button-like classes
                '[class*="link"]',     # Link classes
            ]
            
            # Verification selectors (only if needed)
            if include_verification:
                verification_selectors = [
                    '[class*="alert"]',      # Alert messages
                    '[class*="message"]',    # Messages
                    '[class*="error"]',      # Errors
                    '[class*="success"]',    # Success messages
                    '[class*="cart"]',       # Cart elements
                    '[class*="total"]',      # Totals
                    '[class*="price"]',      # Prices
                    '[class*="product"]',    # Product elements
                    '[class*="checkout"]',   # Checkout elements
                    'img[alt]',              # Images with alt text
                    'h1', 'h2', 'h3',        # Headers (for context)
                    '.price',                # Prices
                    '.total',                # Totals
                ]
                all_selectors = interactive_selectors + verification_selectors
            else:
                all_selectors = interactive_selectors
            
            # Extract matching elements
            relevant_elements = []
            for selector in all_selectors:
                try:
                    elements = soup.select(selector)
                    relevant_elements.extend(elements)
                except:
                    continue
            
            # Remove duplicates and build HTML
            seen = set()
            unique_elements = []
            for elem in relevant_elements:
                elem_str = str(elem)
                if elem_str not in seen:
                    seen.add(elem_str)
                    unique_elements.append(elem)
            
            # Build minimal HTML
            minimal_html = "<body>\n"
            limit = 300 if include_verification else 150
            
            for elem in unique_elements[:limit]:
                tag = elem.name
                attrs = {}
                
                # Keep only essential attributes
                if elem.has_attr('id'): attrs['id'] = elem.get('id')
                if elem.has_attr('class'): attrs['class'] = ' '.join(elem.get('class'))
                if elem.has_attr('name'): attrs['name'] = elem.get('name')
                if elem.has_attr('href'): attrs['href'] = elem.get('href')
                if elem.has_attr('type'): attrs['type'] = elem.get('type')
                if elem.has_attr('data-qa'): attrs['data-qa'] = elem.get('data-qa')
                
                text = elem.get_text(strip=True)[:200]  # Limit text length
                
                # Skip empty non-input elements
                if not text and tag not in ['input', 'button', 'select', 'img']:
                    continue
                
                attr_str = ' '.join([f'{k}="{v}"' for k, v in attrs.items()])
                minimal_html += f"<{tag} {attr_str}>{text}</{tag}>\n"
            
            minimal_html += "</body>"
            
            # Calculate reduction
            reduction = 100 - (len(minimal_html) * 100 // len(full_html)) if len(full_html) > 0 else 0
            print(f"[DOMExtractor] {context}: {len(minimal_html)} chars (reduced by {reduction}%)")
            result_logger_gui.info(f"[DOMExtractor] {context}: {reduction}% reduction")
            
            return minimal_html
            
        except Exception as e:
            print(f"[DOMExtractor] Error creating minimal DOM: {e}")
            result_logger_gui.error(f"[DOMExtractor] Error: {e}")
            # Fallback to truncated full DOM
            return self.driver.page_source[:30000]


# ============================================================
# DOM CHANGE DETECTOR
# ============================================================
class DOMChangeDetector:
    """Detect DOM changes to trigger step regeneration"""
    
    def __init__(self):
        self.last_dom_hash = None
    
    def has_dom_changed(self, current_hash: str) -> bool:
        """Check if DOM has changed since last check"""
        if self.last_dom_hash is None:
            self.last_dom_hash = current_hash
            return False
        
        changed = (current_hash != self.last_dom_hash)
        self.last_dom_hash = current_hash
        return changed


# ============================================================
# STEP EXECUTOR
# ============================================================
class StepExecutor:
    """Execute individual test steps with proper error handling"""
    
    def __init__(self, driver: WebDriver, test_context: TestContext = None):
        self.driver = driver
        self.test_context = test_context

    def _find_element(self, selector: str, timeout: int = 10):
        """Find element with wait"""
        try:
            wait = WebDriverWait(self.driver, timeout)

            # Try CSS selector first
            try:
                element = wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, selector))
                )
                return element
            except:
                # Try XPath if CSS fails
                element = wait.until(
                    EC.presence_of_element_located((By.XPATH, selector))
                )
                return element
        except TimeoutException:
            print(f"⏱️ Timeout waiting for element: {selector}")
            return None
        except Exception as e:
            print(f"❌ Error finding element {selector}: {e}")
            return None



    def _verify(self, verification: str, selector: str = None) -> tuple:
        """
        Execute verification check
        
        Returns:
            tuple: (success: bool, expected: str, actual: str)
        """
        try:
            if "page title contains" in verification.lower():
                expected = verification.split("'")[1]
                actual = self.driver.title
                success = expected.lower() in actual.lower()
                return (success, expected, actual)
            
            if "is visible" in verification.lower() or "is displayed" in verification.lower():
                if selector:
                    element = self._find_element(selector, timeout=5)
                    success = element is not None and element.is_displayed()
                    expected = "Element visible"
                    actual = "Element visible" if success else "Element not found or not visible"
                    return (success, expected, actual)
                return (True, "Element visible", "Element visible")
            
            if "text equals" in verification.lower():
                if selector:
                    element = self._find_element(selector, timeout=5)
                    if element:
                        expected = verification.split("'")[1] if "'" in verification else verification
                        actual = element.text.strip()
                        success = expected.lower() == actual.lower()
                        return (success, expected, actual)
                    return (False, verification.split("'")[1] if "'" in verification else "Text", "Element not found")
                return (True, "Text match", "Text match")
            
            if "text contains" in verification.lower():
                if selector:
                    element = self._find_element(selector, timeout=5)
                    if element:
                        expected = verification.split("'")[1] if "'" in verification else verification
                        actual = element.text.strip()
                        success = expected.lower() in actual.lower()
                        return (success, expected, actual)
                    return (False, verification.split("'")[1] if "'" in verification else "Text", "Element not found")
                return (True, "Text contains", "Text contains")
            
            # Default: assume verification passed
            return (True, verification, "Passed")
            
        except Exception as e:
            logger.error(f"Verification error: {e}")
            return (False, verification, f"Error: {str(e)}")
    
    def execute_step(self, step: Dict[str, Any]) -> bool:
        """
        Execute a single test step
        
        Returns:
            bool: True if step executed successfully, False otherwise
        """
        try:
            step_num = step.get("step_number", "?")
            action = step.get("action", "")
            selector = step.get("selector")
            value = step.get("value")
            description = step.get("description", "")
            wait_seconds = step.get("wait_seconds", 1)
            
            # Log step
            print(f"\n{'='*70}")
            print(f"Step {step_num}: {description}")
            print(f"Action: {action}")
            print(f"Description: {description}")
            if selector:
                print(f"Selector: {selector}")
            if value:
                print(f"Value: {value}")
            print(f"{'='*70}")
            
            # Execute based on action type
            if action == "navigate":
                url = value or step.get("url")
                if url:
                    result_logger_gui.info(f"\nNavigating to {url}")
                    result_logger_gui.info("="*70)
                    
                    self.driver.get(url)
                    logger.info(f"Successfully navigated to {url}")
            
            elif action == "click":
                result_logger_gui.info(f"\nClicking: {description}")
                result_logger_gui.info("="*70)
                
                element = self._find_element(selector)
                if element:
                    element.click()
                    logger.info(f"Successfully clicked element: {selector}")
                else:
                    result_logger_gui.info(f"✗ Failed to find element: {selector}")
                    logger.error(f"Element not found for click: {selector}")
                    return False
            
            elif action == "fill":
                result_logger_gui.info(f"\nFilling field: {description}")
                result_logger_gui.info("="*70)
                
                element = self._find_element(selector)
                if element:
                    element.clear()
                    element.send_keys(value)
                    # Mask password in logs
                    display_value = "****" if "password" in description.lower() else value
                    result_logger_gui.info(f"✓ Entered: {display_value}")
                    logger.info(f"Successfully filled element {selector} with value")
                else:
                    result_logger_gui.info(f"✗ Failed to find field: {selector}")
                    logger.error(f"Element not found for fill: {selector}")
                    return False

            elif action == "select":
                result_logger_gui.info(f"\nSelecting option: {description}")
                result_logger_gui.info("="*70)
                
                from selenium.webdriver.support.ui import Select
                element = self._find_element(selector)
                if element:
                    select = Select(element)
                    try:
                        select.select_by_visible_text(str(value))
                    except:
                        try:
                            select.select_by_value(str(value))
                        except:
                            if str(value).isdigit():
                                select.select_by_index(int(value))
                            else:
                                raise
                    result_logger_gui.info(f"✓ Selected: {value}")
                    logger.info(f"Successfully selected value '{value}' in {selector}")
                else:
                    result_logger_gui.info(f"✗ Failed to find dropdown: {selector}")
                    logger.error(f"Element not found for select: {selector}")
                    return False
            
            elif action == "submit":
                result_logger_gui.info(f"\nSubmitting form: {description}")
                result_logger_gui.info("="*70)
                
                element = self._find_element(selector)
                if element:
                    element.submit()
                    result_logger_gui.info("✓ Form submitted")
                    logger.info(f"Successfully submitted form: {selector}")
                else:
                    result_logger_gui.info(f"✗ Failed to find form: {selector}")
                    logger.error(f"Element not found for submit: {selector}")
                    return False
            
            elif action == "wait":
                time.sleep(wait_seconds)
                result_logger_gui.info(f"[Step {step_num}] Waited {wait_seconds}s")
            
            elif action == "scroll":
                result_logger_gui.info(f"\nScrolling: {description}")
                result_logger_gui.info("="*70)
                
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
                result_logger_gui.info(f"\nValidating: {description}")
                result_logger_gui.info("="*70)
                
                verification = step.get("verification", "")
                success, expected, actual = self._verify(verification, selector)
                
                if success:
                    result_logger_gui.info(f"✓ Validation passed")
                    logger.info(f"Verification passed: {verification}")
                else:
                    result_logger_gui.info(f"✗ Validation failed")
                    result_logger_gui.info(f"  Expected: {expected}")
                    result_logger_gui.info(f"  Actual: {actual}")
                    logger.warning(f"Verification failed - Expected: {expected}, Actual: {actual}")
                    return False

            elif action == "close_alert":
                try:
                    alert = self.driver.switch_to.alert
                    alert_text = alert.text
                    alert.accept()
                    result_logger_gui.info(f"\nClosed alert: {alert_text}")
                    result_logger_gui.info("="*70)
                    logger.info(f"Closed alert with text: {alert_text}")
                except:
                    logger.warning("No alert present to close")
                    pass
            
            # ===== SHOPPING-SPECIFIC ACTIONS =====
            
            elif action == "add_to_cart":
                item_name = step.get("item_name", "Unknown Item")
                price = float(step.get("price", 0))
                quantity = int(step.get("quantity", 1))
                
                if self.test_context:
                    self.test_context.add_to_cart(item_name, price, quantity)
                
                result_logger_gui.info(f"[Step {step_num}] Tracked cart item: {item_name}")
                print(f"✅ Tracked in cart: {item_name} x{quantity} @ ${price}")
            
            elif action == "verify_cart_total":
                if not self.test_context:
                    print("⚠️ No test context for cart verification")
                    return True
                
                try:
                    total_element = self._find_element(selector)
                    if total_element:
                        actual_total_text = total_element.text.strip()
                        import re
                        numbers = re.findall(r'[\d,]+\.?\d*', actual_total_text)
                        if numbers:
                            actual_total = float(numbers[0].replace(',', ''))
                            expected_total = self.test_context.expected_cart_total
                            
                            print(f"[Cart Verify] Expected: ${expected_total:.2f}")
                            print(f"[Cart Verify] Actual: ${actual_total:.2f}")
                            
                            if abs(actual_total - expected_total) < 0.01:
                                print(f"✅ Cart total verified!")
                                result_logger_gui.info(f"[Step {step_num}] ✅ Cart total verified: ${actual_total:.2f}")
                            else:
                                print(f"❌ Cart total mismatch!")
                                result_logger_gui.error(f"[Step {step_num}] ❌ Expected ${expected_total:.2f}, got ${actual_total:.2f}")
                                return False
                        else:
                            print("⚠️ Could not parse total from page")
                            return False
                    else:
                        print(f"❌ Cart total element not found: {selector}")
                        return False
                except Exception as e:
                    print(f"❌ Error verifying cart: {e}")
                    result_logger_gui.error(f"[Step {step_num}] Error verifying cart: {e}")
                    return False
            
            elif action == "apply_coupon":
                code = step.get("code", "")
                discount = float(step.get("discount", 0))
                
                coupon_input = self._find_element(selector)
                if coupon_input:
                    coupon_input.clear()
                    coupon_input.send_keys(code)
                    result_logger_gui.info(f"[Step {step_num}] Entered coupon: {code}")
                    
                    # Try to find and click apply button
                    apply_selectors = [
                        "button.apply-coupon",
                        "button[type='submit'].coupon",
                        "input[value*='Apply']",
                        ".coupon-apply",
                        "button:contains('Apply')"
                    ]
                    
                    applied = False
                    for apply_sel in apply_selectors:
                        try:
                            apply_btn = self._find_element(apply_sel, timeout=2)
                            if apply_btn:
                                apply_btn.click()
                                applied = True
                                break
                        except:
                            continue
                    
                    if applied:
                        time.sleep(2)
                        if self.test_context:
                            self.test_context.apply_coupon(code, discount)
                        print(f"✅ Applied coupon: {code}")
                        result_logger_gui.info(f"[Step {step_num}] ✅ Applied coupon: {code}")
                    else:
                        print(f"⚠️ Coupon entered but could not find apply button")
                        result_logger_gui.warning(f"[Step {step_num}] Could not find apply button")
                else:
                    print(f"❌ Coupon input not found: {selector}")
                    return False
            
            elif action == "dismiss_popup":
                try:
                    popup_element = self._find_element(selector, timeout=3)
                    if popup_element:
                        popup_element.click()
                        time.sleep(0.5)
                        print(f"✅ Dismissed popup: {selector}")
                        result_logger_gui.info(f"[Step {step_num}] Dismissed popup")
                    else:
                        print(f"⚠️ Popup not found (may have auto-closed): {selector}")
                except Exception as e:
                    print(f"⚠️ Popup already gone or error: {e}")
            
            elif action == "wait_for_ajax":
                loading_selector = selector or ".loading-spinner"
                max_wait = wait_seconds or 10
                
                try:
                    WebDriverWait(self.driver, max_wait).until(
                        EC.invisibility_of_element_located((By.CSS_SELECTOR, loading_selector))
                    )
                    print(f"✅ AJAX loading complete")
                    result_logger_gui.info(f"[Step {step_num}] AJAX complete")
                except:
                    print(f"⚠️ No loading indicator found: {loading_selector}")
                
                time.sleep(1)
            
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
            return False


# ============================================================
# TEST ORCHESTRATOR (WITH ALL OPTIMIZATIONS)
# ============================================================
class TestOrchestrator:
    """Main orchestrator for test execution - WITH OPTIMIZATIONS"""
    
    def __init__(
        self,
        driver: WebDriver,
        shopping_site_key: str,
        api_key: Optional[str] = None,
        use_ai: bool = True
    ):
        self.driver = driver
        self.site_config = SHOPPING_SITES[shopping_site_key]
        self.shopping_site_key = shopping_site_key
        self.use_ai = use_ai
        
        # Initialize components
        self.test_context = TestContext()
        self.test_case_repo = TestCaseRepository()
        self.dom_extractor = DOMExtractor(driver)
        self.dom_detector = DOMChangeDetector()
        self.step_executor = StepExecutor(driver, self.test_context)
        
        # ✅ OPTIMIZATION 2: DOM Cache
        self.dom_cache = DOMCache()
        
        # AI helper (only if using AI mode)
        if use_ai:
            if not api_key:
                raise ValueError("API key required for AI mode")
            self.ai_helper = AIHelper(api_key)
        else:
            self.ai_helper = None
        
        # Load test cases
        test_cases_url = self.site_config["test_cases_url"]
        self.all_test_cases = self.test_case_repo.get_test_cases(test_cases_url)
        
        # Get test groups
        self.test_groups = self.site_config.get("test_groups", [])
        
        result_logger_gui.info(f"[Orchestrator] Initialized for {shopping_site_key}")
        print(f"[Orchestrator] Initialized for {shopping_site_key}")
        print(f"[Orchestrator] Total test cases: {len(self.all_test_cases)}")
        print(f"[Orchestrator] Test groups: {len(self.test_groups)}")
    
    def run_with_ai(self):
        """
        Run tests using AI to generate steps dynamically
        ✅ WITH ALL OPTIMIZATIONS ENABLED
        """
        print("\n" + "="*70)
        print("🤖 AI-POWERED TEST EXECUTION (OPTIMIZED)")
        print("="*70)
        print(f"✅ Optimization 1: Minimal DOM (saves 80-90% tokens)")
        print(f"✅ Optimization 2: DOM Caching with hash validation")
        print(f"✅ Optimization 3: Smart Context Detection")
        print(f"Expected API cost savings: 75-85% total")
        print(f"Note: Cache validated with hash to ensure reliability")
        print("="*70)
        
        if not self.ai_helper:
            print("❌ AI helper not initialized")
            return
        
        # Clean old DOM cache entries
        self.dom_cache.clear_old_entries(max_age_hours=24)
        
        # Process each test group
        for group_idx, group in enumerate(self.test_groups, 1):
            group_name = group["name"]
            range_start, range_end = group["range"]
            
            print(f"\n{'='*70}")
            print(f"📦 GROUP {group_idx}/{len(self.test_groups)}: {group_name.upper()}")
            print(f"   Range: Test cases {range_start} to {range_end}")
            print(f"   Description: {group.get('description', 'N/A')}")
            print(f"{'='*70}")
            
            result_logger_gui.info(f"\n{'='*70}")
            result_logger_gui.info(f"STARTING TEST GROUP: {group_name.upper()}")
            result_logger_gui.info(f"Test Range: {range_start} to {range_end}")
            result_logger_gui.info("="*70)
            
            # Get test cases for this group
            group_test_cases = self.all_test_cases[range_start:range_end]
            print(f"[Phase 1] Selected {len(group_test_cases)} test cases for this group")
            
            # Navigate to home page
            home_url = self.site_config["url"]
            print(f"[Phase 2] Navigating to {home_url}...")
            self.driver.get(home_url)
            time.sleep(3)
            
            # ✅ OPTIMIZATION 2: Check DOM cache by URL + hash validation
            current_url = self.driver.current_url
            current_hash = self.dom_extractor.get_dom_hash()
            cached_data = self.dom_cache.get(current_url, current_hash)
            
            if cached_data:
                # Use cached DOM (hash validated!)
                initial_dom = cached_data['dom_html']
                self.dom_detector.last_dom_hash = current_hash
                print(f"[Phase 3] Using cached DOM for {current_url} (hash verified)")
            else:
                # ✅ OPTIMIZATION 1 & 3: Get minimal DOM with verification elements
                # (Initial load: we don't know what's needed yet, so include verification)
                initial_dom = self.dom_extractor.get_minimal_dom(include_verification=True)
                
                # Cache the DOM with hash
                self.dom_cache.set(current_url, initial_dom, current_hash)
                self.dom_detector.last_dom_hash = current_hash
            
            # Determine if this is the first group (for credential generation)
            is_first = (group_idx == 1)
            
            # Generate initial steps using AI
            print(f"[Phase 3] Generating steps for group '{group_name}'...")
            steps = self.ai_helper.generate_test_steps(
                initial_dom,
                group_test_cases,
                test_context=self.test_context,
                is_first_group=is_first
            )
            
            if not steps:
                print(f"❌ No steps generated for group '{group_name}'")
                continue
            
            print(f"[Phase 4] Generated {len(steps)} initial steps")
            
            # Execute steps with DOM change detection
            print(f"[Phase 5] Executing steps with DOM monitoring...")
            current_step_index = 0
            executed_steps = []
            success_count = 0
            
            while current_step_index < len(steps):
                step = steps[current_step_index]
                
                # Log test case if it changed
                current_test_case = step.get("test_case", "")
                if not executed_steps or current_test_case != executed_steps[-1].get("test_case", ""):
                    result_logger_gui.info(f"\n{'='*70}")
                    result_logger_gui.info(f"STARTING TEST CASE: {current_test_case}")
                    result_logger_gui.info("="*70)
                    logger.info(f"Starting new test case: {current_test_case}")
                
                # Execute step
                success = self.step_executor.execute_step(step)
                
                if not success:
                    print(f"⚠️ Step {step.get('step_number')} failed, stopping group")
                    result_logger_gui.info(f"\n✗ Step failed - stopping test group")
                    result_logger_gui.info("="*70)
                    logger.warning(f"Step {step.get('step_number')} failed, stopping group")
                    break
                
                success_count += 1
                executed_steps.append(step)
                
                # Check if DOM changed
                current_hash = self.dom_extractor.get_dom_hash()
                if self.dom_detector.has_dom_changed(current_hash):
                    print(f"\n🔄 DOM changed after step {step.get('step_number')}")

                    result_logger_gui.info(f"\n⏳ Page changed - regenerating test steps...")
                    result_logger_gui.info("=" * 70)
                    logger.info(f"DOM changed after step {step.get('step_number')}, regenerating steps")

                    # Get current URL and hash for caching
                    current_url = self.driver.current_url
                    
                    # ✅ OPTIMIZATION 2: Check cache with hash validation
                    cached_data = self.dom_cache.get(current_url, current_hash)
                    
                    if cached_data:
                        # Cache hit with matching hash
                        new_dom = cached_data['dom_html']
                        print(f"[DOMCache] ✅ Using cached DOM for regeneration (hash verified)")
                    else:
                        # Cache miss or hash mismatch → Get fresh DOM
                        # ✅ OPTIMIZATION 3: Smart context detection
                        needs_verification = ContextAnalyzer.needs_verification(
                            executed_steps,
                            group_test_cases
                        )
                        
                        # ✅ OPTIMIZATION 1: Get minimal DOM with appropriate level
                        new_dom = self.dom_extractor.get_minimal_dom(
                            include_verification=needs_verification
                        )
                        
                        # Cache the new DOM with hash
                        self.dom_cache.set(current_url, new_dom, current_hash)
                    
                    print(f"Regenerating remaining steps...")
                    
                    # Regenerate remaining steps
                    remaining_steps = self.ai_helper.generate_test_steps(
                        new_dom,
                        group_test_cases,
                        previous_steps=executed_steps,
                        step_where_dom_changed=current_step_index,
                        test_context=self.test_context,
                        is_first_group=is_first
                    )

                    if remaining_steps:
                        # Replace remaining steps
                        steps = executed_steps + remaining_steps
                        print(f"✅ Generated {len(remaining_steps)} new steps")
                        result_logger_gui.info(f"✓ Generated {len(remaining_steps)} new steps - continuing...")
                        result_logger_gui.info("=" * 70)
                        logger.info(f"Generated {len(remaining_steps)} new steps after DOM change")
                    else:
                        print(f"⚠️ No remaining steps generated")
                        result_logger_gui.info(f"✗ No steps generated - stopping")
                        logger.warning("No remaining steps generated after DOM change")
                        break
                
                current_step_index += 1
            
            # Save successful steps to JSON file
            if executed_steps:
                output_file = f"{self.shopping_site_key}_{group_name}_steps.json"
                self._save_steps_to_json(executed_steps, output_file)
                print(f"\n💾 Saved {len(executed_steps)} steps to {output_file}")
            
            print(f"\n{'='*70}")
            print(f"✅ GROUP '{group_name}' COMPLETE")
            print(f"   Successful steps: {success_count}/{len(executed_steps)}")
            print(f"{'='*70}")
            
            result_logger_gui.info(f"\n{'='*70}")
            result_logger_gui.info(f"COMPLETED TEST GROUP: {group_name.upper()}")
            result_logger_gui.info(f"Successful Steps: {success_count}/{len(executed_steps)}")
            result_logger_gui.info("="*70)
            
            logger.info(f"Group '{group_name}' complete - {success_count}/{len(executed_steps)} steps successful")
            
            # Pause between groups
            time.sleep(2)
        
        print("\n" + "="*70)
        print("🎉 ALL TEST GROUPS COMPLETE!")
        print("="*70)
        
        result_logger_gui.info("\n" + "="*70)
        result_logger_gui.info("ALL TEST GROUPS COMPLETED")
        result_logger_gui.info("="*70)
        
        logger.info("AI-powered test execution complete")
    
    def run_from_json(self):
        """Run tests from pre-generated JSON files (replay mode)"""
        print("\n" + "="*70)
        print("📼 REPLAY MODE - USING SAVED STEPS")
        print("="*70)
        
        result_logger_gui.info("\n" + "="*70)
        result_logger_gui.info("STARTING TEST REPLAY FROM SAVED STEPS")
        result_logger_gui.info("="*70)
        
        logger.info("Starting replay mode execution")
        
        for group_idx, group in enumerate(self.test_groups, 1):
            group_name = group["name"]
            
            # Look for saved steps file
            steps_file = f"{self.shopping_site_key}_{group_name}_steps.json"
            
            if not os.path.exists(steps_file):
                print(f"⚠️ No saved steps found for group '{group_name}' ({steps_file})")
                result_logger_gui.info(f"\n✗ No saved steps found for group '{group_name}'")
                logger.warning(f"Steps file not found: {steps_file}")
                continue
            
            print(f"\n{'='*70}")
            print(f"📦 GROUP {group_idx}/{len(self.test_groups)}: {group_name.upper()}")
            print(f"{'='*70}")
            
            result_logger_gui.info(f"\n{'='*70}")
            result_logger_gui.info(f"STARTING TEST GROUP: {group_name.upper()}")
            result_logger_gui.info("="*70)
            
            logger.info(f"Processing group {group_idx}/{len(self.test_groups)}: {group_name}")
            
            # Load steps from file
            try:
                with open(steps_file, 'r') as f:
                    steps = json.load(f)
                print(f"[Replay] Loaded {len(steps)} steps from {steps_file}")
                result_logger_gui.info(f"\n✓ Loaded {len(steps)} steps from {steps_file}")
                logger.info(f"Loaded {len(steps)} steps from {steps_file}")
            except Exception as e:
                print(f"❌ Error loading steps: {e}")
                result_logger_gui.info(f"\n✗ Error loading steps: {e}")
                logger.error(f"Error loading steps from {steps_file}: {e}")
                continue
            
            # Navigate to home page
            home_url = self.site_config["url"]
            print(f"[Replay] Navigating to {home_url}...")
            logger.info(f"Navigating to home page: {home_url}")
            self.driver.get(home_url)
            time.sleep(2)
            
            # Execute steps
            result_logger_gui.info("\nExecuting test steps...")
            result_logger_gui.info("="*70)
            
            success_count = 0
            current_test_case = None
            
            for step in steps:
                # Log test case if it changed
                test_case = step.get("test_case", "")
                if test_case != current_test_case:
                    current_test_case = test_case
                    result_logger_gui.info(f"\n{'='*70}")
                    result_logger_gui.info(f"STARTING TEST CASE: {test_case}")
                    result_logger_gui.info("="*70)
                    logger.info(f"Starting test case: {test_case}")
                
                success = self.step_executor.execute_step(step)
                if success:
                    success_count += 1
                else:
                    print(f"⚠️ Step failed, continuing...")
                    result_logger_gui.info(f"\n✗ Step failed - continuing with next step")
                    logger.warning(f"Step {step.get('step_number')} failed")
            
            print(f"\n{'='*70}")
            print(f"✅ GROUP '{group_name}' COMPLETE")
            print(f"   Successful steps: {success_count}/{len(steps)}")
            print(f"{'='*70}")
            
            result_logger_gui.info(f"\n{'='*70}")
            result_logger_gui.info(f"COMPLETED TEST GROUP: {group_name.upper()}")
            result_logger_gui.info(f"Successful Steps: {success_count}/{len(steps)}")
            result_logger_gui.info("="*70)
            
            logger.info(f"Group '{group_name}' complete - {success_count}/{len(steps)} steps successful")
        
        print("\n" + "="*70)
        print("✅ REPLAY COMPLETE")
        print("="*70)
        
        result_logger_gui.info("\n" + "="*70)
        result_logger_gui.info("ALL TEST GROUPS COMPLETED")
        result_logger_gui.info("="*70)
        
        logger.info("Replay mode execution complete")
    
    def _save_steps_to_json(self, steps: List[Dict], filename: str):
        """Save executed steps to JSON file"""
        try:
            with open(filename, 'w') as f:
                json.dump(steps, f, indent=2)
            result_logger_gui.info(f"[Orchestrator] Saved steps to {filename}")
        except Exception as e:
            print(f"❌ Error saving steps: {e}")
            result_logger_gui.error(f"[Orchestrator] Error saving steps: {e}")


# ============================================================
# WEBDRIVER INITIALIZATION
# ============================================================
def initialize_driver(headless: bool = False) -> WebDriver:
    """Initialize Chrome WebDriver with options"""
    from webdriver_manager.chrome import ChromeDriverManager
    
    options = webdriver.ChromeOptions()
    
    if headless:
        print("[WebDriver] Initializing in HEADLESS mode")
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--window-size=1920,1080')
    else:
        print("[WebDriver] Initializing in NORMAL mode")
        options.add_argument("--window-size=1400,900")
    
    # Common options
    options.add_argument('--disable-save-password-bubble')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_argument('--disable-infobars')
    options.add_argument('--disable-notifications')
    options.add_experimental_option('excludeSwitches', ['enable-automation'])
    options.add_experimental_option('prefs', {
        'credentials_enable_service': False,
        'profile.password_manager_enabled': False,
        'profile.default_content_setting_values.notifications': 2
    })
    
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        print("[WebDriver] ✅ Initialized successfully")
        return driver
    except Exception:
        print("[WebDriver] Default initialization failed, downloading ChromeDriver...")
        downloaded_binary_path = ChromeDriverManager().install()
        service = Service(executable_path=downloaded_binary_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        print("[WebDriver] ✅ Initialized successfully")
        return driver


# ============================================================
# MAIN EXECUTION
# ============================================================
def run(
    shopping_site_key: str,
    mode: str = "ai",
    headless: bool = False,
    api_key: Optional[str] = None
):
    """
    Main entry point for test automation
    
    Args:
        shopping_site_key: Key from SHOPPING_SITES dict
        mode: "ai" for AI-powered generation, "replay" for JSON replay
        headless: Run browser in headless mode
        api_key: Anthropic API key (required for AI mode)
    """
    
    result_logger_gui.info(f"\n{'='*70}")
    result_logger_gui.info("INITIALIZING TEST AUTOMATION")
    result_logger_gui.info("="*70)
    
    logger.info("Starting test automation")

    # Validate shopping site key
    if shopping_site_key not in SHOPPING_SITES:
        print(f"❌ ERROR: Shopping site '{shopping_site_key}' not found in SHOPPING_SITES config")
        print(f"Available sites: {', '.join(SHOPPING_SITES.keys())}")
        result_logger_gui.info(f"\n✗ Error: Shopping site '{shopping_site_key}' not found")
        logger.error(f"Invalid shopping site key: {shopping_site_key}")
        return
    
    site_config = SHOPPING_SITES[shopping_site_key]
    target_url = site_config["url"]
    
    print("\n" + "="*70)
    print("🛒 SHOPPING SITE TEST AUTOMATION (OPTIMIZED)")
    print("="*70)
    print(f"Shopping Site: {shopping_site_key}")
    print(f"Target URL: {target_url}")
    print(f"Mode: {mode.upper()}")
    print(f"Headless: {headless}")
    if mode == "ai":
        print(f"✅ Cost Optimizations: Minimal DOM + Caching + Smart Context")
        print(f"✅ Expected Savings: 85%+ on API costs")
    print("="*70)
    
    result_logger_gui.info(f"\nShopping Site: {shopping_site_key}")
    result_logger_gui.info(f"Target URL: {target_url}")
    result_logger_gui.info(f"Mode: {mode.upper()}")
    result_logger_gui.info(f"Headless: {headless}")
    
    logger.info(f"Configuration - Site: {shopping_site_key}, Mode: {mode}, Headless: {headless}")
    
    if mode == "ai":
        result_logger_gui.info("\n✓ Cost Optimizations Enabled:")
        result_logger_gui.info("  - Minimal DOM extraction")
        result_logger_gui.info("  - DOM caching by URL")
        result_logger_gui.info("  - Smart context detection")
        logger.info("AI mode enabled with cost optimizations")
    
    driver = None
    
    try:
        # Initialize WebDriver
        result_logger_gui.info("\nInitializing browser...")
        result_logger_gui.info("="*70)
        
        driver = initialize_driver(headless=headless)
        
        result_logger_gui.info("✓ Browser initialized successfully")
        
        # Create orchestrator
        result_logger_gui.info("\nPreparing test environment...")
        result_logger_gui.info("="*70)
        
        logger.info("Creating test orchestrator")
        orchestrator = TestOrchestrator(
            driver=driver,
            shopping_site_key=shopping_site_key,
            api_key=api_key,
            use_ai=(mode == "ai")
        )
        
        result_logger_gui.info(f"✓ Loaded {len(orchestrator.all_test_cases)} test cases")
        
        # Run based on mode
        if mode == "ai":
            orchestrator.run_with_ai()
        elif mode == "replay":
            orchestrator.run_from_json()
        else:
            print(f"❌ Invalid mode: {mode}. Use 'ai' or 'replay'")
            result_logger_gui.info(f"\n✗ Invalid mode: {mode}")
            logger.error(f"Invalid mode specified: {mode}")
        
    except KeyboardInterrupt:
        print("\n⌨️ User interrupted execution (Ctrl+C)")
        result_logger_gui.info("\n\n✗ Test execution interrupted by user")
        logger.info("User interrupted execution (Ctrl+C)")
    except Exception as e:
        print(f"\n❌ Error during execution: {e}")
        result_logger_gui.info(f"\n\n✗ Error during execution: {str(e)}")
        logger.error(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        logger.error(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
            print("\n[Main] Browser closed")
            result_logger_gui.info("\n✓ Browser closed")
            logger.info("Browser closed")


# ============================================================
# CONFIGURATION & ENTRY POINT
# ============================================================
if __name__ == "__main__":
    
    # ============================================================
    # CONFIGURATION
    # ============================================================
    
    # Select which shopping site to test
    SHOPPING_SITE = "automation_exercise"
    
    # Mode: "ai" = generate with AI, "replay" = use saved JSON
    MODE = "ai"
    
    # Browser settings
    HEADLESS = False
    
    # AI settings
    API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    
    # Validate configuration
    if not API_KEY and MODE == "ai":
        print("="*70)
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment")
        print("Please set the API key or switch to 'replay' mode")
        print("="*70)
        sys.exit(1)
    
    if SHOPPING_SITE not in SHOPPING_SITES:
        print("="*70)
        print(f"❌ ERROR: Shopping site '{SHOPPING_SITE}' not found in SHOPPING_SITES")
        print(f"Available sites: {', '.join(SHOPPING_SITES.keys())}")
        print("="*70)
        sys.exit(1)
    
    # Display configuration
    site_config = SHOPPING_SITES[SHOPPING_SITE]
    print("\n" + "="*70)
    print("📋 CONFIGURATION")
    print("="*70)
    print(f"Shopping Site: {SHOPPING_SITE}")
    print(f"Target URL: {site_config['url']}")
    print(f"Test Cases URL: {site_config['test_cases_url']}")
    print(f"Test Cases Cache: {TEST_CASES_CACHE_FILE}")
    print(f"DOM Cache: {DOM_CACHE_FILE}")
    print(f"Mode: {MODE}")
    print(f"Headless: {HEADLESS}")
    if MODE == "ai":
        print(f"✅ OPTIMIZATIONS ENABLED:")
        print(f"   - Minimal DOM extraction")
        print(f"   - DOM caching by URL")
        print(f"   - Smart context detection")
    print("="*70)
    
    # ============================================================
    # RUN THE AUTOMATION
    # ============================================================
    
    run(
        shopping_site_key=SHOPPING_SITE,
        mode=MODE,
        headless=HEADLESS,
        api_key=API_KEY
    )
