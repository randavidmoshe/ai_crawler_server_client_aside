# ai_error_recovery.py
# AI-Powered Error Recovery and Alert Handling using Claude API

import json
import time
import logging
import anthropic
import random
from typing import List, Dict, Optional, Any
from anthropic._exceptions import OverloadedError, APIError

logger = logging.getLogger('init_logger.form_page_test')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')


class AIErrorRecovery:
    """Helper class for AI-powered error recovery and alert handling using Claude API"""
    
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
                print(f"[AIErrorRecovery] Calling Claude API (attempt {attempt + 1}/{max_retries})...")
                result_logger_gui.info(f"[AIErrorRecovery] Calling Claude API (attempt {attempt + 1}/{max_retries})...")
                
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
                print(f"[AIErrorRecovery] ✅ API call successful ({len(response_text)} chars)")
                return response_text
                
            except OverloadedError as e:
                if attempt == max_retries - 1:
                    # Last attempt failed
                    print(f"[AIErrorRecovery] ❌ API Overloaded after {max_retries} attempts. Giving up.")
                    logger.error(f"[AIErrorRecovery] API Overloaded after {max_retries} attempts: {e}")
                    return None
                
                # Add jitter to prevent thundering herd
                jitter = random.uniform(0, delay * 0.5)
                wait_time = delay + jitter
                
                print(f"[AIErrorRecovery] ⚠️  API Overloaded (529). Retrying in {wait_time:.1f}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIErrorRecovery] API Overloaded. Retry {attempt + 1}/{max_retries} after {wait_time:.1f}s")
                
                time.sleep(wait_time)
                delay *= 2  # Exponential backoff
                
            except APIError as e:
                if attempt == max_retries - 1:
                    print(f"[AIErrorRecovery] ❌ API Error after {max_retries} attempts: {e}")
                    logger.error(f"[AIErrorRecovery] API Error after {max_retries} attempts: {e}")
                    return None
                
                print(f"[AIErrorRecovery] ⚠️  API Error: {e}. Retrying in {delay}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIErrorRecovery] API Error. Retry {attempt + 1}/{max_retries} after {delay}s")
                
                time.sleep(delay)
                delay *= 2
                
            except Exception as e:
                print(f"[AIErrorRecovery] ❌ Unexpected error: {e}")
                logger.error(f"[AIErrorRecovery] Unexpected error: {e}")
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
                print(f"[AIErrorRecovery] Calling Claude API with vision for alert recovery (attempt {attempt + 1}/{max_retries})...")
                result_logger_gui.info(f"[AIErrorRecovery] Calling Claude API with vision for alert recovery (attempt {attempt + 1}/{max_retries})...")
                
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
                print(f"[AIErrorRecovery] ✅ API call successful ({len(response_text)} chars)")
                return response_text
                
            except OverloadedError as e:
                if attempt == max_retries - 1:
                    print(f"[AIErrorRecovery] ❌ API Overloaded after {max_retries} attempts. Giving up.")
                    logger.error(f"[AIErrorRecovery] API Overloaded after {max_retries} attempts: {e}")
                    return None
                
                jitter = random.uniform(0, delay * 0.5)
                wait_time = delay + jitter
                
                print(f"[AIErrorRecovery] ⚠️  API Overloaded (529). Retrying in {wait_time:.1f}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIErrorRecovery] API Overloaded. Retry {attempt + 1}/{max_retries} after {wait_time:.1f}s")
                
                time.sleep(wait_time)
                delay *= 2
                
            except APIError as e:
                if attempt == max_retries - 1:
                    print(f"[AIErrorRecovery] ❌ API Error after {max_retries} attempts: {e}")
                    logger.error(f"[AIErrorRecovery] API Error after {max_retries} attempts: {e}")
                    return None
                
                print(f"[AIErrorRecovery] ⚠️  API Error: {e}. Retrying in {delay}s... ({attempt + 1}/{max_retries})")
                logger.warning(f"[AIErrorRecovery] API Error. Retry {attempt + 1}/{max_retries} after {delay}s")
                
                time.sleep(delay)
                delay *= 2
                
            except Exception as e:
                print(f"[AIErrorRecovery] ❌ Unexpected error: {e}")
                logger.error(f"[AIErrorRecovery] Unexpected error: {e}")
                return None
        
        return None

    def regenerate_steps_after_alert(
        self,
        alert_info: Dict,
        executed_steps: List[Dict],
        dom_html: str,
        screenshot_path: Optional[str],
        test_cases: List[Dict],
        test_context,
        step_where_alert_appeared: int,
        include_accept_step: bool = True,
        gathered_error_info: Optional[Dict] = None  # NEW: For validation errors from DOM detection
    ) -> List[Dict]:
        """
        Generate steps to handle a JavaScript alert/confirm/prompt OR validation errors with AI vision
        
        Args:
            alert_info: Dict with 'type' and 'text' of the alert (or validation error info)
            executed_steps: Steps completed before alert appeared
            dom_html: Current DOM HTML after alert was accepted
            screenshot_path: Path to screenshot showing the alert
            test_cases: Active test cases
            test_context: Test context
            step_where_alert_appeared: Step number that triggered the alert
            include_accept_step: Whether AI should include accept_alert step in response
            gathered_error_info: Optional dict with 'error_fields' and 'error_messages' from DOM detection
            
        Returns:
            List of steps to handle alert + continue with remaining steps
        """
        import base64
        import re
        
        try:
            print(f"[AIErrorRecovery] Generating alert handling steps...")
            
            # Build the prompt (screenshot is optional for alerts)
            prompt = self._build_alert_handling_prompt(
                alert_info=alert_info,
                executed_steps=executed_steps,
                dom_html=dom_html,
                test_cases=test_cases,
                test_context=test_context,
                step_where_alert_appeared=step_where_alert_appeared,
                include_accept_step=include_accept_step,  # NEW: Pass to prompt builder
                gathered_error_info=gathered_error_info  # NEW: Pass gathered validation errors
            )
            
            # Call Claude (with or without screenshot) using retry logic
            result_logger_gui.info("[AIErrorRecovery] Sending alert handling request to Claude API...")
            
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
                print("[AIErrorRecovery] ❌ Failed to get alert handling response after retries")
                logger.error("[AIErrorRecovery] Failed to get alert handling response after retries")
                return []
            
            print(f"[AIErrorRecovery] Received alert handling response ({len(response_text)} chars)")
            logger.info(f"[AIErrorRecovery] Received alert handling response ({len(response_text)} chars)")
            
            # Extract JSON from response - now expecting object with "scenario" and "steps"
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                alert_response = json.loads(json_match.group())
                
                # Extract scenario
                scenario = alert_response.get("scenario", "B")  # Default to B if not specified
                
                if scenario == "A":
                    # Scenario A: Simple alert - just continue
                    alert_steps = alert_response.get("steps", [])
                    
                    if not alert_steps:
                        print("[AIErrorRecovery] No steps found in Scenario A response")
                        logger.warning("[AIErrorRecovery] No steps found in Scenario A response")
                        return {"scenario": "A", "steps": []}
                    
                    print(f"[AIErrorRecovery] Successfully parsed {len(alert_steps)} alert handling steps")
                    print(f"[AIErrorRecovery] Scenario: A")
                    logger.info(f"[AIErrorRecovery] Scenario A - {len(alert_steps)} steps")
                    
                    return {"scenario": "A", "steps": alert_steps}
                
                elif scenario == "B":
                    # Scenario B: Validation error - check issue_type
                    issue_type = alert_response.get("issue_type", "ai_issue")
                    problematic_fields = alert_response.get("problematic_fields", [])
                    
                    if issue_type == "real_issue":
                        # Real system bug
                        explanation = alert_response.get("explanation", "")
                        problematic_field_claimed = alert_response.get("problematic_field_claimed", "")
                        our_action = alert_response.get("our_action", "")
                        
                        print(f"[AIErrorRecovery] Scenario B: real_issue - System Bug")
                        print(f"[AIErrorRecovery] Explanation: {explanation}")
                        logger.warning(f"[AIErrorRecovery] Real issue detected: {explanation}")
                        
                        return {
                            "scenario": "B",
                            "issue_type": "real_issue",
                            "explanation": explanation,
                            "problematic_field_claimed": problematic_field_claimed,
                            "our_action": our_action,
                            "problematic_fields": problematic_fields,
                            "steps": []
                        }
                    
                    else:  # ai_issue
                        # AI testing error
                        alert_steps = alert_response.get("steps", [])
                        explanation = alert_response.get("explanation", "")
                        field_requirements = alert_response.get("field_requirements", "")
                        
                        if not alert_steps:
                            print("[AIErrorRecovery] No steps found in ai_issue response")
                            logger.warning("[AIErrorRecovery] No steps found in ai_issue response")
                            return {"scenario": "B", "issue_type": "ai_issue", "steps": [], "problematic_fields": [], "field_requirements": ""}
                        
                        print(f"[AIErrorRecovery] Successfully parsed {len(alert_steps)} alert handling steps")
                        print(f"[AIErrorRecovery] Scenario: B (ai_issue)")
                        print(f"[AIErrorRecovery] Problematic fields: {problematic_fields}")
                        print(f"[AIErrorRecovery] Field requirements: {field_requirements}")
                        logger.info(f"[AIErrorRecovery] Scenario B (ai_issue) - {len(alert_steps)} steps")
                        
                        return {
                            "scenario": "B",
                            "issue_type": "ai_issue",
                            "explanation": explanation,
                            "problematic_fields": problematic_fields,
                            "field_requirements": field_requirements,
                            "steps": alert_steps
                        }
                else:
                    print(f"[AIErrorRecovery] Unknown scenario: {scenario}")
                    return {"scenario": "B", "issue_type": "ai_issue", "steps": []}
            else:
                print("[AIErrorRecovery] No JSON object found in alert handling response")
                logger.warning("[AIErrorRecovery] No JSON object found in alert handling response")
                return {"scenario": "B", "steps": []}
                
        except Exception as e:
            print(f"[AIErrorRecovery] Error generating alert handling steps: {e}")
            logger.error(f"[AIErrorRecovery] Error generating alert handling steps: {e}")
            return []
    
    def _build_alert_handling_prompt(
        self,
        alert_info: Dict,
        executed_steps: List[Dict],
        dom_html: str,
        test_cases: List[Dict],
        test_context,
        step_where_alert_appeared: int,
        include_accept_step: bool = True,  # NEW: Control whether to include accept_alert step
        gathered_error_info: Optional[Dict] = None  # NEW: Validation errors from DOM detection
    ) -> str:
        """Build the prompt for alert handling"""
        
        alert_type = alert_info.get('type', 'alert')
        alert_text = alert_info.get('text', '')
        
        # Build executed steps context
        executed_context = ""
        if executed_steps:
            executed_context = f"""
Steps completed before alert appeared:
{json.dumps([{"step": i+1, "action": s.get("action"), "description": s.get("description"), "selector": s.get("selector"), "value": s.get("value")} for i, s in enumerate(executed_steps)], indent=2)}
"""
        
        # Build gathered error info section if provided
        gathered_info_section = ""
        if gathered_error_info:
            error_fields = gathered_error_info.get("error_fields", [])
            error_messages = gathered_error_info.get("error_messages", [])
            gathered_info_section = f"""
## GATHERED ERROR INFORMATION (From DOM Analysis):
**The system has already detected the following validation errors in the DOM:**

- **Error Fields Detected**: {', '.join(error_fields) if error_fields else 'None'}
- **Error Messages Detected**: {', '.join(error_messages) if error_messages else 'None'}

**IMPORTANT**: This is validation error information we gathered. You should:
1. Use this as a starting point
2. Also analyze the DOM yourself for additional error indicators
3. Also analyze the screenshot (if provided) for visual error indicators
4. Combine ALL sources to create complete list of problematic fields

"""
        
        prompt = f"""
# JAVASCRIPT ALERT HANDLING WITH SMART RECOVERY

## Context:
Step {step_where_alert_appeared} was executed successfully, but it triggered a JavaScript alert.
**IMPORTANT**: The system has ALREADY accepted/dismissed the alert automatically before calling you.

## Alert Information:
- **Type**: {alert_type}
- **Text**: "{alert_text}"

{gathered_info_section}{executed_context}

## Current DOM (After Alert Was Accepted):
```html
{dom_html}
```

## Your Task - TWO SCENARIOS:

You must decide which scenario applies and respond accordingly:

---

### SCENARIO A: Simple Alert (No Validation Errors)

**Use this when:** The alert is NOT complaining about missing or invalid fields. It's just a confirmation, success message, navigation warning, or generic notification.

**Your response should:**
1. Keep all executed steps 1-{step_where_alert_appeared} (they were successful)
2. {'Start generating steps from ' + str(step_where_alert_appeared + 1) + ' (system already added accept_alert to executed_steps)' if not include_accept_step else 'Add step ' + str(step_where_alert_appeared + 1) + ' as `accept_alert` (documenting what the system already did)'}
3. Add continuation steps to complete the form based on the current DOM

{f'**CRITICAL:** The system has already accepted the alert AND added it to executed_steps as step {step_where_alert_appeared + 1}. Your first generated step should be numbered {step_where_alert_appeared + 1} and should be the NEXT action after alert (e.g., switch_to_frame, fill, etc.). Do NOT include accept_alert in your response!' if not include_accept_step else f'**CRITICAL FOR STEP NUMBERING:** Steps must start from {step_where_alert_appeared + 1}, NOT from step 1! First step must be accept_alert.'}

**Example response for simple alert (if alert appeared at step 26):**
```json
{'[' if True else ''}
  {{{f'"step_number": {step_where_alert_appeared + 1}, "action": "switch_to_frame", "selector": "iframe#addressIframe", "value": "", "description": "Switch to address iframe"' if not include_accept_step else f'"step_number": {step_where_alert_appeared + 1}, "action": "accept_alert", "selector": "", "value": "", "description": "Alert accepted (already done by system)"'}}},
  {{{f'"step_number": {step_where_alert_appeared + 2}, "action": "fill", "selector": "input#street", "value": "123 Main St", "description": "Fill street address"' if not include_accept_step else f'"step_number": {step_where_alert_appeared + 2}, "action": "switch_to_frame", "selector": "iframe#addressIframe", "value": "", "description": "Switch to address iframe"'}}},
  {{{f'"step_number": {step_where_alert_appeared + 3}, "action": "fill", "selector": "input#city", "value": "New York", "description": "Fill city"' if not include_accept_step else f'"step_number": {step_where_alert_appeared + 3}, "action": "fill", "selector": "input#street", "value": "123 Main St", "description": "Fill street address"'}}}
]
```

---

### SCENARIO B: Validation Alert (Field Problems - Missing or Invalid)

**Use this ONLY when:** The alert is specifically complaining that fields are MISSING, REQUIRED, INVALID, or have ERRORS.

**Step 1: Parse Alert Text**
Extract ALL problematic field names/descriptions mentioned in the alert.

Example: "Please fill in: Street Address is required, City has invalid format, Emergency Contact Name is required"
→ Problematic fields: ["Street Address", "City", "Emergency Contact Name"]

**Step 2: Find ADDITIONAL Error Fields from DOM and Screenshot**
The alert text may not mention ALL fields with errors. Also check:

1. **DOM Analysis** - Look for fields with error indicators:
   - Classes like: `error`, `invalid`, `has-error`, `is-invalid`, `field-error`, `ng-invalid`, `validation-error`
   - Attributes like: `aria-invalid="true"`, `data-error="true"`
   - Error message elements near fields (like `<span class="error-message">` or `<div class="field-error">`)
   - Red border styles in inline CSS

2. **Screenshot Analysis** (if available):
   - Fields with red borders or red highlighting
   - Fields with red text or error icons next to them
   - Visual error indicators

3. **Combine All Sources**:
   - Create a COMPLETE list of ALL problematic fields
   - Include fields from: alert text + DOM error indicators + screenshot visual errors
   - **IMPORTANT**: Don't count the same field twice (deduplicate by field name/selector)

Example combined list: If alert mentions "Street Address" and "City", but DOM shows `input#phone` has class="error", and screenshot shows Email field has red border:
→ Complete problematic fields: ["Street Address", "City", "Phone", "Email"]

**Step 3: Analyze DOM Structure**
To understand the form:
- Locate where these problematic fields exist in the DOM
- Identify which tabs/sections/iframes contain them
- Understand the form structure

**Step 4: Generate Complete New Step List**

Generate a COMPLETE NEW step list starting from step 1 that fills the entire form correctly:

```json
{{
  "scenario": "B",
  "problematic_fields": ["Street Address", "City", "Phone", "Email"],
  "steps": [
    {{"step_number": 1, "action": "click", "selector": "...", "description": "Click Details tab"}},
    {{"step_number": 2, "action": "fill", "selector": "...", "value": "...", "description": "Fill Person Name"}},
    ...
    {{"step_number": 65, "action": "click", "selector": "...", "description": "Click Save Form"}}
  ]
}}
```

**CRITICAL for Scenario B:**
- Return scenario as "B"
- Return the complete list of ALL problematic fields in `problematic_fields` array
- Generate COMPLETE step list (steps 1 through N) that fills the entire form from scratch
- Ensure ALL problematic fields are filled with correct values from test_cases
- Navigate through tabs/iframes as needed
- Complete the form properly
- DO NOT include `accept_alert` step (alert is already handled)

**IMPORTANT: For Scenario B, you must also determine issue_type:**

**Sub-Case 1: real_issue** (System Bug)
Use this when we filled the fields correctly but the system rejected them:
- We filled the field that alert complains about
- The value we used is valid/reasonable
- This is a bug in the server/frontend validation

Response format:
```json
{{
  "scenario": "B",
  "issue_type": "real_issue",
  "explanation": "Why this is a system bug (e.g., 'Alert claims Email required but we filled it at step 15 with valid email')",
  "problematic_field_claimed": "Field name from alert",
  "our_action": "Step X: filled selector Y with value Z",
  "problematic_fields": ["Field1", "Field2"],
  "steps": []
}}
```

**Sub-Case 2: ai_issue** (AI Testing Error)
Use this when we made a mistake:
- We missed filling a required field
- We used wrong/invalid value
- The alert is correct about our mistake

Response format:
```json
{{
  "scenario": "B",
  "issue_type": "ai_issue",
  "explanation": "What we did wrong (e.g., 'We missed filling the Phone field')",
  "problematic_fields": ["Field1", "Field2"],
  "field_requirements": "Clear rewritten requirements extracted from the alert. Write EXACTLY what each field needs. Example:\n1. Tax ID - must be exactly 20 digits\n2. Rating - must select stars (required field)\n3. Email - must be valid email format",
  "steps": [
    {{"step_number": 1, "action": "...", "selector": "...", "value": "...", "description": "..."}},
    ...
  ]
}}
```

---

## Available Actions:
- `accept_alert`: Click OK button (no selector needed) - **USE ONLY IN SCENARIO A**
- `dismiss_alert`: Click Cancel button (no selector needed) - **USE ONLY IN SCENARIO A**
- `fill`: Fill input/textarea field
- `clear`: Clear input field
- `select`: Select dropdown option
- `click`: Click button/link/checkbox
- `double_click`: Double-click element
- `check`: Check checkbox (only if not checked)
- `uncheck`: Uncheck checkbox (only if checked)
- `slider`: Set range slider to percentage (value: 0-100)
- `drag_and_drop`: Drag element to target (selector: source, value: target selector)
- `press_key`: Send keyboard key (value: ENTER, TAB, ESCAPE, etc.)
- `wait_for_visible`: Wait for element to appear
- `wait_for_hidden`: Wait for element to disappear
- `switch_to_window`: Switch to window by index (value: 0, 1, 2)
- `switch_to_parent_window`: Return to original window
- `refresh`: Refresh the page
- `switch_to_frame`: Switch to iframe
- `switch_to_default`: Switch back to main content
- `create_file`: Create test file (pdf, txt, csv, xlsx, docx, json, png, jpg)
- `upload_file`: Upload file to input[type='file']

## Test Cases (for field values):
{json.dumps(test_cases, indent=2)}

**CRITICAL: Generate steps for ALL test cases above in ONE continuous JSON array. Do NOT stop after TEST_1!**

**For edit/update tests - COMPLETE WORKFLOW PER FIELD:**
For each field that needs to be verified and updated, generate this complete sequence:
1. Navigate to field (switch_to_frame/shadow_root, click tab, hover, wait_for_visible as needed)
2. Verify original value (action: "verify", value: expected original value from TEST_1)
3. Clear field (action: "clear" - only for text inputs, skip for select/checkbox/radio/slider)
4. Update field (action: "fill"/"select"/"check" with new value)
5. Navigate back (switch_to_default if you entered iframe/shadow_root)

## Response Format:

**CRITICAL: You MUST return a JSON object with two fields:**

```json
{{
  "scenario": "A",  // or "B" - which scenario you chose
  "steps": [...]     // array of step objects
}}
```

**For SCENARIO A** (simple alert - no field validation problems):
```json
{{
  "scenario": "A",
  "steps": [
    {{"step_number": {step_where_alert_appeared + 1}, "action": "accept_alert", "selector": "", "value": "", "description": "Alert accepted (already done by system)"}},
    {{"step_number": {step_where_alert_appeared + 2}, "action": "...", "selector": "...", "value": "...", "description": "Continue with next action"}},
    ...
  ]
}}
```

**For SCENARIO B** (validation error - field problems):

If real_issue (system bug):
```json
{{
  "scenario": "B",
  "issue_type": "real_issue",
  "explanation": "...",
  "problematic_field_claimed": "...",
  "our_action": "...",
  "problematic_fields": ["Field Name 1", "Field Name 2"],
  "steps": []
}}
```

If ai_issue (our mistake):
```json
{{
  "scenario": "B",
  "issue_type": "ai_issue",
  "explanation": "...",
  "problematic_fields": ["Field Name 1", "Field Name 2", "Field Name 3"],
  "field_requirements": "1. Field Name 1 - exact requirement from alert\n2. Field Name 2 - exact requirement from alert\n3. Field Name 3 - exact requirement from alert",
  "steps": [
    {{"step_number": 1, "action": "...", "selector": "...", "value": "...", "description": "..."}},
    {{"step_number": 2, "action": "...", "selector": "...", "value": "...", "description": "..."}},
    ...
    {{"step_number": N, "action": "...", "selector": "...", "value": "...", "description": "..."}}
  ]
}}
```

**IMPORTANT:** 
- For Scenario B, must include `issue_type`: "real_issue" or "ai_issue"
- `problematic_fields` must be an array of ALL field names/descriptions that have errors
- `field_requirements` must be a clear rewritten message explaining EXACTLY what each field needs (for ai_issue only)
- For ai_issue: `steps` must be complete step list from 1 to N
- For real_issue: `steps` must be empty array []

Return ONLY this JSON object, no other text.
"""
        
        return prompt
