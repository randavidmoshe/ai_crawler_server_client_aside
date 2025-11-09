# ai_prompter.py
# AI-Powered Test Step Generation using Claude API

import json
import time
import logging
import anthropic
import random
from typing import List, Dict, Optional, Any
from anthropic._exceptions import OverloadedError, APIError

logger = logging.getLogger('init_logger.form_page_test')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')


class AIHelper:
    """Helper class for AI-powered step generation using Claude API"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required for AI functionality")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
    
    def _call_api_with_retry(self, prompt: str, max_tokens: int = 16000, max_retries: int = 3) -> Optional[str]:
        """
        Call Claude API with retry logic for handling overload errors
        
        Args:
            prompt: The prompt to send
            max_tokens: Maximum tokens for response
            max_retries: Number of retry attempts (default: 3)
            
        Returns:
            Response text or None if all retries fail
        """
        delay = 2  # Start with 2 second delay
        
        for attempt in range(max_retries):
            try:
                print(f"[AIHelper] Calling Claude API (attempt {attempt + 1}/{max_retries})...")
                result_logger_gui.info(f"[AIHelper] Calling Claude API (attempt {attempt + 1}/{max_retries})...")
                
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": prompt
                        }
                    ]
                )
                
                response_text = message.content[0].text
                print(f"[AIHelper] ✅ API call successful ({len(response_text)} chars)")
                return response_text
                
            except OverloadedError as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    print(f"[AIHelper] ❌ API Overloaded after {max_retries} attempts. Giving up.")
                    logger.error(f"[AIHelper] API Overloaded after {max_retries} attempts: {e}")
                    return None
                
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, delay * 0.5)
                wait_time = delay + jitter
                
                print(f"[AIHelper] ⚠️  API Overloaded (529). Retrying in {wait_time:.1f}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIHelper] API Overloaded. Retry {attempt + 1}/{max_retries} after {wait_time:.1f}s")
                
                time.sleep(wait_time)
                delay *= 2  # Exponential backoff
                
            except APIError as e:
                if attempt == max_retries - 1:
                    print(f"[AIHelper] ❌ API Error after {max_retries} attempts: {e}")
                    logger.error(f"[AIHelper] API Error after {max_retries} attempts: {e}")
                    return None
                
                print(f"[AIHelper] ⚠️  API Error: {e}. Retrying in {delay}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIHelper] API Error. Retry {attempt + 1}/{max_retries} after {delay}s")
                
                time.sleep(delay)
                delay *= 2
                
            except Exception as e:
                print(f"[AIHelper] ❌ Unexpected error: {e}")
                logger.error(f"[AIHelper] Unexpected error: {e}")
                return None
        
        return None
    
    def _call_api_with_retry_multimodal(self, content: list, max_tokens: int = 16000, max_retries: int = 3) -> Optional[str]:
        """
        Call Claude API with retry logic for multimodal content (images + text)
        
        Args:
            content: List of content blocks (can include images and text)
            max_tokens: Maximum tokens for response
            max_retries: Number of retry attempts (default: 3)
            
        Returns:
            Response text or None if all retries fail
        """
        delay = 2  # Start with 2 second delay
        
        for attempt in range(max_retries):
            try:
                print(f"[AIHelper] Calling Claude API with vision (attempt {attempt + 1}/{max_retries})...")
                result_logger_gui.info(f"[AIHelper] Calling Claude API with vision (attempt {attempt + 1}/{max_retries})...")
                
                message = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": content
                        }
                    ]
                )
                
                response_text = message.content[0].text
                print(f"[AIHelper] ✅ API call successful ({len(response_text)} chars)")
                return response_text
                
            except OverloadedError as e:
                if attempt == max_retries - 1:
                    print(f"[AIHelper] ❌ API Overloaded after {max_retries} attempts. Giving up.")
                    logger.error(f"[AIHelper] API Overloaded after {max_retries} attempts: {e}")
                    return None
                
                jitter = random.uniform(0, delay * 0.5)
                wait_time = delay + jitter
                
                print(f"[AIHelper] ⚠️  API Overloaded (529). Retrying in {wait_time:.1f}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIHelper] API Overloaded. Retry {attempt + 1}/{max_retries} after {wait_time:.1f}s")
                
                time.sleep(wait_time)
                delay *= 2
                
            except APIError as e:
                if attempt == max_retries - 1:
                    print(f"[AIHelper] ❌ API Error after {max_retries} attempts: {e}")
                    logger.error(f"[AIHelper] API Error after {max_retries} attempts: {e}")
                    return None
                
                print(f"[AIHelper] ⚠️  API Error: {e}. Retrying in {delay}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIHelper] API Error. Retry {attempt + 1}/{max_retries} after {delay}s")
                
                time.sleep(delay)
                delay *= 2
                
            except Exception as e:
                print(f"[AIHelper] ❌ Unexpected error: {e}")
                logger.error(f"[AIHelper] Unexpected error: {e}")
                return None
        
        return None

    def generate_test_steps(
            self,
            dom_html: str,
            test_cases: List[Dict[str, str]],
            previous_steps: Optional[List[Dict]] = None,
            step_where_dom_changed: Optional[int] = None,
            test_context=None,
            is_first_iteration: bool = False,
            screenshot_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Generate Selenium test steps based on DOM and test cases.
        If DOM changed, provide previous steps and which step caused the change.
        
        Returns:
            Dict with 'steps' (list) and 'ui_issue' (string)
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

        if is_first_iteration and test_context:
            # First iteration: generate NEW random credentials for registration if needed
            timestamp = int(time.time())
            test_email = f"testuser_{timestamp}@example.com"
            test_password = f"TestPass{random.randint(1000, 9999)}"
            test_name = f"TestUser{random.randint(100, 999)}"

            credentials_instruction = f"""=== TEST CREDENTIALS (FOR REGISTRATION IF NEEDED) ===
        If the form requires registration/login, use these NEW credentials:
        - Name: {test_name}
        - Email: {test_email}
        - Password: {test_password}

        Store these credentials as they may be used for login in subsequent steps.
        """
            # Save to context
            test_context.registered_name = test_name
            test_context.registered_email = test_email
            test_context.registered_password = test_password
        else:
            # Subsequent iterations: use EXISTING credentials for login only
            if test_context and test_context.has_credentials():
                credentials_instruction = f"""=== TEST CREDENTIALS (LOGIN ONLY) ===
        User is already registered. For any login tests, use these credentials:
        - Name: {test_context.registered_name}
        - Email: {test_context.registered_email}
        - Password: {test_context.registered_password}

        DO NOT perform registration again. Only do login if needed.
        """
            else:
                credentials_instruction = "=== NO CREDENTIALS AVAILABLE ===\nSkip any login/registration tests.\n"

        # Build previously reported UI issues section
        previously_reported_section = ""
        if test_context and test_context.reported_ui_issues:
            issues_list = "\n".join([f"- {issue}" for issue in test_context.reported_ui_issues])
            previously_reported_section = f"""
