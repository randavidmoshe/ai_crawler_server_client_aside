# ai_form_page_runner_error_prompter.py
# AI-powered error analysis for form page execution failures

import json
import anthropic
import re
from typing import Dict, List, Optional


class AIFormPageRunError:
    """Analyze and handle errors during form page stage execution"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
    
    def analyze_error(
        self,
        failed_stage: Dict,
        dom_html: str,
        screenshot_base64: str,
        all_stages: List[Dict],
        error_message: str
    ) -> Dict:
        """
        Analyze error and determine recovery action
        
        Args:
            failed_stage: The stage that failed
            dom_html: Current DOM at failure point
            screenshot_base64: Screenshot at failure point
            all_stages: All stages from JSON (for context)
            error_message: The exception/error message
            
        Returns:
            Dict with decision and recovery steps
        """
        prompt = self._build_error_analysis_prompt(
            failed_stage, dom_html, all_stages, error_message
        )
        
        # Build message with screenshot
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
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=16000,
                messages=[{"role": "user", "content": message_content}]
            )
            
            response_text = message.content[0].text
            
            # Parse JSON response
            json_match = re.search(r'\{[\s\S]*\}', response_text)
            if json_match:
                result = json.loads(json_match.group())
                return result
            else:
                return {"decision": "general_error", "description": "Failed to parse AI response"}
                
        except Exception as e:
            return {"decision": "general_error", "description": f"AI call failed: {str(e)}"}
    
    def _build_error_analysis_prompt(
        self,
        failed_stage: Dict,
        dom_html: str,
        all_stages: List[Dict],
        error_message: str
    ) -> str:
        """Build prompt for error analysis"""
        
        prompt = f"""# FORM PAGE EXECUTION ERROR ANALYSIS

## Context
You are analyzing an error that occurred during automated execution of form page test stages. The stages were created by AI to test a web form, and now during execution, one stage has failed.

## Failed Stage
```json
{json.dumps(failed_stage, indent=2)}
```

## Error Message
```
{error_message}
```

## Current DOM (at failure point)
```html
{dom_html[:50000]}
```

## All Stages Context (first 20 for reference)
```json
{json.dumps(all_stages[:20], indent=2)}
```

## Your Task
Analyze the failure and determine ONE of the following decisions:

---

### **Decision 1: locator_changed**
The selector/locator in the stage is outdated. The element exists but with a different selector.

**When to use:**
- Element is visible in DOM and screenshot
- Selector doesn't match anymore (ID changed, class changed, attribute changed)
- Element is at expected location but selector is wrong

**Response format:**
```json
{{
  "decision": "locator_changed",
  "description": "Brief explanation of what changed in locator",
  "corrected_step": {{
    "step_number": {failed_stage.get('step_number')},
    "test_case": "{failed_stage.get('test_case', '')}",
    "action": "{failed_stage.get('action')}",
    "selector": "NEW_CORRECT_SELECTOR_HERE",
    "value": "{failed_stage.get('value', '')}",
    "description": "{failed_stage.get('description', '')}"
  }}
}}
```

---

### **Decision 2: general_error**
Page-level issue: 404, blank page, network error, loading issue.

**When to use:**
- Page is blank or showing error
- Page failed to load
- Network/connection issue
- 404 or 500 error page

**Response format:**
```json
{{
  "decision": "general_error",
  "description": "What page-level error occurred"
}}
```

---

### **Decision 3: need_healing**
Major UI changes detected - field no longer exists, moved, or new fields added.

**When to use:**
- Field completely removed from UI
- Field moved to different tab/section
- New required fields appeared that aren't in stages
- Major structural changes in form

**Check by:**
- Compare DOM against all_stages
- Look for fields in stages that don't exist in DOM
- Look for new fields in DOM not in stages

**Response format:**
```json
{{
  "decision": "need_healing",
  "description": "Detailed description of major UI changes (which fields added/removed/moved)"
}}
```

---

### **Decision 4: correction_steps**
Locator is fine, page is fine, but step needs correction or preparation steps.

**When to use:**
- Selector is correct but step needs modification
- Need to execute preparation steps before this step
- Timing or interaction issue

**Two sub-options:**

**Option A: Just fix present step**
```json
{{
  "decision": "correction_steps",
  "type": "present_only",
  "description": "What was corrected",
  "corrected_step": {{
    "step_number": {failed_stage.get('step_number')},
    "test_case": "{failed_stage.get('test_case', '')}",
    "action": "CORRECTED_ACTION",
    "selector": "SELECTOR",
    "value": "CORRECTED_VALUE",
    "description": "CORRECTED_DESCRIPTION"
  }}
}}
```

**Option B: Pre-steps + present step**

**When to use pre-steps:**
- If the form page appears entirely empty or you can't find the element
- Page state was lost (fields that should be filled are now empty)
- You can use the `all_stages` list provided to understand what steps were taken before
- Check which fields are still filled (visible in DOM/screenshot) and provide pre-steps starting from an appropriate earlier step
- Only include pre-steps for fields that are now empty/missing up to the point of the failed step to rebuild the page state

**Example Scenario:**
```
Original steps from all_stages:
1. fill "First Name" with "John"
2. fill "Last Name" with "Doe"  
3. fill "Email" with "john@example.com"
4. click "Next" button
5. fill "Phone" with "123-456-7890"
6. fill "Address" with "123 Main St" ← FAILED

Current DOM shows:
- "First Name" field has value "John" ✅
- "Last Name" field has value "Doe" ✅
- "Email" field is empty ❌
- "Next" button exists ✅
- "Phone" field doesn't exist ❌
- "Address" field doesn't exist ❌

Correct response: Start from Email (step 3) onwards since First Name and Last Name are still filled
```

**Response format:**
```json
{{
  "decision": "correction_steps",
  "type": "with_presteps",
  "description": "What pre-steps are needed and why",
  "presteps": [
    {{"step_number": {failed_stage.get('step_number')}-0.1, "test_case": "", "action": "...", "selector": "...", "value": "...", "description": "..."}},
    {{"step_number": {failed_stage.get('step_number')}-0.2, "test_case": "", "action": "...", "selector": "...", "value": "...", "description": "..."}}
  ],
  "corrected_step": {{
    "step_number": {failed_stage.get('step_number')},
    "test_case": "{failed_stage.get('test_case', '')}",
    "action": "...",
    "selector": "...",
    "value": "...",
    "description": "..."
  }}
}}
```

---

## Decision Process
1. Look at screenshot and DOM - is the element visible?
2. Check if selector matches any element in DOM
3. Check if page loaded correctly (no 404, blank, errors)
4. Compare DOM structure against all_stages - any major changes?
5. Decide which of the 4 decisions fits best

**IMPORTANT:** Return ONLY the JSON object for your chosen decision. No other text.
"""
        
        return prompt
