# ai_all_form_pages_main_prompter.py
# AI-Powered Form Page Discovery using Claude API

import json
import time
import logging
import anthropic
import random
from typing import List, Dict, Optional, Any
from anthropic._exceptions import OverloadedError, APIError

logger = logging.getLogger('init_logger.form_page_discovery')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_discovery')


class AIHelper:
    """Helper class for AI-powered form page discovery using Claude API"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required for AI functionality")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
    
    def _call_api_with_retry_multimodal(self, content: list, max_tokens: int = 16000, max_retries: int = 3) -> Optional[str]:
        """
        Call Claude API with retry logic for multimodal content (images + text)
        
        Args:
            content: List of content blocks (can include images and text)
            max_tokens: Maximum tokens for response
            max_retries: Number of retry attempts
            
        Returns:
            Response text or None if all retries fail
        """
        delay = 2
        
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

    def generate_exploration_steps(
            self,
            dom_html: str,
            executed_steps: Optional[List[Dict]] = None,
            screenshot_base64: str = None,
            already_cataloged_pages: Optional[List[str]] = None
    ) -> Dict[str, Any]:
        """
        Generate exploration steps for discovering form pages in a web application.
        Uses DFS (Depth-First Search) strategy to navigate through the application.
        
        Args:
            dom_html: Current page DOM
            executed_steps: Steps executed so far (for context and loop prevention)
            screenshot_base64: Screenshot for UI verification and navigation decisions
            already_cataloged_pages: List of form pages already discovered
            
        Returns:
            Dict with:
            - steps: List of next exploration steps
            - exploration_complete: Boolean indicating if exploration is done
            - ui_issue: String describing any UI problems
        """
        
        if executed_steps is None:
            executed_steps = []
        if already_cataloged_pages is None:
            already_cataloged_pages = []
        
        # Build context about what's been done
        executed_context = ""
        if executed_steps:
            # Show last 20 steps for context
            recent_steps = executed_steps[-20:] if len(executed_steps) > 20 else executed_steps
            executed_context = f"""
## Steps Executed So Far:
(Showing last {len(recent_steps)} of {len(executed_steps)} total steps)

{json.dumps(recent_steps, indent=2)}

**Important**: Use these steps to:
1. Understand the current navigation path
2. Avoid clicking things already explored (check for form_page_info in steps)
3. Determine if you need to backtrack
"""
        
        cataloged_context = ""
        if already_cataloged_pages:
            cataloged_context = f"""
## Form Pages Already Cataloged:
{json.dumps(already_cataloged_pages, indent=2)}

**Do NOT navigate back to these pages.**
"""
        
        # Main prompt
        prompt = f"""
# WEB APPLICATION FORM PAGE DISCOVERY

You are exploring a web application to discover ALL form pages using Depth-First Search (DFS).

{executed_context}

{cataloged_context}

## Current Page DOM:
```html
{dom_html}
```

## UI Verification Task:

Examine the screenshot for visual defects:
- Overlapping elements blocking content
- Missing images (broken image icons)
- Misaligned text or buttons
- Layout issues (elements outside boundaries)
- Contrast issues (unreadable text)
- Broken styles

If you find UI issues, include them in your response under "ui_issue" field.

## CRITICAL - Verify Last Step Actually Happened:

**BEFORE generating new steps, analyze if the last executed step actually worked:**
- Compare the current DOM and screenshot with what you expected after the last step
- Did the expected element appear? Did navigation happen? Did content change?
- If the last step FAILED (nothing changed, no expected result):
  - DO NOT move forward
  - Generate the SAME step again with a BETTER selector
  - Or find an alternative way to achieve the same goal

**Example:** If last step was "Click Add button" but screenshot shows no form opened → The click failed, retry with better selector

## Your Mission:

**STEP 1: Analyze Current Page**

Check if this page is a FORM PAGE:
- Has multiple input fields (text, select, checkbox, radio, textarea, etc.)
- Has a save/submit/update button
- Purpose is to CREATE or EDIT data (not search/filter/view)