=== PREVIOUSLY REPORTED UI ISSUES ===
You have already reported these UI issues in earlier steps of this test:
{issues_list}

**CRITICAL: DO NOT report these issues again!**
Only report NEW issues that are not in the list above.
If all visible issues are already in the list, leave ui_issue as empty string "".
===============================================================================

"""

        prompt = f"""You are a test automation expert. You have TWO SEPARATE TASKS to complete:

        ================================================================================
        TASK 1: UI VERIFICATION (DO THIS FIRST - ISOLATED FROM TASK 2)
        ================================================================================
        
        {previously_reported_section}You are provided with a screenshot of the current page. Your FIRST task is to perform a thorough UI verification by analyzing the screenshot for visual defects.
        
        **MANDATORY SYSTEMATIC SCAN - Follow this checklist in order:**
        
        **Step 1: Scan Page Edges and Background**
        - Check TOP-LEFT corner of the entire viewport
        - Check TOP-RIGHT corner of the entire viewport  
        - Check BOTTOM-LEFT corner of the entire viewport
        - Check BOTTOM-RIGHT corner of the entire viewport
        - Check the BACKGROUND area around the form container
        - Check the HEADER area above the form
        - Look for any floating, orphaned, or disconnected visual elements (colored boxes, shapes, artifacts)
        
        **Step 2: Scan Each Form Field Individually**
        Go through EVERY visible form field one by one and check:
        - LEFT side of the field - any unexpected borders, boxes, or artifacts?
        - RIGHT side of the field - any unexpected borders, boxes, or artifacts?
        - TOP of the field - any unexpected borders, boxes, or artifacts?
        - BOTTOM of the field - any unexpected borders, boxes, or artifacts?
        - INSIDE the field - any styling issues, corrupted visuals?
        
        **What to Look For:**
        1. **Overlapping Elements** - Buttons, fields, or text covering each other
        2. **Unexpected Overlays** - Cookie banners or chat widgets blocking elements
        3. **Broken Layout** - Misaligned elements, horizontal scrollbars
        4. **Missing/Broken Visual Elements** - Broken icons, missing graphics
        5. **Visual Artifacts** - Unexpected colored boxes, shapes, borders (RED boxes, GREEN boxes, GRAY boxes, BLUE boxes, etc.)
        6. **Styling Defects** - Corrupted borders, inconsistent colors/backgrounds
        7. **Positioning Anomalies** - Elements floating outside containers
        8. **Spacing Issues** - Excessive or missing spacing
        
        **IMPORTANT:**
        - Don't stop after finding ONE issue - continue checking ALL areas and ALL fields
        - Some issues are subtle (small gray boxes) while others are obvious (bright red/green boxes)
        - Report ALL issues you find, comma-separated
        - Be specific: mention which field has which issue, or where in the page the issue appears
        
        **Example of complete report:**
        "Phone Number field has red border artifact on left side, Email Address field has gray box on right side, Green square visible in top-right corner of page"
        
        ================================================================================
        TASK 2: GENERATE TEST STEPS (DO THIS SECOND - AFTER UI VERIFICATION)
        ================================================================================
        
        Now generate Selenium WebDriver test steps for the form page.

        === SELECTOR GUIDELINES ===

        **Use CSS selectors (RECOMMENDED):**
           ✅ input[name='email']                           ← Good: form attributes
           ✅ input[data-qa='username-input']               ← Best: unique data attributes
           ✅ #email-field                                  ← Good: unique ID
           ✅ select[name='country']                        ← Good: dropdowns
           ✅ .submit-button                                ← Good: specific classes
        
        ** or buttons like accept/save/submit/ok use unique locators as most look alike  - so maybe XPATH for them
        
        **General Priority (for any element):**
           Priority 1: data-qa, data-testid, data-test attributes
           Priority 2: name, type, id attributes
           Priority 3: Unique IDs or classes
           Priority 4: Structural selectors (last resort)

        **FORBIDDEN SYNTAX (Playwright/jQuery specific):**
           ❌ :has-text('text')           ← Playwright only - NOT in Selenium
           ❌ :contains('text')            ← jQuery only - NOT in Selenium  
           ❌ :text('text')                ← Playwright only - NOT in Selenium
           ❌ >> (combinator)              ← Playwright only - NOT in Selenium

        **Good Examples:**

        

        Input Fields:
        ✅ "selector": "input[name='email']"
        ✅ "selector": "input[data-qa='username-input']"
        ✅ "selector": "#password-field"

        Links:
        ✅ "selector": "a[href='/terms']"
        ✅ "selector": "a.privacy-link"

        Dropdowns:
        ✅ "selector": "select[name='country']"
        ✅ "selector": "#state-dropdown"
        ✅ they can be also custom dropdowns

        **Key Rules:**
        - Prefer CSS selectors with attributes (name, id, data-*, type)
        - Use unique identifiers when available
        - Keep selectors simple and robust

        === END SELECTOR GUIDELINES ===


        === YOUR TASK: FORM PAGE TESTING ===

        You are testing a FORM PAGE. The test flow is:
        
        **Step 1: Find the Entry Point**
        - You start on a base page (like a list page, dashboard, or home page)
        - Look for a button/link to enter the form, such as:
          * "Add" / "Add New" / "Add [Item]"
          * "Create" / "Create New" / "Create [Item]"
          * "New" / "New [Item]"
          * "+" button
          * "Register" / "Sign Up"
          * Any button/link that opens a form
        - Click this button to enter the form
        
        **CRITICAL: Entry Button Workflow**
        Usually, the workflow is:
        1. You see ONLY the entry button initially (no form yet)
        2. You generate a click step for the entry button
        3. After clicking, the FORM WILL APPEAR (even though you can't see it yet!)
        4. You MUST generate steps to fill the form that will appear
        
        **Don't stop after clicking the entry button!** 
        Even if you only see the button now, you know a form will open after clicking it.
        Generate steps for: click button → THEN fill the form fields → THEN submit
        
        **Step 2: Fill the Form**
        Once inside the form (after clicking entry button):
        
        **Form Structure:**
        - Input fields (text, email, number, date, etc.)
        - Selection controls (dropdowns, radio buttons, checkboxes)
        - Tabs or sections that organize the form
        - Navigation buttons (Next, Previous, Save, Submit)
        - List items (sections with "Add" / "Add New" / "+" buttons to add multiple entries)
        
        **MANDATORY: LIST ITEMS HANDLING**
        ================================================================================
        If the form has a section for adding list items (e.g., "Add Item", "Add New", "+ Add", "Create Entry"):
        
        **YOU MUST ADD EXACTLY 2 ITEMS** by following this pattern:
        
        **First Item:**
        1. Click the "Add" / "Add New" / "+" button to open the item form/modal
        2. Fill ALL fields that appear in the modal/form
        3. Click the save/submit button ("Save", "Submit", "OK", "Add", "Accept", etc.)
        4. Wait for the modal to close or item to be added
        
        **Second Item (CRITICAL - DON'T FORGET THIS):**
        5. Click the "Add" / "Add New" / "+" button AGAIN to add a second item
        6. Fill ALL fields with DIFFERENT values from the first item
        7. Click the save/submit button again
        8. Wait for the modal to close or item to be added
        
        **Example Step Sequence:**
        ```
        Step X: Click "Add Item" button
        Step X+1: Fill "Name" field with "Item 1"
        Step X+2: Fill "Description" field with "First item description"
        Step X+3: Click "Save" button
        Step X+4: Wait for modal to close (1 second)
        Step X+5: Click "Add Item" button AGAIN (for second item)
        Step X+6: Fill "Name" field with "Item 2"
        Step X+7: Fill "Description" field with "Second item description"
        Step X+8: Click "Save" button
        Step X+9: Wait for modal to close (1 second)
        ```
        
        **IMPORTANT:** Do not skip list items! If you see an "Add" button for a list, you MUST add 2 items before moving to the next section.
        ================================================================================
        
        **CRITICAL: Tab/Section Handling:**
        If the form has tabs or sections:
        1. Click the FIRST tab
        2. Fill ALL visible fields in that tab completely
        3. Click the SECOND tab
        4. Fill ALL visible fields in that tab completely
        5. Repeat for EVERY tab/section
        6. Only after ALL tabs are filled → click Next or Submit
        
        **CRITICAL: Fill fields in the order a user would encounter them.**
        - If a field is inside a tab, you MUST click that tab FIRST before filling its fields
        - Do NOT try to fill fields from tabs that aren't active yet
        - Only generate fill steps for fields you can actually SEE in the current DOM
        - Use the EXACT selectors from the DOM (id, name, class attributes)
        - Do NOT guess field names or make up selectors that don't exist in the DOM
        
        **DO NOT skip tabs! Every tab must be filled before moving forward!**
        
        **Form Junctions - Random Selection:**
        Forms have "junctions" where user choices affect what appears next:
        - Dropdown selection → might show/hide fields
        - Radio button choice → might reveal new sections
        - Checkbox → might enable additional options
        - Tab selection → shows different content
        
        **At EVERY junction, you must:**
        1. Identify available options (e.g., dropdown has 5 options)
        2. Make a RANDOM choice (don't always pick the first!)
        3. Fill ALL fields and list items and dropdowns and anything else a user fills up that appear as a result
        4. Continue to next junction
        
        
        
        **Your Testing Path - Act Like a Real User:**
        You should follow ONE RANDOM path through the form, like a real user would:
        
        **IMPORTANT: Even if you only see an entry button now, you MUST generate ALL steps including:**
        - Click entry button
        - Wait for form to load
        - Fill ALL fields (that will appear after button click)
        - Make random selections at junctions
        - Submit the form
        
        Don't generate just the click and stop! Generate the complete flow!
        
        1. Start at the beginning of the form
        2. If form has tabs, process them ONE BY ONE:
           - Click Tab 1 → Fill ALL fields in Tab 1
           - Click Tab 2 → Fill ALL fields in Tab 2
           - Click Tab 3 → Fill ALL fields in Tab 3
           - etc.
        3. Fill ALL visible fields in the order they appear (not just required ones)
        4. At each junction (dropdown, radio button, checkbox), make a RANDOM selection
        5. After selecting, fill ANY new fields that appear
        6. Continue filling all visible fields in order
        7. Handle special elements:
           - Star ratings → Click on stars
           - Fields behind barriers (iframe, shadow DOM) → Use available tools to access them
           - Checkboxes → Check them if needed
           - Hidden fields revealed by hover/click → Fill them
        8. After ALL sections/tabs are complete → click Next or Submit
        9. Continue through multi-step forms
        10. Eventually reach and click the final Save/Submit button

        **CRITICAL: Access ALL Fields:**
        Your goal is to fill EVERY visible field, regardless of where it is.
        If fields require special access (inside iframe, shadow DOM, nested structures), 
        use the available tools (switch_to_frame, switch_to_shadow_root, etc.) to reach them.
        Generate whatever steps are necessary to access and fill ALL fields.

        **CRITICAL Rules for Real User Behavior:**
        - Fill fields in the ORDER a user would encounter them (top to bottom, if inside a tab then click tab first)
        - Only generate fill steps for fields that ACTUALLY EXIST in the DOM with real selectors
        - Do NOT guess or hallucinate field names - read them from the DOM attributes (name, id, class)
        - Fill ALL visible fields (required AND optional) - users often fill everything
        - Process EVERY tab/section before clicking Next
        - Make RANDOM selections at junctions (don't always pick the first option)
        - After each junction choice, check for newly visible fields and fill them ALL
        - Handle iframes, star ratings, and special UI elements
        - Continue until you find Next/Continue button or Save/Submit button
        - Follow this single random path to completion

        === TEST CONTEXT & CREDENTIALS ===

        {credentials_instruction}

        **Form Data Guidelines:**
        When generating test data for forms:
        - Name: {test_context.registered_name if test_context and test_context.registered_name else 'TestUser123'}
        - Email: {test_context.registered_email if test_context and test_context.registered_email else 'test@example.com'}
        - Phone: 1234567890
        - Address: 123 Main St
        - City: Los Angeles
        - State: California
        - Zip: 90001
        - Country: United States
        - Dates: Use reasonable values (e.g., birthdate: 01/15/1990)
        - Numbers: Use realistic values based on field context


        === AVAILABLE ACTIONS ===

        **Standard Actions:**
        - click: Click element (buttons, links, tabs)
        - fill: Enter text in input field
        - select: Choose from dropdown OR select radio button
        - verify: Check if element is visible
        - wait: Wait for duration (MAX 10 seconds!) OR wait for element to be ready if selector provided
        - wait_for_ready: Wait for AJAX-loaded element to become interactable (use for dynamic fields)
        - scroll: Scroll to element

        **Special Access Tools (use when needed to reach fields):**
        - switch_to_frame: Access fields inside iframe
        - switch_to_parent_frame: Navigate back one iframe level
        - switch_to_default: Return to main page context
        - switch_to_shadow_root: Access fields inside shadow DOM

        **CRITICAL WAIT RULES:**
        - **NEVER use wait with value > 10 seconds!** (will cause timeout)
        - For time-based wait: {{"action": "wait", "value": "2"}} (max 10 seconds)
        - For AJAX/dynamic fields: {{"action": "wait_for_ready", "selector": "#dependentField"}}
        - wait_for_ready waits up to 10s for element to be clickable/enabled
        - **For wait actions, keep selectors simple** - use IDs, classes, or basic attributes. Avoid complex CSS like :not(), :has(), or pseudo-selectors that may not work reliably with Selenium's wait conditions.

        **AJAX/Dynamic Field Handling:**
        When a field loads via AJAX (e.g., Field B appears after filling Field A):
        ```json
        {{"action": "fill", "selector": "input#fieldA", "value": "SomeValue"}},
        {{"action": "wait_for_ready", "selector": "input#fieldB", "description": "Wait for Field B to load via AJAX"}},
        {{"action": "fill", "selector": "input#fieldB", "value": "AnotherValue"}}
        ```

        **IMPORTANT: Use 'select' action for BOTH:**
        - <select> dropdowns: {{"action": "select", "selector": "select[name='country']", "value": "USA"}}
        - Radio buttons: {{"action": "select", "selector": "input[value='option1']", "value": "option1"}}


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
           - "selector": string or null (CSS selector is preferred - see guidelines above!)
           - "value": string or null (value for fill/select actions)
           - "verification": string or null (what to verify after action)
           - "wait_seconds": number (seconds to wait after action)

        3. **Selector Selection Process (follow this order):**
           Step 1: Look for data-qa, data-testid, data-test attributes → USE THESE FIRST
           Step 2: Look for unique name, type, id attributes → USE THESE SECOND
           Step 3: Look for unique IDs (#something) → USE THESE THIRD
           Step 4: Look for specific classes with context (.form .submit-btn) → USE THESE FOURTH
           Step 5: Use structural selectors (form > button:last-child) → LAST RESORT

        4. **Verification Steps:**
           After important actions, verify success:
           - After submit → verify success message exists
           - After navigation → verify new page/section loaded
           - After form completion → verify confirmation displayed

        5. **Wait Times:**
           - After navigate: 2 seconds
           - After click (page change): 2 seconds
           - After fill: 0.5 seconds
           - After verify: 1 second

        3. **Breaking Down Generic Steps:**
           - "Fill form fields" → Generate fill steps for EACH VISIBLE field (required AND optional)
           - "Complete form" → Generate steps for all sections/tabs
           - "Navigate to next section" → Click next button and verify new section
           - "Make random selection" → For dropdowns/radios, choose randomly from available options
           - **"Add list items" → Generate steps to add EXACTLY 2 items: Click Add → Fill fields → Save → Click Add AGAIN → Fill different values → Save**
           - Real users fill ALL visible fields, not just required ones!


        === EXAMPLE OUTPUT ===

        [
          {{
            "step_number": 1,
            "test_case": "Complete Form Following Random Path",
            "action": "click",
            "description": "Click 'Add New' button to open form",
            "selector": "button.add-new",
            "value": null,
            "verification": "form opens",
            "wait_seconds": 2
          }},
          {{
            "step_number": 2,
            "test_case": "Complete Form Following Random Path",
            "action": "fill",
            "description": "Enter name in form",
            "selector": "input[name='name']",
            "value": "TestUser123",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 3,
            "test_case": "Complete Form Following Random Path",
            "action": "click",
            "description": "Click address tab",
            "selector": "button[data-tab='address']",
            "value": null,
            "verification": null,
            "wait_seconds": 1
          }},
          {{
            "step_number": 4,
            "test_case": "Complete Form Following Random Path",
            "action": "switch_to_frame",
            "description": "Access address iframe",
            "selector": "iframe#address-frame",
            "value": null,
            "verification": null,
            "wait_seconds": 1
          }},
          {{
            "step_number": 5,
            "test_case": "Complete Form Following Random Path",
            "action": "fill",
            "description": "Fill street address",
            "selector": "input[name='street']",
            "value": "123 Main St",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 6,
            "test_case": "Complete Form Following Random Path",
            "action": "switch_to_default",
            "description": "Return to main page",
            "selector": null,
            "value": null,
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 7,
            "test_case": "Complete Form Following Random Path",
            "action": "fill",
            "description": "Fill Field A (triggers AJAX)",
            "selector": "input#fieldA",
            "value": "SampleValue",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 8,
            "test_case": "Complete Form Following Random Path",
            "action": "wait_for_ready",
            "description": "Wait for Field B to load via AJAX",
            "selector": "input#fieldB",
            "value": null,
            "verification": null,
            "wait_seconds": 0
          }},
          {{
            "step_number": 9,
            "test_case": "Complete Form Following Random Path",
            "action": "fill",
            "description": "Fill Field B",
            "selector": "input#fieldB",
            "value": "DependentValue",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 9,
            "test_case": "Complete Form Following Random Path",
            "action": "click",
            "description": "Click the Add button to add a new finding item",
            "selector": "button.btn-add-finding",
            "value": null,
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 10,
            "test_case": "Complete Form Following Random Path",
            "action": "select",
            "description": "Select inquiry type (random choice)",
            "selector": "select[name='inquiry_type']",
            "value": "General",
            "verification": null,
            "wait_seconds": 0.5
          }},
          {{
            "step_number": 8,
            "test_case": "Complete Form Following Random Path",
            "action": "click",
            "description": "Click submit button",
            "selector": "button[type='submit']",
            "value": null,
            "verification": "form submitted",
            "wait_seconds": 2
          }},
          {{
            "step_number": 9,
            "test_case": "Complete Form Following Random Path",
            "action": "verify",
            "description": "Verify success message displayed",
            "selector": ".success-message",
            "value": null,
            "verification": "success message is visible",
            "wait_seconds": 1
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
        ☐ Following ONE path through the form
        ☐ Valid JSON format (no trailing commas, proper quotes)

        {context}

        === RESPONSE FORMAT ===
        Return ONLY a JSON object with this structure:

        ```json
        {{
          "steps": [
            {{"step_number": 1, "action": "fill", "selector": "input#field", "value": "value", "description": "Fill field"}},
            {{"step_number": 2, "action": "click", "selector": "button.submit", "description": "Submit form"}}
          ],
          "ui_issue": ""
        }}
        ```

        - **steps**: Array of step objects to execute
        - **ui_issue**: Empty string if UI is fine, or description of issue if detected (e.g., "Cookie banner overlapping submit button")

        Return ONLY the JSON object, no other text.
        """
        
        try:
            logger.info("[AIHelper] Sending request to Claude API...")
            print("[AIHelper] Sending request to Claude API...")

            # Use retry wrapper (with or without screenshot)
            if screenshot_base64:
                # Use multimodal API with screenshot
                message_content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
                response_text = self._call_api_with_retry_multimodal(message_content, max_tokens=16000, max_retries=3)
            else:
                # Text-only API (backward compatibility)
                response_text = self._call_api_with_retry(prompt, max_tokens=16000, max_retries=3)
            
            if response_text is None:
                print("[AIHelper] ❌ Failed to get response from API after retries")
                logger.error("[AIHelper] Failed to get response from API after retries")
                return {"steps": [], "ui_issue": ""}
            
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
            
            # Try parsing as object first (new format with ui_issue)
            try:
                result = json.loads(response_text)
                if isinstance(result, dict) and "steps" in result:
                    # New format: {"steps": [...], "ui_issue": "..."}
                    steps = result.get("steps", [])
                    ui_issue = result.get("ui_issue", "")
                    
                    logger.info(f"[AIHelper] Successfully parsed {len(steps)} steps")
                    print(f"[AIHelper] Successfully parsed {len(steps)} steps")
                    
                    if ui_issue:
                        print(f"[AIHelper] ⚠️  UI Issue detected: {ui_issue}")
                    
                    return {"steps": steps, "ui_issue": ui_issue}
                elif isinstance(result, list):
                    # Old format: just array of steps (backward compatibility)
                    logger.info(f"[AIHelper] Successfully parsed {len(result)} steps (legacy format)")
                    print(f"[AIHelper] Successfully parsed {len(result)} steps (legacy format)")
                    return {"steps": result, "ui_issue": ""}
                else:
                    raise ValueError("Unexpected response format")
            except (json.JSONDecodeError, ValueError) as e:
                # Failed to parse
                result_logger_gui.error(f"[AIHelper] Failed to parse JSON: {e}")
                print(f"[AIHelper] Failed to parse JSON: {e}")
                print(f"[AIHelper] Response text: {response_text[:500]}")
                return {"steps": [], "ui_issue": ""}
            
        except Exception as e:
            result_logger_gui.error(f"[AIHelper] Error: {e}")
            print(f"[AIHelper] Error: {e}")
            import traceback
            traceback.print_exc()
            return {"steps": [], "ui_issue": ""}
    
    def regenerate_steps(
        self,
        dom_html: str,
        executed_steps: list,
        test_cases: list,
        test_context,
        screenshot_base64: Optional[str] = None
    ) -> Dict[str, Any]:
        """
        Regenerate remaining steps after DOM change
        
        Args:
            dom_html: Current page DOM (after change)
            executed_steps: Steps already executed
            test_cases: Test cases
            test_context: Test context
            screenshot_base64: Optional base64 screenshot for UI verification
            
        Returns:
            Dict with 'steps' (list) and 'ui_issue' (string)
        """
        try:
            print(f"[AIHelper] Regenerating steps after DOM change...")
            print(f"[AIHelper] Already executed: {len(executed_steps)} steps")
            
            # Build context of what's been done
            executed_context = ""
            if executed_steps:
                executed_context = f"""
## Steps Already Completed:
{json.dumps([{"step": i+1, "action": s.get("action"), "description": s.get("description"), "selector": s.get("selector")} for i, s in enumerate(executed_steps)], indent=2)}
"""
            
            # Build test cases context
            test_cases_context = ""
            if test_cases:
                test_cases_context = f"""
## Test Cases:
{json.dumps(test_cases, indent=2)}
"""
            
            # Build previously reported UI issues section
            previously_reported_section = ""
            if test_context and test_context.reported_ui_issues:
                issues_list = "\n".join([f"- {issue}" for issue in test_context.reported_ui_issues])
                previously_reported_section = f"""
=== PREVIOUSLY REPORTED UI ISSUES ===
You have already reported these UI issues in earlier steps of this test:
{issues_list}

**CRITICAL: DO NOT report these issues again!**
Only report NEW issues that are not in the list above.
If all visible issues are already in the list, leave ui_issue as empty string "".
===============================================================================

"""
            
            # Build full prompt with UI verification as separate task
            prompt = f"""You are a web automation expert. You have TWO SEPARATE TASKS to complete:

================================================================================
TASK 1: UI VERIFICATION (DO THIS FIRST - ISOLATED FROM TASK 2)
================================================================================

{previously_reported_section}You are provided with a screenshot of the current page. Your FIRST task is to perform a thorough UI verification by analyzing the screenshot for visual defects.

**MANDATORY SYSTEMATIC SCAN - Follow this checklist in order:**

**Step 1: Scan Page Edges and Background**
- Check TOP-LEFT corner of the entire viewport
- Check TOP-RIGHT corner of the entire viewport  
- Check BOTTOM-LEFT corner of the entire viewport
- Check BOTTOM-RIGHT corner of the entire viewport
- Check the BACKGROUND area around the form container
- Check the HEADER area above the form
- Look for any floating, orphaned, or disconnected visual elements (colored boxes, shapes, artifacts)

**Step 2: Scan Each Form Field Individually**
Go through EVERY visible form field one by one and check:
- LEFT side of the field - any unexpected borders, boxes, or artifacts?
- RIGHT side of the field - any unexpected borders, boxes, or artifacts?
- TOP of the field - any unexpected borders, boxes, or artifacts?
- BOTTOM of the field - any unexpected borders, boxes, or artifacts?
- INSIDE the field - any styling issues, corrupted visuals?

**What to Look For:**
1. **Overlapping Elements** - Buttons, fields, or text covering each other
2. **Unexpected Overlays** - Cookie banners or chat widgets blocking elements
3. **Broken Layout** - Misaligned elements, horizontal scrollbars
4. **Missing/Broken Visual Elements** - Broken icons, missing graphics
5. **Visual Artifacts** - Unexpected colored boxes, shapes, borders (RED boxes, GREEN boxes, GRAY boxes, BLUE boxes, etc.)
6. **Styling Defects** - Corrupted borders, inconsistent colors/backgrounds
7. **Positioning Anomalies** - Elements floating outside containers
8. **Spacing Issues** - Excessive or missing spacing

**IMPORTANT:**
- Don't stop after finding ONE issue - continue checking ALL areas and ALL fields
- Some issues are subtle (small gray boxes) while others are obvious (bright red/green boxes)
- Report ALL issues you find, comma-separated
- Be specific: mention which field has which issue, or where in the page the issue appears

**Example of complete report:**
"Phone Number field has red border artifact on left side, Email Address field has gray box on right side, Green square visible in top-right corner of page"

================================================================================
TASK 2: GENERATE REMAINING TEST STEPS (DO THIS SECOND - AFTER UI VERIFICATION)
================================================================================

The DOM has changed after executing some steps.

{executed_context}

The DOM changed, and here is the NEW current state:

## Current Page DOM:
{dom_html}

{test_cases_context}

## Your Task:
Based on the steps already completed and the NEW DOM state, generate the REMAINING steps needed to complete the form test.

**CRITICAL: LIST ITEMS REQUIREMENT - CHECK THIS FIRST BEFORE ANYTHING ELSE:**
Each list section requires EXACTLY 2 items total. **IMMEDIATELY look at the LAST executed step above:**
- **Did the LAST step just save a list item?** (Look for "Save Finding", "Save Engagement", "Save [Something]" in the last step)
- **If YES:** YOU MUST ADD A SECOND ITEM OF THAT SAME TYPE RIGHT NOW AS YOUR FIRST GENERATED STEP!
- **Do NOT move to other list types or fields until you complete the current list type!**
- Use the SAME "Add" button you just used → Fill fields with different values → Save

**Example:** If last step was "Save Finding" → Your first step MUST be "Click Add Finding button again"

Generate steps to:
1. **FIRST AND MOST IMPORTANT: If the last executed step saved a list item, add the second item of that same type NOW (Click the same Add button → Fill → Save)**
2. Check for OTHER list sections that also need 2 items each
3. Fill all remaining form fields
4. Handle any dropdowns, checkboxes, or special inputs
5. Submit the form
6. Verify success

## Response Format:
Return ONLY a JSON object with this structure:

```json
{{
  "steps": [
    {{"step_number": 1, "action": "fill", "selector": "input#field", "value": "value", "description": "Fill field"}},
    {{"step_number": 2, "action": "click", "selector": "button.submit", "description": "Submit form"}}
  ],
  "ui_issue": ""
}}
```

- **steps**: Array of step objects to execute
- **ui_issue**: Empty string if UI is fine, or description of ALL issues found (comma-separated)

Available actions: fill, select, click, verify, wait, wait_for_ready, scroll, hover, switch_to_frame, switch_to_default, switch_to_shadow_root

**CRITICAL:** Never use wait with value > 10 seconds! For AJAX, use wait_for_ready instead.

Return ONLY the JSON object, no other text.
"""
            
            # Call Claude API with retry (with or without screenshot)
            result_logger_gui.info("[AIHelper] Sending regeneration request to Claude API...")
            
            if screenshot_base64:
                # Use multimodal API with screenshot
                message_content = [
                    {
                        "type": "image",
                        "source": {
                            "type": "base64",
                            "media_type": "image/png",
                            "data": screenshot_base64
                        }
                    },
                    {
                        "type": "text",
                        "text": prompt
                    }
                ]
                response_text = self._call_api_with_retry_multimodal(message_content, max_tokens=16000, max_retries=3)
            else:
                # Text-only API
                response_text = self._call_api_with_retry(prompt, max_tokens=16000, max_retries=3)
            
            if response_text is None:
                print("[AIHelper] ❌ Failed to regenerate steps after retries")
                return {"steps": [], "ui_issue": ""}
            
            print(f"[AIHelper] Received regeneration response ({len(response_text)} chars)")
            
            # Parse JSON response
            import re
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            
            if json_match:
                response_data = json.loads(json_match.group())
                steps = response_data.get("steps", [])
                ui_issue = response_data.get("ui_issue", "")
                
                print(f"[AIHelper] Successfully regenerated {len(steps)} new steps")
                if ui_issue:
                    print(f"[AIHelper] ⚠️  UI Issue detected: {ui_issue}")
                
                return {"steps": steps, "ui_issue": ui_issue}
            else:
                print("[AIHelper] No JSON object found in regeneration response")
                return {"steps": [], "ui_issue": ""}
                
        except Exception as e:
            print(f"[AIHelper] Error regenerating steps: {e}")
            import traceback
            traceback.print_exc()
            return {"steps": [], "ui_issue": ""}

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

            prompt = f"""Analyze this form page and discover {max_scenarios} NEW testable scenarios.

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
    - "Navigate to form page"
    - "Fill all required fields in personal info section"
    - "Select option from dropdown that reveals additional fields"
    - "Fill conditional fields that appeared"
    - "Add list items"
    - "Click next to go to payment section"
    - "Complete payment fields"
    - "Submit form"
    - "Verify success confirmation"

    Focus on:
    - Unused form fields or sections
    - Different paths through conditional logic
    - List items
    - Alternative dropdown/radio selections
    - Edge cases or validation scenarios
    - Multi-step form flows

    ONLY return the JSON array, nothing else.
    """

            logger.info("Sending discovery request to Claude API...")

            response_text = self._call_api_with_retry(prompt, max_tokens=4096, max_retries=3)
            
            if response_text is None:
                logger.error("Failed to discover scenarios after retries")
                return []

            logger.info(f"Received discovery response ({len(response_text)} chars)")

            # Parse JSON
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
    
    def analyze_failure_and_recover(
        self,
        failed_step: Dict,
        executed_steps: List[Dict],
        fresh_dom: str,
        screenshot_path: str,
        test_cases: List[Dict],
        test_context,
        attempt_number: int
    ) -> List[Dict]:
        """
        Analyze a failed step using AI with vision and generate recovery steps
        
        Args:
            failed_step: The step that failed
            executed_steps: Steps completed successfully so far
            fresh_dom: Current DOM state
            screenshot_path: Path to full page screenshot
            test_cases: Active test cases
            test_context: Test context
            attempt_number: Attempt number (1 or 2)
            
        Returns:
            List of steps: [recovery steps] + [corrected failed step] + [remaining steps]
        """
        import base64
        import re
        
        try:
            print(f"[AIHelper] Analyzing failure with vision...")
            
            # Read and encode screenshot
            with open(screenshot_path, 'rb') as f:
                screenshot_data = base64.standard_b64encode(f.read()).decode('utf-8')
            
            # Build the prompt
            prompt = self._build_recovery_prompt(
                failed_step=failed_step,
                executed_steps=executed_steps,
                fresh_dom=fresh_dom,
                test_cases=test_cases,
                test_context=test_context,
                attempt_number=attempt_number
            )
            
            # Call Claude with vision and retry logic
            result_logger_gui.info("[AIHelper] Sending failure recovery request to Claude API with vision...")
            
            content = [
                {
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_data
                    }
                },
                {
                    "type": "text",
                    "text": prompt
                }
            ]
            
            response_text = self._call_api_with_retry_multimodal(content, max_tokens=16000, max_retries=3)
            
            if response_text is None:
                print("[AIHelper] ❌ Failed to get recovery response after retries")
                logger.error("[AIHelper] Failed to get recovery response after retries")
                return []
            
            print(f"[AIHelper] Received recovery response ({len(response_text)} chars)")
            logger.info(f"[AIHelper] Received recovery response ({len(response_text)} chars)")
            
            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                recovery_steps = json.loads(json_match.group())
                print(f"[AIHelper] Successfully parsed {len(recovery_steps)} recovery steps")
                logger.info(f"[AIHelper] Successfully parsed {len(recovery_steps)} recovery steps")
                return recovery_steps
            else:
                print("[AIHelper] No JSON array found in recovery response")
                logger.warning("[AIHelper] No JSON array found in recovery response")
                return []
                
        except Exception as e:
            print(f"[AIHelper] Error in failure recovery: {e}")
            logger.error(f"[AIHelper] Error in failure recovery: {e}")
            return []
    
    def _build_recovery_prompt(
        self,
        failed_step: Dict,
        executed_steps: List[Dict],
        fresh_dom: str,
        test_cases: List[Dict],
        test_context,
        attempt_number: int
    ) -> str:
        """Build the prompt for failure recovery analysis"""
        
        action = failed_step.get('action', 'unknown')
        selector = failed_step.get('selector', '')
        description = failed_step.get('description', '')
        
        # Build executed steps context
        executed_context = ""
        if executed_steps:
            executed_context = f"""
Steps completed successfully so far:
{json.dumps([{"step": i+1, "action": s.get("action"), "description": s.get("description")} for i, s in enumerate(executed_steps)], indent=2)}
"""
        
        prompt = f"""
# FAILURE RECOVERY AND ANALYSIS

A test step has FAILED. Your job is to analyze the failure and provide recovery steps.

## Failed Step (Attempt {attempt_number}/2):
- Action: {action}
- Selector: {selector}
- Description: {description}

{executed_context}

## What I'm Providing:
1. **Screenshot**: Full page screenshot showing current state
2. **Fresh DOM**: Current DOM structure (see below)

## Your Tasks:

### 1. Analyze the Screenshot:
- Is the page blank/white/error page? → Recovery: refresh page
- Is element blocked by overlay/modal/hover menu? → Recovery: close it (ESC, click outside, move mouse away)
- Is element not visible on screen? → Recovery: scroll to element
- Is element in a different tab/section? → Recovery: click correct tab

### 2. Check the DOM:
- Does the selector exist in the DOM?
- If wrong selector, find the CORRECT one from the DOM
- Is element hidden (display:none)?

### 3. Generate Recovery Steps:
Return JSON array with:
- **Recovery actions** (if needed): refresh, press_key (ESC), click outside, scroll, wait, move_mouse_away, etc.
- **Corrected failed step** (with fixed selector if needed)
- **All remaining steps** to complete the form

## Available Recovery Actions:
- `refresh`: Reload the page
- `press_key`: Press a key (e.g., "ESC" to close modals)
- `click`: Click element to close overlays
- `scroll`: Scroll to element
- `wait`: Wait for element to appear
- `hover`: Move mouse away from hover menus (use offset coordinates)

## Important Notes:
- If the screenshot shows the page is functioning normally but element just isn't found, the selector is likely wrong - find the correct one
- If there's a hover menu open from previous steps, you MUST add a recovery action to close it (move mouse away or press ESC)
- Always return the FULL remaining test plan, not just the recovery

## Test Cases:
{json.dumps(test_cases, indent=2)}

## Current DOM:
```html
{fresh_dom}
```

## Response Format:
Return ONLY a JSON array of step objects. Each step must have:
- step_number: sequential number
- action: one of (fill, select, click, verify, navigate, wait, scroll, switch_to_frame, switch_to_default, switch_to_shadow_root, hover, refresh, press_key)
- selector: CSS selector at first priority
- value: value for the action (if applicable)
- description: what this step does

Example response:
```json
[
  {{"step_number": 1, "action": "press_key", "selector": "body", "value": "ESC", "description": "Close any open overlays"}},
  {{"step_number": 2, "action": "click", "selector": ".star[data-rating='4']", "description": "Click 4-star rating"}},
  {{"step_number": 3, "action": "fill", "selector": "input#field1", "value": "test", "description": "Fill field 1"}}
]
```

Return ONLY the JSON array, no other text.
"""
        
        return prompt


    def generate_alert_handling_steps(
        self,
        alert_info: Dict,
        executed_steps: List[Dict],
        screenshot_path: str,
        test_cases: List[Dict],
        test_context,
        step_where_alert_appeared: int
    ) -> List[Dict]:
        """
        Generate steps to handle a JavaScript alert/confirm/prompt with AI vision
        
        Args:
            alert_info: Dict with 'type' and 'text' of the alert
            executed_steps: Steps completed before alert appeared
            screenshot_path: Path to screenshot showing the alert
            test_cases: Active test cases
            test_context: Test context
            step_where_alert_appeared: Step number that triggered the alert
            
        Returns:
            List of steps to handle alert + continue with remaining steps
        """
        import base64
        import re
        
        try:
            print(f"[AIHelper] Generating alert handling steps...")
            
            # Build the prompt (screenshot is optional for alerts)
            prompt = self._build_alert_handling_prompt(
                alert_info=alert_info,
                executed_steps=executed_steps,
                test_cases=test_cases,
                test_context=test_context,
                step_where_alert_appeared=step_where_alert_appeared
            )
            
            # Call Claude (with or without screenshot) using retry logic
            result_logger_gui.info("[AIHelper] Sending alert handling request to Claude API...")
            
            # Build message content
            message_content = []
            
            # Add screenshot if available (not for JS alerts)
            if screenshot_path:
                with open(screenshot_path, 'rb') as f:
                    screenshot_data = base64.standard_b64encode(f.read()).decode('utf-8')
                message_content.append({
                    "type": "image",
                    "source": {
                        "type": "base64",
                        "media_type": "image/png",
                        "data": screenshot_data
                    }
                })
            
            # Add text prompt
            message_content.append({
                "type": "text",
                "text": prompt
            })
            
            # Use multimodal retry if we have image, otherwise use regular retry
            if screenshot_path:
                response_text = self._call_api_with_retry_multimodal(message_content, max_tokens=16000, max_retries=3)
            else:
                response_text = self._call_api_with_retry(prompt, max_tokens=16000, max_retries=3)
            
            if response_text is None:
                print("[AIHelper] ❌ Failed to get alert handling response after retries")
                logger.error("[AIHelper] Failed to get alert handling response after retries")
                return []
            
            print(f"[AIHelper] Received alert handling response ({len(response_text)} chars)")
            logger.info(f"[AIHelper] Received alert handling response ({len(response_text)} chars)")
            
            # Extract JSON from response
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                alert_steps = json.loads(json_match.group())
                print(f"[AIHelper] Successfully parsed {len(alert_steps)} alert handling steps")
                logger.info(f"[AIHelper] Successfully parsed {len(alert_steps)} alert handling steps")
                return alert_steps
            else:
                print("[AIHelper] No JSON array found in alert handling response")
                logger.warning("[AIHelper] No JSON array found in alert handling response")
                return []
                
        except Exception as e:
            print(f"[AIHelper] Error generating alert handling steps: {e}")
            logger.error(f"[AIHelper] Error generating alert handling steps: {e}")
            return []
    
    def _build_alert_handling_prompt(
        self,
        alert_info: Dict,
        executed_steps: List[Dict],
        test_cases: List[Dict],
        test_context,
        step_where_alert_appeared: int
    ) -> str:
        """Build the prompt for alert handling"""
        
        alert_type = alert_info.get('type', 'alert')
        alert_text = alert_info.get('text', '')
        
        # Build executed steps context
        executed_context = ""
        if executed_steps:
            executed_context = f"""
Steps completed before alert appeared:
{json.dumps([{"step": i+1, "action": s.get("action"), "description": s.get("description")} for i, s in enumerate(executed_steps)], indent=2)}
"""
        
        prompt = f"""
# JAVASCRIPT ALERT HANDLING

A JavaScript alert/dialog appeared after step {step_where_alert_appeared}. Your job is to generate steps to handle it and continue the test.

## Alert Information:
- **Type**: {alert_type} (detected programmatically)
- **Text**: "{alert_text}"

**Note**: JavaScript alerts block all page interactions, so no screenshot is available. You must determine the appropriate action based on the alert type and text.

{executed_context}

## Your Tasks:

### 1. FIRST STEP - Accept/Dismiss the Alert:
**YOUR VERY FIRST STEP MUST ALWAYS BE TO ACCEPT OR DISMISS THE ALERT!**
- For "alert": Generate `accept_alert` action as FIRST step
- For "confirm": Generate `accept_alert` or `dismiss_alert` as FIRST step
- For "prompt": Generate `fill_alert` then `accept_alert` as first steps

### 2. Analyze the Alert Text:
Read the alert text carefully to understand what it's telling you:

**If the alert is a VALIDATION ERROR** (contains phrases like "required", "Please fill in", "missing fields", "must complete"):
- The alert is telling you which fields are missing or incomplete
- You need to go back and fill those specific fields BEFORE retrying
- Parse the alert text to identify WHICH fields need to be filled

**Example alert text:**
"Please fill in all required fields:
1. Street Address is required
2. City is required  
3. Emergency Contact Name is required"

**What this means:**
- You skipped or didn't complete these fields
- You need to navigate to the tabs/sections where these fields are located
- Fill ALL the missing fields mentioned in the alert
- THEN retry the action that triggered the alert

### 3. Generate Recovery Steps (After Accepting Alert):

**A. If validation error - Fix the missing fields:**

1. Identify which tabs/sections contain the missing fields:
   - Address fields (Street, City, State, ZIP) → Usually in "Address" tab or iframe
   - Emergency Contact fields → Usually in Address tab's nested iframe
   - Preferences fields (Rating, Options) → Usually in "Preferences" tab
   - Comments/Notes → Usually in main Details tab

2. Navigate to those tabs/sections:
   - Click the appropriate tab button
   - Switch to iframe if needed (switch_to_frame)
   - Handle any confirmation dialogs

3. Fill ALL the missing fields mentioned in the alert

4. Navigate through ALL remaining required tabs/sections that weren't completed

5. Retry the action that caused the alert (e.g., click "Next" or "Submit" button again)

**B. If not a validation error (success message, confirmation, etc.):**
- Just continue with remaining steps to complete the form

### 4. Example Response for Validation Error:

```json
[
  {{"step_number": 1, "action": "accept_alert", "selector": "", "value": "", "description": "Accept validation error alert"}},
  {{"step_number": 2, "action": "fill", "selector": "textarea#comments", "value": "Additional comments", "description": "Fill Additional Comments field"}},
  {{"step_number": 3, "action": "click", "selector": "button.tab-button[onclick='showTab(\\'address\\')']", "description": "Click Address tab"}},
  {{"step_number": 4, "action": "switch_to_frame", "selector": "iframe#addressIframe", "description": "Switch to address iframe"}},
  {{"step_number": 5, "action": "fill", "selector": "input#street", "value": "123 Main St", "description": "Fill Street Address"}},
  {{"step_number": 6, "action": "fill", "selector": "input#city", "value": "New York", "description": "Fill City"}},
  {{"step_number": 7, "action": "select", "selector": "select#state", "value": "NY", "description": "Select State"}},
  {{"step_number": 8, "action": "fill", "selector": "input#zipCode", "value": "10001", "description": "Fill ZIP Code"}},
  {{"step_number": 9, "action": "switch_to_frame", "selector": "iframe#contactIframe", "description": "Switch to nested contact iframe"}},
  {{"step_number": 10, "action": "fill", "selector": "input#emergencyName", "value": "Jane Doe", "description": "Fill Emergency Contact Name"}},
  {{"step_number": 11, "action": "switch_to_default", "description": "Switch back to main content"}},
  {{"step_number": 12, "action": "click", "selector": "button.tab-button[onclick='showTab(\\'preferences\\')']", "description": "Click Preferences tab"}},
  {{"step_number": 13, "action": "fill", "selector": "textarea#ratingComment", "value": "Great service", "description": "Fill Rating Comment"}},
  {{"step_number": 14, "action": "click", "selector": "input#terms", "description": "Check terms and conditions"}},
  {{"step_number": 15, "action": "click", "selector": "button[onclick='validateAndGoToPartTwo()']", "description": "Retry clicking Next: Part 2 button"}}
]
```

## Available Alert Actions:
- `accept_alert`: Click OK button (no selector needed)
- `dismiss_alert`: Click Cancel button (no selector needed)  
- `fill_alert`: Fill prompt input field (provide value)

## Test Cases:
{json.dumps(test_cases, indent=2)}

## Response Format:
Return ONLY a JSON array of step objects. Your FIRST step must ALWAYS be accept_alert or dismiss_alert!

Return ONLY the JSON array, no other text.
"""
        
        return prompt
