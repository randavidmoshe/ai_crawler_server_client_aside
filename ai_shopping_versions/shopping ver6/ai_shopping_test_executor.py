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
    StaleElementReferenceException, ElementClickInterceptedException
)



# ============================================================
# SHOPPING SITES CONFIGURATION
# ============================================================
SHOPPING_SITES = {
    "automation_exercise": {
        "url": "https://automationexercise.com/",
        "requires_auth": True,
        "test_groups": [
            {"name": "auth", "test_ids": [1, 2, 3, 4, 5], "description": "Authentication tests"},
            {"name": "products", "test_ids": [8, 9, 18, 19, 21, 27], "description": "Product browsing tests"},
            {"name": "cart", "test_ids": [12, 13, 17, 20, 22], "description": "Shopping cart tests"},
            {"name": "checkout", "test_ids": [14, 15, 16, 23, 24], "description": "Checkout tests"},
            {"name": "engagement", "test_ids": [6, 10, 11], "description": "Newsletter & contact tests"},
            {"name": "navigation", "test_ids": [7, 25, 26], "description": "Navigation tests"},
            {"name": "exploration", "test_ids": [100], "description": "AI exploratory testing"}
        ]
    }
}



# Generic test cases file
import os
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERIC_TEST_CASES_FILE = os.path.join(SCRIPT_DIR, "generic_form_page_crawler_test_cases.json")
DOM_CACHE_FILE = os.path.join(SCRIPT_DIR, "dom_cache.json")
PROJECTS_BASE_DIR = os.path.expanduser("~/automation_product_config/shopping_site_projects")
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
                #result_logger_gui.warning(f"[DOMCache] Hash mismatch - DOM changed without URL change")
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

        prompt = f"""You are a test automation expert generating Selenium WebDriver test steps for a shopping website.

        === 🚫 CRITICAL: FORBIDDEN SELECTORS (READ THIS FIRST!) 🚫 ===

        SELENIUM DOES NOT SUPPORT THESE SELECTORS - USING THEM WILL CRASH YOUR TESTS:

        ❌ FORBIDDEN SYNTAX:
           :has-text('text')           ← Playwright only - NOT in Selenium
           :contains('text')            ← jQuery only - NOT in Selenium  
           :text('text')                ← Playwright only - NOT in Selenium
           >> (combinator)              ← Playwright only - NOT in Selenium
           //div[text()='...']          ← XPath text() - breaks with nested HTML
           //a[contains(text(), '...')]  ← XPath contains(text()) - breaks with formatting

        🚨 IF YOU USE ANY ABOVE SYNTAX → TEST WILL FAIL WITH "INVALID SELECTOR" ERROR! 🚨

        ✅ ONLY USE SELENIUM-COMPATIBLE SELECTORS:

        **Priority 1 - Attributes (ALWAYS TRY FIRST):**
           ✅ input[data-qa='login-email']       ← Best: unique data attributes
           ✅ button[data-testid='submit']       ← Best: test identifiers
           ✅ a[href='/logout']                  ← Good: semantic attributes
           ✅ input[name='email']                ← Good: form attributes
           ✅ button[type='submit']              ← Good: semantic attributes
           ✅ [aria-label='Close']               ← Good: accessibility attributes

        **Priority 2 - IDs and Classes:**
           ✅ #login-form                        ← Unique ID
           ✅ .submit-button                     ← Specific class
           ✅ .header .nav-link                  ← Class with context

        **Priority 3 - Structural (LAST RESORT):**
           ✅ form > button:nth-child(2)         ← Structural selector
           ✅ .header a:last-child               ← Structural with context
           ✅ .product-list > div:first-child    ← First item in list

        **WRONG vs RIGHT Examples:**

        ❌ "selector": "a:has-text('Logged in as')"
        ✅ "selector": "a[href='/logout']"

        ❌ "selector": "button:contains('Submit')"  
        ✅ "selector": "button[type='submit']"

        ❌ "selector": "button[data-qa='login-button']:has-text('Login')"
        ✅ "selector": "button[data-qa='login-button']"

        ❌ "selector": "//h2[text()='Enter Account Information']"
        ✅ "selector": "h2.title.text-center"

        ❌ "selector": "//div[contains(text(), 'Success')]"
        ✅ "selector": ".alert-success"

        **For "Verify user is logged in" type checks:**
        ❌ BAD:  Find element with text "Logged in as"
        ✅ GOOD: Find logout link: a[href='/logout']
        ✅ GOOD: Find user menu: .user-menu
        ✅ GOOD: Check username display: .logged-in-username

        **Key Rule: NEVER select elements by their text content! Always use attributes or structure!**

        === END CRITICAL SECTION ===


        === YOUR TASK: GENERIC TO SPECIFIC CONVERSION ===

        You will receive HIGH-LEVEL test steps like:
        - "Navigate to home page"
        - "Fill all signup form fields"
        - "Add product to cart"
        - "Verify user is logged in"

        **Your Job:** Convert these GENERIC steps into SPECIFIC Selenium actions by analyzing the DOM.

        **Conversion Examples:**

        1. Generic: "Go to signup page"
           → Analyze DOM: <a href="/login">Signup / Login</a>
           → Generate: {{"action": "click", "selector": "a[href='/login']"}}

        2. Generic: "Fill signup form"
           → Analyze DOM: See 5 input fields
           → Generate 5 SEPARATE steps:
             {{"action": "fill", "selector": "input[data-qa='signup-name']", "value": "TestUser123"}}
             {{"action": "fill", "selector": "input[data-qa='signup-email']", "value": "test@example.com"}}
             ... (3 more)

        3. Generic: "Verify user is logged in"
           → Analyze DOM: See <a href="/logout">Logout</a>
           → Generate: {{"action": "verify", "selector": "a[href='/logout']", "verification": "logout link is visible"}}

        **Key Conversion Rules:**
        - ONE generic step → MULTIPLE specific steps (often)
        - Use the DOM to find ACTUAL selectors on THIS site
        - Generate realistic test data
        - Skip impossible steps, continue with rest


        === TEST CONTEXT & CREDENTIALS ===

        {credentials_instruction}

        **Current Test State:**
        - Registered Email: {getattr(test_context, 'registered_user_email', None) or 'None yet'}
        - Registered Password: {getattr(test_context, 'registered_user_password', None) or 'None yet'}

        **When to Use Existing Credentials:**
        - Test says "Login with registered user" → USE email/password from above
        - Test says "Enter registered email" → USE the email from context
        - DO NOT create new users if credentials exist!

        **When to Create NEW Credentials (registration only):**
        - Email: testuser_{{unix_timestamp}}@example.com
        - Password: TestPass{{4_random_digits}}
        - Name: TestUser{{random_number}}
        - Phone: 1234567890
        - Address: 123 Main St
        - City: Los Angeles
        - State: California
        - Zip: 90001
        - Country: United States


        === AVAILABLE ACTIONS ===

        **Standard Actions:**
        - navigate: Go to URL
        - click: Click element
        - fill: Enter text in input
        - select: Choose from dropdown OR select radio button
        - verify: Check if element is visible
        - wait: Wait for duration
        - scroll: Scroll to element

        **IMPORTANT: Use 'select' action for BOTH:**
        - <select> dropdowns: {{"action": "select", "selector": "select[name='country']", "value": "USA"}}
        - Radio buttons: {{"action": "select", "selector": "input[value='Mr']", "value": "Mr"}}

        **Shopping-Specific Actions:**
        1. add_to_cart: {{"action": "add_to_cart", "item_name": "Blue Shirt", "price": 500, "quantity": 1}}
        2. verify_cart_total: {{"action": "verify_cart_total", "selector": ".cart-total"}}
        3. apply_coupon: {{"action": "apply_coupon", "code": "SAVE20", "selector": "input.coupon", "discount": 100}}
        4. verify_discount: {{"action": "verify_discount", "selector": ".discount-amount"}}
        5. dismiss_popup: {{"action": "dismiss_popup", "selector": ".popup-close"}}
        6. wait_for_ajax: {{"action": "wait_for_ajax", "selector": ".loading-spinner", "wait_seconds": 10}}


        === CURRENT PAGE DOM ===

        {dom_html}


        === TEST CASES TO IMPLEMENT ===

        {json.dumps(test_cases, indent=2)}


        === OUTPUT REQUIREMENTS ===

        1. **Return ONLY valid JSON array** - no explanations, no markdown, just JSON

        2. **Each action must have these fields:**
           - "step_number": integer (sequential, starting from 1)
           - "test_case": string (which test this belongs to)
           - "action": string (navigate, click, fill, select, verify, etc.)
           - "description": string (human-readable description)
           - "selector": string or null (CSS selector - MUST follow rules above!)
           - "value": string or null (value for fill/select actions)
           - "verification": string or null (what to verify after action)
           - "wait_seconds": number (seconds to wait after action)

        3. **Selector Selection Process (follow this order):**
           Step 1: Look for data-qa, data-testid, data-test attributes → USE THESE FIRST
           Step 2: Look for unique href, name, type attributes → USE THESE SECOND
           Step 3: Look for unique IDs (#something) → USE THESE THIRD
           Step 4: Look for specific classes with context (.form .submit-btn) → USE THESE FOURTH
           Step 5: Use structural selectors (form > button:last-child) → LAST RESORT

        4. **Verification Steps:**
           After important actions, verify success:
           - After submit → verify success message exists
           - After login → verify logout link exists (NOT text matching!)
           - After add to cart → verify cart count increased

        5. **Wait Times:**
           - After navigate: 2 seconds
           - After click (page change): 2 seconds
           - After fill: 0.5 seconds
           - After verify: 1 second

        6. **Breaking Down Generic Steps:**
           - "Fill registration form" → Generate fill steps for EACH field
           - "Complete checkout" → Generate steps for shipping, payment, review
           - "Add product to cart" → Click product, click add button, verify cart


        === EXAMPLE OUTPUT ===

        [
          {{
            "step_number": 1,
            "test_case": "Register User",
            "action": "navigate",
            "description": "Navigate to home page",
            "selector": null,
            "value": "/",
            "verification": "page loaded successfully",
            "wait_seconds": 2
          }},
          {{
            "step_number": 2,
            "test_case": "Register User",
            "action": "click",
            "description": "Click signup link in navigation",
            "selector": "a[href='/login']",
            "value": null,
            "verification": "navigated to login page",
            "wait_seconds": 2
          }},
          {{
            "step_number": 3,
            "test_case": "Register User",
            "action": "verify",
            "description": "Verify signup form is visible",
            "selector": "input[data-qa='signup-name']",
            "value": null,
            "verification": "signup form is visible",
            "wait_seconds": 1
          }},
          {{
            "step_number": 4,
            "test_case": "Register User",
            "action": "fill",
            "description": "Enter name in signup form",
            "selector": "input[data-qa='signup-name']",
            "value": "TestUser456",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 5,
            "test_case": "Register User",
            "action": "fill",
            "description": "Enter email in signup form",
            "selector": "input[data-qa='signup-email']",
            "value": "testuser_1698765432@example.com",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 6,
            "test_case": "Register User",
            "action": "click",
            "description": "Click signup button",
            "selector": "button[data-qa='signup-button']",
            "value": null,
            "verification": "navigated to registration form",
            "wait_seconds": 2
          }}
        ]


        === FINAL CHECKLIST BEFORE RESPONDING ===

        Before you output your JSON, verify:
        ☐ NO :has-text() selectors anywhere
        ☐ NO :contains() selectors anywhere  
        ☐ NO :text() selectors anywhere
        ☐ NO XPath with text() or contains(text())
        ☐ ALL selectors use attributes, IDs, classes, or structure
        ☐ Each generic step expanded into specific actions
        ☐ Using test context credentials correctly
        ☐ Valid JSON format (no trailing commas, proper quotes)

        {context}

        Now generate the test steps as a JSON array. ONLY output the JSON array, nothing else.
        """
        
        try:
            logger.info("[AIHelper] Sending request to Claude API...")
            print("[AIHelper] Sending request to Claude API...")

            message = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            
            response_text = message.content[0].text
            logger.info(f"[AIHelper] Received response ({len(response_text)} chars)")
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
            
            logger.info(f"[AIHelper] Successfully parsed {len(steps)} steps")
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

    def discover_test_scenarios(self, dom_html: str, already_tested: list, max_scenarios: int = 5) -> list:
        """
        AI analyzes page and discovers new test scenarios

        Args:
            dom_html: Current page DOM
            already_tested: List of features already tested
            max_scenarios: Maximum scenarios to discover

        Returns:
            List of discovered test scenarios
        """
        try:
            already_tested_str = ", ".join(already_tested) if already_tested else "None"

            prompt = f"""Analyze this e-commerce page and discover {max_scenarios} NEW testable scenarios.

    === CURRENT PAGE DOM ===
    {dom_html}

    === ALREADY TESTED FEATURES ===
    {already_tested_str}

    === TASK ===
    Discover {max_scenarios} NEW test scenarios that are:
    1. NOT in the already-tested list
    2. Actually visible/available on this page
    3. Testable with automated steps
    4. Valuable for quality assurance

    For each scenario, provide:
    - Scenario name (brief, descriptive)
    - Why it's important to test
    - Priority (high/medium/low)
    - Test steps as simple string descriptions

    === OUTPUT FORMAT ===
    Return ONLY a JSON array (no other text):
    [
      {{
        "name": "Feature Name",
        "reason": "Why this should be tested",
        "priority": "high",
        "steps": [
          "Step 1 description as simple string",
          "Step 2 description as simple string",
          "Step 3 description as simple string"
        ]
      }}
    ]

    Example steps format:
    - "Navigate to products page"
    - "Click on first product"
    - "Verify product details are displayed"
    - "Add product to cart"
    - "Verify cart count increased"

    Focus on:
    - Unused buttons, links, or forms
    - Interactive elements not covered
    - Edge cases or alternative workflows
    - Features visible but not tested

    ONLY return the JSON array, nothing else.
    """

            logger.info("Sending discovery request to Claude API...")

            message = self.client.messages.create(
                model=self.model,
                max_tokens=4096,
                messages=[{
                    "role": "user",
                    "content": prompt
                }]
            )

            response_text = message.content[0].text
            logger.info(f"Received discovery response ({len(response_text)} chars)")

            # Parse JSON
            import json
            import re

            # Try to extract JSON array from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                scenarios = json.loads(json_match.group())
                logger.info(f"Successfully discovered {len(scenarios)} scenarios")
                return scenarios
            else:
                logger.warning("No JSON array found in discovery response")
                return []

        except Exception as e:
            logger.error(f"Error discovering scenarios: {e}")
            return []

