# ai_form_page_ui_visual_verify_prompter.py
# AI-Powered UI Visual Verification using Claude API

import json
import time
import logging
import anthropic
from typing import List, Optional
from anthropic._exceptions import OverloadedError, APIError

logger = logging.getLogger('init_logger.form_page_test')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')


class AIUIVisualVerifier:
    """Helper class for AI-powered UI visual verification using Claude API"""
    
    def __init__(self, api_key: str):
        if not api_key:
            raise ValueError("API key is required for AI functionality")
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
    
    def _call_api_with_retry_multimodal(self, content: list, max_tokens: int = 4000, max_retries: int = 3) -> Optional[str]:
        """
        Call Claude API with multimodal content (images) with retry logic
        
        Args:
            content: List of content blocks (text and images)
            max_tokens: Maximum tokens in response
            max_retries: Number of retry attempts
            
        Returns:
            Response text or None if failed
        """
        for attempt in range(max_retries):
            try:
                print(f"[AIUIVerifier] Calling Claude API with vision for visual verification (attempt {attempt + 1}/{max_retries})...")
                
                response = self.client.messages.create(
                    model=self.model,
                    max_tokens=max_tokens,
                    messages=[
                        {
                            "role": "user",
                            "content": content
                        }
                    ]
                )
                
                response_text = response.content[0].text
                print(f"[AIUIVerifier] ✅ API call successful ({len(response_text)} chars)")
                return response_text
                
            except OverloadedError as e:
                wait_time = (attempt + 1) * 30
                print(f"[AIUIVerifier] ⚠️  API overloaded, waiting {wait_time}s (attempt {attempt + 1}/{max_retries})")
                logger.warning(f"[AIUIVerifier] API overloaded, waiting {wait_time}s")
                time.sleep(wait_time)
                
            except APIError as e:
                print(f"[AIUIVerifier] ❌ API error: {e}")
                logger.error(f"[AIUIVerifier] API error: {e}")
                if attempt < max_retries - 1:
                    time.sleep(5)
                else:
                    return None
                    
            except Exception as e:
                print(f"[AIUIVerifier] ❌ Unexpected error: {e}")
                logger.error(f"[AIUIVerifier] Unexpected error: {e}")
                return None
        
        return None
    
    def verify_visual_ui(
            self,
            screenshot_base64: str,
            previously_reported_issues: Optional[List[str]] = None
    ) -> str:
        """
        Verify UI visual elements by analyzing a screenshot for defects.
        
        Args:
            screenshot_base64: Base64 encoded screenshot image
            previously_reported_issues: List of issues already reported (to avoid duplicates)
            
        Returns:
            String describing UI issues found, or empty string if no issues
        """
        if not screenshot_base64:
            print("[AIUIVerifier] No screenshot provided")
            return ""
        
        # Build previously reported issues section
        previously_reported_section = ""
        if previously_reported_issues and len(previously_reported_issues) > 0:
            issues_list = "\n".join([f"- {issue}" for issue in previously_reported_issues])
            previously_reported_section = f"""
=== PREVIOUSLY REPORTED UI ISSUES ===
You have already reported these UI issues in earlier steps of this test:
{issues_list}

**CRITICAL: DO NOT report these issues again!**
Only report NEW issues that are not in the list above.
If all visible issues are already in the list, return an empty string "".
===============================================================================

"""
        
        prompt = f"""You are a UI/UX quality assurance expert. Your task is to perform a thorough visual inspection of the provided screenshot to detect UI defects.

{previously_reported_section}
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

**Response Format:**
Return ONLY a JSON object with this structure:
```json
{{
  "ui_issue": ""
}}
```

Where `ui_issue` is:
- Empty string "" if no UI issues found
- Description of ALL issues found (comma-separated) if issues detected

Return ONLY the JSON object, no other text.
"""
        
        try:
            # Build multimodal content with screenshot
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
            
            response_text = self._call_api_with_retry_multimodal(message_content, max_tokens=4000, max_retries=3)
            
            if response_text is None:
                print("[AIUIVerifier] ❌ Failed to get response from API after retries")
                return ""
            
            print(f"[AIUIVerifier] Received response ({len(response_text)} chars)")
            
            # Parse JSON from response
            response_text = response_text.strip()
            if response_text.startswith("```json"):
                response_text = response_text[7:]
            if response_text.startswith("```"):
                response_text = response_text[3:]
            if response_text.endswith("```"):
                response_text = response_text[:-3]
            response_text = response_text.strip()
            
            try:
                result = json.loads(response_text)
                ui_issue = result.get("ui_issue", "")
                
                if ui_issue:
                    print(f"[AIUIVerifier] ⚠️  UI Issue detected: {ui_issue}")
                else:
                    print("[AIUIVerifier] ✅ No UI issues detected")
                
                return ui_issue
                
            except (json.JSONDecodeError, ValueError) as e:
                print(f"[AIUIVerifier] Failed to parse JSON: {e}")
                print(f"[AIUIVerifier] Response text: {response_text[:500]}")
                return ""
            
        except Exception as e:
            print(f"[AIUIVerifier] Error: {e}")
            import traceback
            traceback.print_exc()
            return ""