**CRITICAL - Form Page vs Search Page:**
- ✅ FORM PAGE: Creates NEW records or EDITS existing records (Add User, Edit Product, Create Invoice)
- ❌ NOT A FORM PAGE: Search forms, filter forms, view-only pages with fields
- Search/filter pages have fields but they only FIND data, not CREATE/EDIT it
- If the page has "Search" button and displays results table → NOT a form page

**IMPORTANT - What NOT to catalog:**
- User profile/account/settings forms (personal info, password change, preferences)
- Login/authentication pages
- Search/filter forms (only find data, don't create/edit)
- Only catalog BUSINESS ENTITY forms (records that represent business data)

**Two ways to find form pages:**
1. **Navigation reveals it**: Clicked tab/dropdown → landed on form page
2. **Entry point button**: "Add", "Create", "New", "Edit", "+" buttons that open forms

**Form Page Naming:**
Choose a descriptive snake_case name that reflects the entity/purpose:
- Good: "new_customer", "invoice", "product", "order_management"
- Bad: "form1", "add_form", "page", "user_search"

**Parent Reference Fields:**
Identify fields that reference parent entities (foreign keys):
- Look at field names: "customer_name", "customer_id", "order_id", "category_name"
- Analyze JavaScript: function names like "saveCustomer()", "loadOrder()" indicate parent entities
- Check attributes: data-parent, data-entity, onclick handlers
- A form page can have MULTIPLE parent references

For each parent reference field, capture:
- Field name (e.g., "customer_name")
- Parent entity (e.g., "customer")
- How you identified it (field name / JS function / attribute)

**STEP 2: Decide Next Actions**

If NOT a form page, generate exploration steps using DFS:

**PRIMARY GOAL: Find FORM PAGES (pages with input fields for creating/editing business data)**

**CRITICAL - COMPLETELY IGNORE Search/Filter Areas:**
- If you see search fields, filter fields, or search/reset buttons → IGNORE THEM COMPLETELY
- DO NOT click search/filter buttons
- DO NOT fill search/filter fields
- DO NOT press ESC to close them
- DO NOT click Reset/Clear buttons
- Search/filter areas are IRRELEVANT to form page discovery - skip them entirely
- Focus ONLY on navigation that leads to CREATE/EDIT forms (Add, New, Edit buttons and menu items)

**CRITICAL - NEVER Click These (they DON'T lead to form pages):**
- Search buttons - COMPLETELY IGNORE
- Reset/Clear buttons - COMPLETELY IGNORE
- Filter dropdowns/fields - COMPLETELY IGNORE
- View/Display buttons - only show data, no form
- Export/Download/Print buttons
- Data table rows/cells
- Reports/dashboards
- Verify/Validate buttons

**Navigation Strategy:**
- Click tabs, menu items, dropdown options
- Click entry point buttons (Add, Create, New, Edit, +)
- Dive deep into each option before moving to siblings
- When no more options → backtrack to last junction point
- SKIP any search/filter sections - they're not part of navigation

**What NOT to click (these don't lead to form pages):**
- Search buttons - only filter data, don't open forms
- View/Display buttons - only show data, no form
- Export/Download/Print buttons
- Data table rows/cells
- Reports/dashboards
- Verify/Validate buttons
- Filter/Sort options

**Junction Points** (where to return after deep dive):
- Tabs with multiple options
- Dropdown menus
- Radio buttons that change content
- Any navigation revealing different fields

**CRITICAL RULE:**
When generating steps, STOP at form page detection.
Do NOT include steps that go through/past a form page.

**Modals:**
If modal appears:
1. Check if it's a form page → Catalog it
2. If not → Close it (click X, press ESC) and continue

**Loop Prevention:**
- Check executed_steps to see what's been clicked
- Don't click same navigation twice
- If all options explored at current level → indicate backtracking needed

**Completion Detection:**
If you've explored all navigation options and there's nothing left to click, set:
`exploration_complete: true`

## Response Format:

Return ONLY a valid JSON object:

```json
{{
  "steps": [
    {{
      "step_number": 1,
      "action": "click",
      "selector": "#inventory-tab",
      "description": "Click Inventory tab"
    }},
    {{
      "step_number": 2,
      "action": "click",
      "selector": "#add-product",
      "description": "Click Add Product button",
      "form_page_info": {{
        "form_name": "new_product",
        "navigation_path": "Inventory → Products → Add Product",
        "navigation_steps": [
          {{"step_number": 1, "action": "click", "selector": "#inventory-tab", "description": "Click Inventory tab"}},
          {{"step_number": 2, "action": "click", "selector": "#add-product", "description": "Click Add Product button"}}
        ],
        "parent_fields": [
          {{
            "field_name": "category_id",
            "parent_entity": "category",
            "identified_by": "field name pattern"
          }}
        ],
        "field_types": ["text", "number", "select"]
      }}
    }}
  ],
  "exploration_complete": false,
  "ui_issue": ""
}}
```

**CRITICAL - Form Page Info Structure:**
When you detect a form page, attach `form_page_info` to the SPECIFIC STEP that enters the form page.

The `form_page_info` must include:
- `form_name`: snake_case name (e.g., "new_product", "invoice", "customer")
- `navigation_path`: Text description of path
- `navigation_steps`: ACTUAL executable Selenium steps to reach this form page (so we can navigate to it later)
- `parent_fields`: Array of parent reference fields (if any)
- `field_types`: Array of field types found

**Note about executed_steps:**
When I send you executed_steps, some steps may already have `form_page_info` attached - these are form pages you already discovered. Use this to avoid cataloging the same form twice.

**Actions available:**
- click: Click element
- hover: Hover over element
- wait: Wait for element to appear
- scroll: Scroll to element
- switch_to_frame: Enter iframe
- switch_to_shadow_root: Enter shadow DOM
- switch_to_default: Exit iframe/shadow DOM
- press_key: Press keyboard key (e.g., "ESC")

**CRITICAL - CSS Selector Rules:**
- Use ONLY valid CSS selectors supported by Selenium (class, id, attribute, tag, nth-child, etc.)
- DO NOT use :contains() - not supported by Selenium
- DO NOT use :has() - not supported by Selenium
- DO NOT use any jQuery-specific or CSS4 pseudo-selectors
- Valid examples: button.oxd-button, #submit-btn, button[type="submit"], div.form-container > button
- Invalid examples: button:contains('Add'), button:has(i.icon), div:has(text), a[href*='partial']

**CRITICAL - Selector Reliability (MUST WORK - No Failures!):**
- BEFORE suggesting a selector, VERIFY in the DOM that element exists and is unique
- Count how many elements match your selector - if more than 1, make it more specific
- Choose selectors that target VISIBLE, ENABLED, CLICKABLE elements ONLY
- NEVER use partial attribute matching (href*=, class*=) - use exact matches
- NEVER use generic selectors like "button", "a", "span" without specific classes/attributes
- For buttons: Use FULL class names, not partial: button.oxd-button.oxd-button--medium.oxd-button--secondary
- For links: Use exact href attribute: a[href='/exact/path'] NOT a[href*='partial']
- Test: "Does this EXACT selector exist in the DOM? Is it unique? Is it clickable?"
- If unsure, use multiple classes or attributes to make selector ultra-specific

**Selector Best Practices:**
- Prefer: id > multiple unique classes > data attributes > exact href/attribute match
- ALWAYS use full class names, not abbreviated
- Avoid nth-child unless element has no other way to identify it

**CRITICAL - Dropdown Handling:**
- Dropdowns require TWO steps: (1) Click dropdown trigger, (2) Click item inside
- Look for dropdown triggers: chevron icons, aria-expanded, role="button", clickable span/div

**Important:**
- Generate maximum 2 steps per response
- If form page detected, attach form_page_info to the step that enters it
- Always check executed_steps to avoid loops
- Stop generating steps when you detect a form page

**CRITICAL - Response Format:**
Return ONLY a valid JSON object. NO explanations, NO comments, NO text before or after the JSON.
Your ENTIRE response must be ONLY the JSON object and nothing else.
"""
        
        # Call API with screenshot
        content = [
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
        response_text = self._call_api_with_retry_multimodal(content, max_tokens=16000, max_retries=3)
        
        if response_text is None:
            print("[AIHelper] ❌ Failed to get exploration response after retries")
            logger.error("[AIHelper] Failed to get exploration response after retries")
            return {
                "steps": [],
                "exploration_complete": False,
                "ui_issue": ""
            }
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
                print(f"[AIHelper] ✅ Parsed exploration response")
                logger.info(f"[AIHelper] Parsed exploration response: steps={len(result.get('steps', []))}")
                return result
            except json.JSONDecodeError as e:
                print(f"[AIHelper] ❌ JSON parsing error: {e}")
                logger.error(f"[AIHelper] JSON parsing error: {e}")
                return {
                    "steps": [],
                    "exploration_complete": False,
                    "ui_issue": ""
                }
        else:
            print("[AIHelper] ❌ No JSON object found in response")
            logger.error("[AIHelper] No JSON object found in response")
            return {
                "steps": [],
                "exploration_complete": False,
                "ui_issue": ""
            }

    def analyze_failure_and_recover(
            self,
            failed_step: Dict,
            executed_steps: List[Dict],
            fresh_dom: str,
            screenshot_path: str,
            test_cases: List[Dict],
            test_context: Any,
            attempt_number: int
    ) -> List[Dict]:
        """
        Analyze a failed step and generate ONE corrective step to replace it.
        
        Args:
            failed_step: The step that failed
            executed_steps: All steps executed successfully so far
            fresh_dom: Current page DOM
            screenshot_path: Path to screenshot of current state
            test_cases: Available test cases
            test_context: Current test context
            attempt_number: Which retry attempt this is
            
        Returns:
            List with ONE corrective step to replace the failed step
        """
        
        # Build context about executed steps
        executed_context = ""
        if executed_steps:
            recent_steps = executed_steps[-10:] if len(executed_steps) > 10 else executed_steps
            executed_context = f"""
## Steps Successfully Executed So Far:
(Showing last {len(recent_steps)} of {len(executed_steps)} total steps)

{json.dumps(recent_steps, indent=2)}
"""
        
        # Build context about the failed step
        failed_step_context = f"""
## Failed Step (Attempt #{attempt_number}):
{json.dumps(failed_step, indent=2)}

**Why it failed:** Element not found or action couldn't be executed
"""
        
        prompt = f"""
# STEP FAILURE RECOVERY

You are helping recover from a failed step during form exploration.

{executed_context}

{failed_step_context}

## Current Page DOM:
```html
{fresh_dom}
```

## Your Task:

Generate **EXACTLY ONE** corrective step to replace the failed step.

**Analysis:**
1. Why did the step fail? (selector wrong? element hidden? wrong action?)
2. What's the correct way to achieve the same goal?
3. Is the element available but with a different selector?
4. Should we try a different action (click → hover, etc.)?

**CRITICAL - Dropdown Analysis:**
- Is the target element a DROPDOWN?
- Dropdowns often fail because the selector targets the container, not the clickable trigger
- Look for: chevron icons, aria-expanded, role="button", dropdown-toggle classes
- The clickable element is usually a child span, button, or div inside the dropdown container
- Try targeting the actual clickable element (often has onclick handler or cursor pointer)

**Important:**
- Return ONLY ONE step that corrects the failure
- Keep the same goal as the failed step
- Use a different approach (different selector, action, or strategy)
- The corrective selector MUST target the exact same UI element but with a different locator
- If it's a dropdown, target the clickable trigger element, not the container
- Prefer specific selectors: id > unique class > data attributes > tag+class
- If the element truly doesn't exist, choose an alternative navigation path

**CRITICAL - CSS Selector Rules:**
- Use ONLY valid CSS selectors (class, id, attribute, tag, nth-child, etc.)
- DO NOT use :contains() - it's not valid CSS (it's jQuery-only)
- DO NOT use any jQuery-specific pseudo-selectors
- Valid examples: button.oxd-button, #submit-btn, button[type="submit"], div.form-container > button
- Invalid examples: button:contains('Add'), div:has(text)

## Response Format:

Return ONLY a valid JSON object with ONE step:

```json
{{
  "steps": [
    {{
      "step_number": 1,
      "action": "click",
      "selector": "corrected CSS selector",
      "description": "Corrected action description"
    }}
  ]
}}
```

**Available actions:**
- click, hover, wait, scroll, fill, select, switch_to_frame, switch_to_shadow_root, switch_to_default, press_key

Return ONLY the JSON object, no other text.
"""
        
        # Call API (text only, no screenshot needed)
        content = [
            {
                "type": "text",
                "text": prompt
            }
        ]
        
        response_text = self._call_api_with_retry_multimodal(content, max_tokens=4000, max_retries=3)
        
        if response_text is None:
            print("[AIHelper] ❌ Failed to get failure recovery response")
            logger.error("[AIHelper] Failed to get failure recovery response")
            return []
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
                steps = result.get("steps", [])
                print(f"[AIHelper] ✅ Generated {len(steps)} corrective step(s)")
                logger.info(f"[AIHelper] Generated {len(steps)} corrective step(s)")
                return steps
            except json.JSONDecodeError as e:
                print(f"[AIHelper] ❌ JSON parsing error: {e}")
                logger.error(f"[AIHelper] JSON parsing error: {e}")
                return []
        else:
            print("[AIHelper] ❌ No JSON object found in response")
            logger.error("[AIHelper] No JSON object found in response")
            return []

    def discover_login_fields(
            self,
            dom_html: str,
            screenshot_base64: str
    ) -> List[Dict]:
        """
        Discover login fields on a login page and generate login steps.
        
        Args:
            dom_html: Login page DOM
            screenshot_base64: Screenshot of login page
            
        Returns:
            List of 3 steps: [fill username, fill password, click login]
        """
        
        prompt = f"""
# LOGIN PAGE FIELD DISCOVERY

Analyze this login page and generate steps to log in.

## Current Page DOM:
```html
{dom_html}
```

## Task:

Generate EXACTLY 3 steps to log in:
1. Fill username field with placeholder value "{{{{USERNAME}}}}"
2. Fill password field with placeholder value "{{{{PASSWORD}}}}"
3. Click login/submit button

## Response Format:

Return ONLY a valid JSON object:

```json
{{{{
  "steps": [
    {{{{
      "step_number": 1,
      "action": "fill",
      "selector": "CSS selector for username field",
      "value": "{{{{{{{{USERNAME}}}}}}}}",
      "description": "Fill username field"
    }}}},
    {{{{
      "step_number": 2,
      "action": "fill",
      "selector": "CSS selector for password field",
      "value": "{{{{{{{{PASSWORD}}}}}}}}",
      "description": "Fill password field"
    }}}},
    {{{{
      "step_number": 3,
      "action": "click",
      "selector": "CSS selector for login button",
      "value": "",
      "description": "Click login button"
    }}}}
  ]
}}}}
```

Return ONLY the JSON object, no other text.
"""
        
        # Call API with screenshot
        content = [
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
        
        response_text = self._call_api_with_retry_multimodal(content, max_tokens=4000, max_retries=3)
        
        if response_text is None:
            print("[AIHelper] ❌ Failed to get login field discovery response")
            logger.error("[AIHelper] Failed to get login field discovery response")
            return []
        
        # Parse JSON response
        import re
        json_match = re.search(r'\{[\s\S]*\}', response_text)
        if json_match:
            try:
                result = json.loads(json_match.group())
                steps = result.get("steps", [])
                print(f"[AIHelper] ✅ Discovered {len(steps)} login steps")
                logger.info(f"[AIHelper] Discovered {len(steps)} login steps")
                return steps
            except json.JSONDecodeError as e:
                print(f"[AIHelper] ❌ JSON parsing error: {e}")
                logger.error(f"[AIHelper] JSON parsing error: {e}")
                return []
        else:
            print("[AIHelper] ❌ No JSON object found in response")
            logger.error("[AIHelper] No JSON object found in response")
            return []