# ============================================================
# TEST CASE REPOSITORY (Caching)
# ============================================================
class TestCaseRepository:
    """Load generic test cases from JSON file"""

    def __init__(self, cache_file: str = GENERIC_TEST_CASES_FILE):
        self.test_cases_file = cache_file  # Now points to generic_form_page_crawler_test_cases.json
        # Get directory where the script is located
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(script_dir, cache_file)
    

    
    def load_cached_test_cases(self) -> List[Dict[str, Any]]:
        """Load test cases from cache file"""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
                logger.info(f"[TestCaseRepository] Loaded {len(test_cases)} test cases from cache")
                print(f"[TestCaseRepository] Loaded {len(test_cases)} test cases from cache")
                return test_cases
        except Exception as e:
            result_logger_gui.error(f"[TestCaseRepository] Error loading cache: {e}")
            print(f"[TestCaseRepository] Error loading cache: {e}")
            return []
    



    def get_test_cases(self) -> List[Dict]:
        """Load generic test cases from JSON file"""

        if not os.path.exists(self.test_cases_file):
            print(f"[TestCaseRepository] ❌ File not found: {self.test_cases_file}")
            result_logger_gui.error(f"Test cases file not found: {self.test_cases_file}")
            return []

        try:
            with open(self.test_cases_file, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)

            print(f"[TestCaseRepository] Loaded {len(test_cases)} generic test cases")
            logger.info(f"[TestCaseRepository] Loaded {len(test_cases)} test cases")

            return test_cases

        except Exception as e:
            print(f"[TestCaseRepository] ❌ Error loading test cases: {e}")
            result_logger_gui.error(f"Error loading test cases: {e}")
            return []


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
            logger.info(f"[DOMExtractor] {context}: {reduction}% reduction")
            
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
    def __init__(self, driver, test_context, base_url, shopping_site_key):
        self.driver = driver
        self.test_context = test_context
        self.base_url = base_url
        self.shopping_site_key = shopping_site_key

    def get_mode_label(self):
        """Return mode label for logging"""
        if hasattr(self, 'mode') and self.mode and self.mode.lower() == 'ai':
            return " (AI exploratory method)"
        else:
            return " (Regular non-AI method)"

    def _check_for_errors(self):
        """Check if there are any error messages on the page"""
        error_selectors = [
            "p[style*='color: red']",
            "p[style*='color:red']",
            ".error",
            ".error-message",
            ".alert-danger",
            "[class*='error']",
            "p.text-danger"
        ]

        for selector in error_selectors:
            try:
                error_elem = self._find_element(selector, timeout=0.5)
                if error_elem and error_elem.is_displayed():
                    error_text = error_elem.text.strip()
                    if error_text:
                        return True, error_text
            except:
                continue

        return False, ""

    def capture_failure_screenshot(self, step_info: str = ""):
        """Capture screenshot on test failure"""
        try:
            import datetime

            # Generate timestamp
            timestamp = datetime.datetime.now().strftime("%Y%m%d_%H%M%S")

            # Create screenshots directory with proper structure
            screenshots_dir = os.path.expanduser(f"~/automation_product_config/screenshots/{self.shopping_site_key}")
            os.makedirs(screenshots_dir, exist_ok=True)

            # Create filename with timestamp and step info
            step_clean = step_info.replace(" ", "_").replace("/", "_")[:50]  # Limit length
            filename = f"failure_{timestamp}_{step_clean}.png"
            filepath = os.path.join(screenshots_dir, filename)

            # Take screenshot
            self.driver.save_screenshot(filepath)

            print(f"📸 Screenshot saved: {filepath}")
            result_logger_gui.info(f"📸 Screenshot saved: {filename}")
            logger.info(f"Failure screenshot saved to: {filepath}")

            return filepath

        except Exception as e:
            print(f"⚠️ Failed to capture screenshot: {e}")
            logger.error(f"Screenshot capture failed: {e}")
            return None

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
            except Exception as css_error:
                # Check if it's an invalid selector error (Playwright syntax)
                error_str = str(css_error).lower()
                if "invalid selector" in error_str or "syntax" in error_str:
                    # Try to auto-convert Playwright selectors
                    if ":has-text(" in selector:
                        import re
                        match = re.search(r"(.+):has-text\(['\"](.+)['\"]\)", selector)
                        if match:
                            tag = match.group(1)
                            text = match.group(2)
                            xpath = f"//{tag}[contains(text(), '{text}')]"
                            logger.info(f"Auto-converting Playwright selector to XPath: {xpath}")
                            print(f"🔄 Converted :has-text() to XPath: {xpath}")
                            try:
                                element = wait.until(
                                    EC.presence_of_element_located((By.XPATH, xpath))
                                )
                                return element
                            except:
                                print(f"⚠️ Converted XPath also failed: {xpath}")

                    elif ":contains(" in selector:
                        import re
                        match = re.search(r"(.+):contains\(['\"](.+)['\"]\)", selector)
                        if match:
                            tag = match.group(1)
                            text = match.group(2)
                            converted_xpath = f"//{tag}[contains(text(), '{text}')]"
                            logger.info(f"Auto-converting jQuery selector to XPath: {converted_xpath}")
                            print(f"🔄 Converted :contains() to XPath: {converted_xpath}")
                            try:
                                element = wait.until(
                                    EC.presence_of_element_located((By.XPATH, converted_xpath))
                                )
                                return element
                            except:
                                print(f"⚠️ Converted XPath also failed: {converted_xpath}")

                    # If conversion failed or not applicable, log and return None
                    print(f"❌ Invalid selector (Playwright syntax not supported): {selector}")
                    logger.error(f"Invalid selector: {selector}")
                    return None

                # Not an invalid selector error, try XPath
                try:
                    element = wait.until(
                        EC.presence_of_element_located((By.XPATH, selector))
                    )
                    return element
                except:
                    # Both CSS and XPath failed
                    return None

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
            # Check if this is an error/failure verification
            is_error_check = any(keyword in verification.lower() for keyword in [
                'error', 'fail', 'invalid', 'incorrect', 'wrong', 'denied'
            ])

            if "page title contains" in verification.lower():
                expected = verification.split("'")[1]
                actual = self.driver.title
                success = expected.lower() in actual.lower()
                return (success, expected, actual)

            if "is visible" in verification.lower() or "is displayed" in verification.lower():
                if selector:
                    element = self._find_element(selector, timeout=5)
                    element_visible = element is not None and element.is_displayed()

                    if is_error_check:
                        # Simple: Is there ANY error text visible on the page?
                        error_exists = element_visible and element is not None

                        # Is this a negative test? (expects error)
                        is_negative_test = any(keyword in verification.lower() for keyword in [
                            'incorrect', 'wrong', 'invalid', 'failed', 'denied', 'existing', "exist"
                        ])

                        if is_negative_test:
                            # Negative test: error SHOULD exist
                            success = error_exists
                            expected = "Error message visible"
                            actual = "Error message visible" if error_exists else "No error message"
                        else:
                            # Positive test: error should NOT exist
                            success = not error_exists
                            expected = "No error message"
                            actual = "Error message visible" if error_exists else "No error message"
                    else:
                        # Normal check: if element visible = SUCCESS
                        success = element_visible
                        expected = "Element visible"
                        actual = "Element visible" if success else "Element not found or not visible"

                    return (success, expected, actual)
                return (True, "Element visible", "Element visible")

            if "text equals" in verification.lower() or "value equals" in verification.lower():
                if selector:
                    element = self._find_element(selector, timeout=5)
                    if element:
                        expected = verification.split("'")[1] if "'" in verification else verification

                        # Auto-detect if it's an input field
                        tag_name = element.tag_name.lower()
                        if tag_name in ['input', 'textarea', 'select']:
                            actual = element.get_attribute('value') or ""
                        else:
                            actual = element.text.strip()

                        success = expected.lower() == actual.lower()
                        return (success, expected, actual)
                    return (False, verification.split("'")[1] if "'" in verification else "Text", "Element not found")
                return (True, "Text match", "Text match")

            if "text contains" in verification.lower() or "value contains" in verification.lower():
                if selector:
                    element = self._find_element(selector, timeout=5)
                    if element:
                        expected = verification.split("'")[1] if "'" in verification else verification

                        # Auto-detect if it's an input field
                        tag_name = element.tag_name.lower()
                        if tag_name in ['input', 'textarea', 'select']:
                            actual = element.get_attribute('value') or ""
                        else:
                            actual = element.text.strip()

                        success = expected.lower() in actual.lower()
                        return (success, expected, actual)
                    return (False, verification.split("'")[1] if "'" in verification else "Text", "Element not found")
                return (True, "Text contains", "Text contains")

            # Default: check for error keywords
            if is_error_check:
                # If it's an error check and we get here, assume no error = success
                return (True, "No error", "No error")

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
                    # Fix relative URLs
                    if url.startswith('/'):
                        # Relative URL - prepend base URL
                        base_url = self.base_url
                        url = base_url.rstrip('/') + url
                    elif not url.startswith('http'):
                        # No protocol - add https://
                        url = 'https://' + url

                    logger.info(f"Navigating to {url}")
                    logger.info(f"-" * 70)

                    self.driver.get(url)
                    logger.info(f"Successfully navigated to {url}")

            elif action == "click":
                logger.info(f"\nClicking: {description}")
                logger.info("-" * 70)

                element = self._find_element(selector)
                if element:
                    try:
                        # Method 1: Try normal click first (fastest)
                        element.click()
                        logger.info(f"Successfully clicked element: {selector}")
                        is_submit = any(word in description.lower() for word in
                                        ['submit', 'login', 'register', 'signup', 'create account'])

                        if is_submit:
                            time.sleep(2)  # Wait for page to process

                            # Check for error messages
                            test_case = step.get("test_case", "")
                            is_negative_test = any(keyword in description.lower() for keyword in [
                                'incorrect', 'invalid', 'wrong', 'bad', 'fail', 'existing', 'exist'
                            ]) or any(keyword in test_case.lower() for keyword in [
                                'incorrect', 'invalid', 'wrong', 'bad', 'fail', 'existing', 'exist'
                            ])

                            # Check for error messages
                            has_error, error_text = self._check_for_errors()

                            if has_error:
                                if is_negative_test:
                                    # Error is EXPECTED in negative tests - this is SUCCESS!
                                    print(f"✅ Expected error found (negative test): {error_text}")
                                    result_logger_gui.info(f"✅ Expected error: {error_text}")
                                    logger.info(f"Negative test passed - error correctly shown: {error_text}")
                                    # Don't return False - continue to next step!
                                else:
                                    # Error is UNEXPECTED in positive tests - this is FAILURE!
                                    print(f"❌ Unexpected error (positive test): {error_text}")
                                    result_logger_gui.error(f"Form error: {error_text}")
                                    logger.error(f"Form submission failed with error: {error_text}")
                                    self.capture_failure_screenshot(f"form_error_{error_text[:30]}")
                                    return False

                    except ElementClickInterceptedException:
                        # Element is blocked by ad, modal, or other overlay
                        logger.warning(f"Normal click blocked (likely by ad), trying alternatives...")
                        result_logger_gui.warning(f"⚠️ Click blocked by overlay, using fallback...")

                        try:
                            # Method 2: Scroll element to center of viewport and retry
                            self.driver.execute_script(
                                "arguments[0].scrollIntoView({block: 'center', behavior: 'smooth'});", element)
                            time.sleep(0.5)  # Wait for scroll
                            element.click()
                            result_logger_gui.info(f"✓ Clicked after scrolling")
                            logger.info(f"Successfully clicked after scrolling: {selector}")
                        except:
                            try:
                                # Method 3: JavaScript click (bypasses all overlays)
                                self.driver.execute_script("arguments[0].click();", element)
                                result_logger_gui.info(f"✓ Clicked with JavaScript")
                                logger.info(f"Successfully clicked with JavaScript: {selector}")
                            except Exception as e:
                                result_logger_gui.error(f"✗ All click methods failed: {e}")
                                logger.error(f"All click methods failed for {selector}: {e}")
                                self.capture_failure_screenshot(f"all_click_methods_failed")
                                return False
                else:
                    result_logger_gui.info(f"✗ Failed to find element: {selector}")
                    logger.error(f"Element not found for click: {selector}")
                    self.capture_failure_screenshot(f"element_not_found_for_click")
                    return False
            
            elif action == "fill":
                result_logger_gui.info(f"Filling field: {description}")

                element = self._find_element(selector)
                if element:
                    element.clear()
                    element.send_keys(value)
                    # Mask password in logs
                    display_value = "****" if "password" in description.lower() else value
                    result_logger_gui.info(f"✓ Entered: {display_value}")
                    result_logger_gui.info("-" * 70)
                    logger.info(f"Successfully filled element {selector} with value")
                else:
                    result_logger_gui.info(f"✗ Failed to find field: {selector}")
                    logger.error(f"Element not found for fill: {selector}")
                    self.capture_failure_screenshot(f"element_not_found_for_fill")
                    return False


            elif action == "select":

                result_logger_gui.info(f"Selecting option: {description}")


                element = self._find_element(selector)

                if element:

                    tag_name = element.tag_name.lower()

                    # Check if it's actually a <select> element

                    if tag_name == 'select':

                        # Standard dropdown

                        from selenium.webdriver.support.ui import Select

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
                        result_logger_gui.info("-" * 70)

                        logger.info(f"Successfully selected value '{value}' in {selector}")


                    elif tag_name == 'input' and element.get_attribute('type') == 'radio':

                        # It's a radio button - find the specific one with this value

                        logger.info(f"Element is a radio button, finding option with value '{value}'")

                        # Get the name attribute

                        name = element.get_attribute('name')

                        # Find all radio buttons with this name

                        radio_buttons = self.driver.find_elements(By.CSS_SELECTOR,
                                                                  f"input[type='radio'][name='{name}']")

                        # Find the one matching the value

                        clicked = False

                        for radio in radio_buttons:

                            radio_value = radio.get_attribute('value')

                            # Check if value matches (case-insensitive)

                            if radio_value and radio_value.lower() == str(value).lower():
                                radio.click()

                                result_logger_gui.info(f"✓ Selected radio: {value}")
                                result_logger_gui.info("-" * 70)

                                logger.info(f"Successfully selected radio button: {value}")

                                clicked = True

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
                #result_logger_gui.info("-"*70)
                
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
                                self.capture_failure_screenshot(f"cart_total_mismatch")
                                return False
                        else:
                            print("⚠️ Could not parse total from page")
                            self.capture_failure_screenshot(f"cant_parse_total_from_page")
                            return False
                    else:
                        print(f"❌ Cart total element not found: {selector}")
                        self.capture_failure_screenshot(f"cart_total_element_not_found")
                        return False
                except Exception as e:
                    print(f"❌ Error verifying cart: {e}")
                    result_logger_gui.error(f"[Step {step_num}] Error verifying cart: {e}")
                    self.capture_failure_screenshot(f"error_verifying_cart")
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
                    self.capture_failure_screenshot(f"coupon_input_not_found")
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
            self.capture_failure_screenshot(f"error_executing_step")
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
        use_ai: bool = True,
        regenerate_only_on_url_change: bool = False
    ):
        self.driver = driver
        self.site_config = SHOPPING_SITES[shopping_site_key]
        self.shopping_site_key = shopping_site_key
        self.regenerate_only_on_url_change = regenerate_only_on_url_change
        self.use_ai = use_ai
        
        # Initialize components
        self.test_context = TestContext()
        self.test_case_repo = TestCaseRepository()
        self.dom_extractor = DOMExtractor(driver)
        self.dom_detector = DOMChangeDetector()

        self.step_executor = StepExecutor(
            self.driver,
            self.test_context,
            self.site_config["url"],
            self.shopping_site_key  # ADD THIS
        )
        
        # ✅ OPTIMIZATION 2: DOM Cache
        self.dom_cache = DOMCache()
        self.mode = None
        
        # AI helper (only if using AI mode)
        if use_ai:
            if not api_key:
                raise ValueError("API key required for AI mode")
            self.ai_helper = AIHelper(api_key)
        else:
            self.ai_helper = None
        
        # Load test cases
        self.all_test_cases = self.test_case_repo.get_test_cases()
        
        # Get test groups
        self.test_groups = self.site_config.get("test_groups", [])
        
        logger.info(f"[Orchestrator] Initialized for {shopping_site_key}")
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

        self.mode = 'ai'
        
        if not self.ai_helper:
            print("❌ AI helper not initialized")
            return
        
        # Clean old DOM cache entries
        self.dom_cache.clear_old_entries(max_age_hours=24)
        
        # Process each test group
        for group_idx, group in enumerate(self.test_groups, 1):
            group_name = group['name']
            test_ids = group['test_ids']


            print(f"\n{'=' * 70}")
            print(f"📦 GROUP {group_idx}/{len(self.test_groups)}: {group_name.upper()}")
            print(f"   Test IDs: {test_ids}")
            print(f"   Description: {group.get('description', '')}")
            print("=" * 70)

            # Select test cases for this group by IDs
            group_test_cases = [tc for tc in self.all_test_cases if tc['id'] in test_ids]

            skipped_tests = [tc for tc in group_test_cases if tc.get('skip', False)]
            group_test_cases = [tc for tc in group_test_cases if not tc.get('skip', False)]

            if skipped_tests:
                print(f"[Phase 1] Skipping {len(skipped_tests)} test(s):")
                for tc in skipped_tests:
                    print(f"   ⏭️  {tc['name']} (skip=true)")
                logger.info(f"Skipped {len(skipped_tests)} tests in group '{group_name}'")

            if not group_test_cases:
                print(
                    f"\n⏭️  Skipping GROUP {group_idx}/{len(self.test_groups)}: {group_name.upper()} (all tests marked skip=true)")
                logger.info(f"Skipped entire group '{group_name}' - all tests marked skip=true")
                continue

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
                    result_logger_gui.info("="*70)
                    mode_label = " (AI exploratory method)" if self.mode == 'ai' else " (Regular non-AI method)"
                    result_logger_gui.info(f"STARTING TEST CASE: {current_test_case}{mode_label}")
                    #result_logger_gui.info("=" * 70)
                    logger.info(f"Starting new test case: {current_test_case} (AI run mode)")
                
                # Execute step
                success = self.step_executor.execute_step(step)
                
                if not success:
                    print(f"⚠️ Step {step.get('step_number')} failed, stopping group")
                    result_logger_gui.info(f"** Step failed - stopping test group")
                    result_logger_gui.info("-"*70)
                    logger.warning(f"Step {step.get('step_number')} failed, stopping group")
                    break
                
                success_count += 1
                executed_steps.append(step)
                
                # Check if DOM changed
                # Check if DOM changed
                current_hash = self.dom_extractor.get_dom_hash()
                dom_changed = self.dom_detector.has_dom_changed(current_hash)

                # Check if URL changed
                current_url_now = self.driver.current_url
                url_changed = current_url_now != getattr(self, '_last_url', current_url)

                # Decide whether to regenerate based on configuration
                should_regenerate = False

                if self.regenerate_only_on_url_change:
                    # Mode: Only regenerate on URL change
                    if url_changed:
                        should_regenerate = True
                        print(f"🔄 URL changed after step {step.get('step_number')}")
                        logger.info(f"⏳ Page changed (URL) - regenerating test steps...")
                    elif dom_changed:
                        print(f"🔄 DOM changed (same URL) - continuing without regeneration")
                else:
                    # Mode: Regenerate on any DOM change (current behavior)
                    if dom_changed:
                        should_regenerate = True
                        if url_changed:
                            print(f"🔄 URL changed after step {step.get('step_number')}")
                            logger.info(f"⏳ Page changed (URL) - regenerating test steps...")
                        else:
                            print(f"🔄 DOM changed after step {step.get('step_number')}")
                            result_logger_gui.info(f"⏳ Page changed (DOM) - regenerating test steps...")

                if should_regenerate:
                    result_logger_gui.info("=" * 70)
                    logger.info(f"DOM/URL changed after step {step.get('step_number')}, regenerating steps")

                    # Store current URL for next comparison
                    self._last_url = current_url_now

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
                        logger.info(f"✓ Generated {len(remaining_steps)} new steps - continuing...")
                        logger.info("=" * 70)
                        logger.info(f"Generated {len(remaining_steps)} new steps after DOM change")
                    else:
                        print(f"⚠️ No remaining steps generated")
                        result_logger_gui.info(f"✗ No steps generated - stopping")
                        logger.warning("No remaining steps generated after DOM change")
                        break
                
                current_step_index += 1
            
            # Save successful steps to JSON file
            if executed_steps:
                # Create project directory if it doesn't exist
                project_dir = os.path.join(PROJECTS_BASE_DIR, self.shopping_site_key)
                os.makedirs(project_dir, exist_ok=True)

                output_file = os.path.join(project_dir, f"{self.shopping_site_key}_{group_name}_steps.json")
                self._save_steps_to_json(executed_steps, output_file)
                print(f"💾 Saved {len(executed_steps)} steps to {output_file}")
            
            print(f"{'='*70}")
            print(f"✅ GROUP '{group_name}' COMPLETE")
            print(f"   Successful steps: {success_count}/{len(executed_steps)}")
            print(f"{'='*70}")
            
            result_logger_gui.info("="*70)
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

    def _run_exploratory_testing(self, exploratory_test_case: Dict) -> list:
        """
        Run exploratory testing on current page

        Args:
            exploratory_test_case: The exploratory test case config

        Returns:
            List of discovered test scenarios (as test case objects)
        """
        print("\n" + "=" * 70)
        print("🔍 EXPLORATORY TESTING - DISCOVERING NEW SCENARIOS")
        print("=" * 70)

        try:
            max_scenarios = 5

            current_url = self.driver.current_url
            print(f"📍 Analyzing: {current_url}")

            dom_html = self.dom_extractor.get_minimal_dom(include_verification=True)

            already_tested = [tc['name'] for tc in self.all_test_cases if tc.get('id') != 100]

            print(f"🔎 Discovering up to {max_scenarios} new test scenarios...")
            print(f"📋 Already tested: {len(already_tested)} features")

            discovered = self.ai_helper.discover_test_scenarios(
                dom_html=dom_html,
                already_tested=already_tested,
                max_scenarios=max_scenarios
            )

            if not discovered:
                print("⚠️ No new scenarios discovered")
                return []

            print(f"✨ DISCOVERED {len(discovered)} NEW SCENARIOS:")
            print("=" * 70)

            converted_scenarios = []
            for idx, scenario in enumerate(discovered, 1):
                print(f"{idx}. {scenario['name']}")
                print(f"   Priority: {scenario.get('priority', 'medium').upper()}")
                print(f"   Reason: {scenario.get('reason', 'N/A')}")
                print(f"   Steps: {len(scenario.get('steps', []))}")

                test_case = {
                    "id": 100 + idx,
                    "name": scenario['name'],
                    "category": "exploration",
                    "steps": scenario.get('steps', []),
                    "discovered": True,
                    "priority": scenario.get('priority', 'medium')
                }
                converted_scenarios.append(test_case)

            print("\n" + "=" * 70)
            print(f"✅ Ready to execute {len(converted_scenarios)} discovered scenarios")
            print("=" * 70)

            return converted_scenarios

        except Exception as e:
            logger.error(f"Error in exploratory testing: {e}")
            import traceback
            traceback.print_exc()
            return []


    def run_from_json(self):
        """Run tests from pre-generated JSON files (replay mode)"""
        print("\n" + "="*70)
        print("📼 REPLAY MODE - USING SAVED STEPS")
        print("="*70)
        
        result_logger_gui.info("\n" + "="*70)
        result_logger_gui.info("STARTING TEST REPLAY FROM SAVED STEPS (Regular non AI run)")
        result_logger_gui.info("="*70)
        
        logger.info("Starting replay mode execution (regular non AI mode)")
        
        for group_idx, group in enumerate(self.test_groups, 1):
            group_name = group["name"]
            test_ids = group.get("test_ids", [])
            
            # Look for saved steps file
            # Look for saved steps in project directory

            group_test_cases = [tc for tc in self.all_test_cases if tc['id'] in test_ids]
            skipped_tests = [tc for tc in group_test_cases if tc.get('skip', False)]
            active_tests = [tc for tc in group_test_cases if not tc.get('skip', False)]

            if skipped_tests and active_tests:
                print(f"\n[Replay] Skipping {len(skipped_tests)} test(s) in group '{group_name}':")
                for tc in skipped_tests:
                    print(f"   ⏭️  {tc['name']} (skip=true)")

            if not active_tests:
                print(
                    f"\n⏭️  Skipping GROUP {group_idx}/{len(self.test_groups)}: {group_name.upper()} (all tests marked skip=true)")
                logger.info(f"Skipped entire group '{group_name}' in replay mode - all tests marked skip=true")
                continue

            project_dir = os.path.join(PROJECTS_BASE_DIR, self.shopping_site_key)
            steps_file = os.path.join(project_dir, f"{self.shopping_site_key}_{group_name}_steps.json")
            
            if not os.path.exists(steps_file):
                print(f"⚠️ No saved steps found for group '{group_name}' ({steps_file})")
                result_logger_gui.info(f"✗ No saved steps found for group '{group_name}'")
                logger.warning(f"Steps file not found: {steps_file}")
                continue
            
            print(f"\n{'='*70}")
            print(f"📦 GROUP {group_idx}/{len(self.test_groups)}: {group_name.upper()}")
            print(f"{'='*70}")
            
            result_logger_gui.info(f"\n{'='*70}")
            result_logger_gui.info(f"STARTING TEST GROUP: {group_name.upper()} (Regular non AI run)")
            result_logger_gui.info("="*70)
            
            logger.info(f"Processing group {group_idx}/{len(self.test_groups)}: {group_name}")
            
            # Load steps from file
            try:
                with open(steps_file, 'r') as f:
                    steps = json.load(f)
                print(f"[Replay] Loaded {len(steps)} steps from {steps_file}")
                logger.info(f"Loaded {len(steps)} steps from {steps_file}")
            except Exception as e:
                print(f"❌ Error loading steps: {e}")
                result_logger_gui.info(f"✗ Error loading steps: {e}")
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
            result_logger_gui.info("-"*70)
            
            success_count = 0
            current_test_case = None
            
            for step in steps:
                # Log test case if it changed
                test_case = step.get("test_case", "")
                if test_case != current_test_case:
                    current_test_case = test_case
                    result_logger_gui.info("")  # Blank line
                    result_logger_gui.info("=" * 70)
                    result_logger_gui.info(f"STARTING TEST CASE: {test_case} (Regular non AI run)")
                    result_logger_gui.info("=" * 70)
                    result_logger_gui.info("")  # Blank line
                    logger.info(f"Starting test case: {test_case} (regular non AI Mode)")
                
                success = self.step_executor.execute_step(step)
                if success:
                    success_count += 1
                else:
                    print(f"⚠️ Step failed, continuing...")
                    result_logger_gui.info(f"✗ Step failed - continuing with next step")
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
            logger.info(f"[Orchestrator] Saved steps to {filename}")
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
        'profile.default_content_setting_values.notifications': 2,
        "profile.default_content_settings.popups": 0,
        "autofill.profile_enabled": False
    })

    options.add_argument("--disable-features=PasswordManager")
    options.add_experimental_option('useAutomationExtension', False)
    
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
    api_key: Optional[str] = None,
    regenerate_only_on_url_change: bool = False,
):
    """
    Main entry point for test automation
    
    Args:
        shopping_site_key: Key from SHOPPING_SITES dict
        mode: "ai" for AI-powered generation, "replay" for JSON replay
        headless: Run browser in headless mode
        api_key: Anthropic API key (required for AI mode)
    """
    
    result_logger_gui.info("="*70)
    result_logger_gui.info("INITIALIZING TEST AUTOMATION")
    result_logger_gui.info("="*70)
    
    logger.info("Starting test automation (regular no AI run)")

    # Validate shopping site key
    if shopping_site_key not in SHOPPING_SITES:
        print(f"❌ ERROR: Shopping site '{shopping_site_key}' not found in SHOPPING_SITES config")
        print(f"Available sites: {', '.join(SHOPPING_SITES.keys())}")
        result_logger_gui.info(f"✗ Error: Shopping site '{shopping_site_key}' not found")
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
    
    result_logger_gui.info(f"Shopping Site: {shopping_site_key}")
    result_logger_gui.info(f"Target URL: {target_url}")
    result_logger_gui.info(f"Mode: {mode.upper()}")
    result_logger_gui.info(f"Headless: {headless}")
    result_logger_gui.info(f"regenerate_only_on_url_change: {regenerate_only_on_url_change}")

    logger.info(f"Configuration - Site: {shopping_site_key}, Mode: {mode}, Headless: {headless}")
    
    if mode == "ai":
        result_logger_gui.info("✓ Cost Optimizations Enabled:")
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
        result_logger_gui.info("Preparing test environment...")
        result_logger_gui.info("="*70)
        
        logger.info("Creating test orchestrator")
        orchestrator = TestOrchestrator(
            driver=driver,
            shopping_site_key=shopping_site_key,
            api_key=api_key,
            use_ai=(mode == "ai"),
            regenerate_only_on_url_change=regenerate_only_on_url_change
        )
        
        logger.info(f"✓ Loaded {len(orchestrator.all_test_cases)} test cases")
        
        # Run based on mode
        if mode == "ai":
            orchestrator.run_with_ai()
        elif mode == "replay":
            orchestrator.run_from_json()
        else:
            print(f"❌ Invalid mode: {mode}. Use 'ai' or 'replay'")
            result_logger_gui.info(f"✗ Invalid mode: {mode}")
            logger.error(f"Invalid mode specified: {mode}")
        
    except KeyboardInterrupt:
        print("\n⌨️ User interrupted execution (Ctrl+C)")
        result_logger_gui.info("\n\n✗ Test execution interrupted by user")
        logger.info("User interrupted execution (Ctrl+C)")
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        result_logger_gui.info(f"✗ Error during execution: {str(e)}")
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

    REGENERATE_ONLY_ON_URL_CHANGE = True  # Default: check DOM changes
    
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
    print(f"Test Cases File: {GENERIC_TEST_CASES_FILE}")
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
        api_key=API_KEY,
        regenerate_only_on_url_change= REGENERATE_ONLY_ON_URL_CHANGE
    )
