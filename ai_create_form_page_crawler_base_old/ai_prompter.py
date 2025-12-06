# ai_form_mapper_main_prompter.py
# AI-Powered Test Step Generation using Claude API

import json
import time
import logging
import anthropic
from typing import List, Dict, Optional, Any

logger = logging.getLogger('init_logger.form_page_test')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')


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
            is_first_iteration: bool = False
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

        prompt = f"""You are a test automation expert generating Selenium WebDriver test steps for a form page.

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
           ✅ input[name='email']                ← Good: form attributes
           ✅ button[type='submit']              ← Good: semantic attributes
           ✅ [aria-label='Close']               ← Good: accessibility attributes
           ✅ a[href='/next-page']               ← Good: semantic attributes

        **Priority 2 - IDs and Classes:**
           ✅ #login-form                        ← Unique ID
           ✅ .submit-button                     ← Specific class
           ✅ .form-section .input-field         ← Class with context

        **Priority 3 - Structural (LAST RESORT):**
           ✅ form > button:nth-child(2)         ← Structural selector
           ✅ .tab-content input:first-child     ← Structural with context
           ✅ .field-list > div:first-child      ← First item in list

        **WRONG vs RIGHT Examples:**

        ❌ "selector": "button:has-text('Submit')"
        ✅ "selector": "button[type='submit']"

        ❌ "selector": "button:contains('Next')"  
        ✅ "selector": "button.next-button"

        ❌ "selector": "input[name='email']:has-text('Email')"
        ✅ "selector": "input[name='email']"

        ❌ "selector": "//h2[text()='Personal Information']"
        ✅ "selector": "h2.section-title"

        ❌ "selector": "//div[contains(text(), 'Success')]"
        ✅ "selector": ".alert-success"

        **Key Rule: NEVER select elements by their text content! Always use attributes or structure!**

        === END CRITICAL SECTION ===


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
        3. Fill ALL fields that appear as a result
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
        - wait: Wait for duration
        - scroll: Scroll to element

        **Special Access Tools (use when needed to reach fields):**
        - switch_to_frame: Access fields inside iframe
        - switch_to_parent_frame: Navigate back one iframe level
        - switch_to_default: Return to main page context
        - switch_to_shadow_root: Access fields inside shadow DOM

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
           - "selector": string or null (CSS selector - MUST follow rules above!)
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
    - "Click next to go to payment section"
    - "Complete payment fields"
    - "Submit form"
    - "Verify success confirmation"

    Focus on:
    - Unused form fields or sections
    - Different paths through conditional logic
    - Alternative dropdown/radio selections
    - Edge cases or validation scenarios
    - Multi-step form flows

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
            
            # Call Claude with vision
            result_logger_gui.info("[AIHelper] Sending failure recovery request to Claude API with vision...")
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                messages=[
                    {
                        "role": "user",
                        "content": [
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
                    }
                ]
            )
            
            response_text = message.content[0].text
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
- selector: CSS selector
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
            
            # Call Claude (with or without screenshot)
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
            
            message = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                messages=[
                    {
                        "role": "user",
                        "content": message_content
                    }
                ]
            )
            
            response_text = message.content[0].text
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

### 1. Analyze the Alert:
- Based on the type ({alert_type}) and text, determine what action is needed
- For "alert": just accept it
- For "confirm": decide to accept or dismiss based on context (usually accept to continue)
- For "prompt": provide appropriate input value and accept

### 2. Generate Alert Handling Steps:

**For type "alert" (just OK button):**
- Generate: `accept_alert` action

**For type "confirm" (OK/Cancel buttons):**
- Decide based on context whether to accept or dismiss
- Generate: `accept_alert` or `dismiss_alert` action

**For type "prompt" (text input + OK/Cancel):**
- Generate: `fill_alert` action with appropriate value
- Then: `accept_alert` action

### 3. Continue with Remaining Steps:
After handling the alert, generate all remaining steps to complete the form submission.

## Available Alert Actions:
- `accept_alert`: Click OK button (no selector needed)
- `dismiss_alert`: Click Cancel button (no selector needed)  
- `fill_alert`: Fill prompt input field (provide value)

## Test Cases:
{json.dumps(test_cases, indent=2)}

## Response Format:
Return ONLY a JSON array of step objects:

```json
[
  {{"step_number": 1, "action": "accept_alert", "selector": "", "value": "", "description": "Accept confirmation dialog"}},
  {{"step_number": 2, "action": "switch_to_frame", "selector": "iframe#addressIframe", "description": "Switch to address iframe"}},
  {{"step_number": 3, "action": "fill", "selector": "input#street", "value": "123 Main St", "description": "Fill street"}}
]
```

Or for prompt:
```json
[
  {{"step_number": 1, "action": "fill_alert", "selector": "", "value": "John Doe", "description": "Fill name in prompt"}},
  {{"step_number": 2, "action": "accept_alert", "selector": "", "value": "", "description": "Accept prompt"}},
  {{"step_number": 3, "action": "fill", "selector": "input#nextField", "value": "data", "description": "Continue filling form"}}
]
```

Return ONLY the JSON array, no other text.
"""
        
        return prompt
