# ai_helper.py
# Claude AI integration for intelligent form crawling with obstacle handling
# Version 3 - Complete

import os
import json
import re
from typing import List, Dict, Any, Optional
from anthropic import Anthropic

# Configuration
MODEL = "claude-3-5-haiku-20241022"  # Correct Claude 3.5 Haiku model
MAX_TOKENS = 8192
TEMPERATURE = 0.3

# Pricing per million tokens (Claude Haiku)
PRICE_PER_MILLION_INPUT = 1.00   # $1 per million input tokens
PRICE_PER_MILLION_OUTPUT = 5.00  # $5 per million output tokens

class AIHelper:
    """Helper class for Claude AI integration with comprehensive obstacle handling"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.environ.get("ANTHROPIC_API_KEY")
        if not self.api_key:
            raise ValueError(
                "Anthropic API key not found. Set ANTHROPIC_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = Anthropic(api_key=self.api_key)
        self.model = MODEL  # Store model for vision API calls
        
        # Cost tracking
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.api_call_count = 0
        
        print(f"[AIHelper] Initialized with model: {MODEL}")
    
    def _call_claude(self, prompt: str, system_prompt: str = "") -> str:
        """Call Claude API"""
        try:
            messages = [{"role": "user", "content": prompt}]
            
            kwargs = {
                "model": MODEL,
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
                "messages": messages
            }
            
            if system_prompt:
                kwargs["system"] = system_prompt
            
            response = self.client.messages.create(**kwargs)
            
            # Track token usage
            self.api_call_count += 1
            self.total_input_tokens += response.usage.input_tokens
            self.total_output_tokens += response.usage.output_tokens
            
            return response.content[0].text
            
        except Exception as e:
            print(f"[AIHelper] Error calling Claude API: {e}")
            raise
    
    def get_cost_summary(self) -> Dict[str, Any]:
        """Calculate total cost of API usage"""
        input_cost = (self.total_input_tokens / 1_000_000) * PRICE_PER_MILLION_INPUT
        output_cost = (self.total_output_tokens / 1_000_000) * PRICE_PER_MILLION_OUTPUT
        total_cost = input_cost + output_cost
        
        return {
            "api_calls": self.api_call_count,
            "input_tokens": self.total_input_tokens,
            "output_tokens": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "input_cost": input_cost,
            "output_cost": output_cost,
            "total_cost": total_cost
        }
    
    def print_cost_summary(self):
        """Print formatted cost summary"""
        summary = self.get_cost_summary()
        
        print("\n" + "="*60)
        print("💰 AI COST SUMMARY")
        print("="*60)
        print(f"API Calls:      {summary['api_calls']}")
        print(f"Input Tokens:   {summary['input_tokens']:,}")
        print(f"Output Tokens:  {summary['output_tokens']:,}")
        print(f"Total Tokens:   {summary['total_tokens']:,}")
        print("-"*60)
        print(f"Input Cost:     ${summary['input_cost']:.4f}")
        print(f"Output Cost:    ${summary['output_cost']:.4f}")
        print(f"TOTAL COST:     ${summary['total_cost']:.4f}")
        print("="*60 + "\n")
    
    def find_form_page_candidates(self, page_html: str, page_url: str) -> List[Dict[str, Any]]:
        """Use AI to find clickable elements that likely lead to form pages"""
        print(f"[AIHelper] Analyzing page for form candidates: {page_url}")
        
        simplified_html = self._simplify_html(page_html)
        
        system_prompt = """You are an expert at analyzing web pages to find forms.
Identify clickable elements (buttons, links, etc.) that likely lead to form pages where users can create or edit data.

Return ONLY a valid JSON array:
[
  {
    "selector": "CSS selector",
    "text": "visible text",
    "reasoning": "why this leads to a form",
    "confidence": "high/medium/low"
  }
]"""

        prompt = f"""Analyze this HTML and find elements that likely lead to form pages.

URL: {page_url}
HTML: {simplified_html[:15000]}

Return the JSON array of candidates."""

        response = self._call_claude(prompt, system_prompt)
        candidates = self._extract_json_from_response(response)
        
        print(f"[AIHelper] Found {len(candidates)} form page candidates")
        return candidates
    
    def analyze_form_fields(self, page_html: str, page_url: str) -> List[Dict[str, Any]]:
        """
        Use AI to find and analyze all form fields with comprehensive obstacle detection
        """
        print(f"[AIHelper] Analyzing form fields with obstacle detection: {page_url}")
        
        simplified_html = self._simplify_html(page_html)
        
        system_prompt = """You are an expert at analyzing complex web forms and identifying ALL obstacles.

CRITICAL: For each field, identify:
1. Basic Info: selector, type, label, name
2. **ALL Obstacles**: iframes, shadow DOM, overlays, lazy loading, disabled states, hovers, etc.
3. **Solutions**: Exact steps to overcome each obstacle

Return ONLY a valid JSON array:
[
  {
    "selector": "CSS selector",
    "field_type": "text|email|select|checkbox|radio|textarea|date|number|url|tel",
    "label": "field label or purpose",
    "name": "field name attribute",
    "required": true/false,
    "placeholder": "placeholder if any",
    "options": ["list", "of", "options"],
    "obstacles": [
      {
        "type": "iframe|shadow_root|overlay|lazy_load|disabled|hover|scroll|custom",
        "description": "what the obstacle is",
        "solution": {
          "action": "switch_iframe|pierce_shadow|dismiss_overlay|scroll|hover|wait|enable",
          "selector": "obstacle element selector",
          "details": "additional info"
        }
      }
    ],
    "in_iframe": true/false,
    "iframe_selector": "iframe CSS selector if in iframe",
    "in_shadow_root": true/false,
    "shadow_host_selector": "shadow host selector if in shadow DOM",
    "requires_hover": true/false,
    "hover_target_selector": "element to hover over",
    "requires_scroll": true/false,
    "is_lazy_loaded": true/false,
    "precondition_fields": ["fields that must be filled first"]
  }
]

Be EXTREMELY thorough. Identify EVERY obstacle."""

        prompt = f"""Analyze this form page and extract all fields with complete obstacle analysis.

URL: {page_url}
HTML: {simplified_html[:15000]}

Return the JSON array with ALL fields and obstacles."""

        response = self._call_claude(prompt, system_prompt)
        fields = self._extract_json_from_response(response)
        
        print(f"[AIHelper] Found {len(fields)} form fields")
        return fields
    
    def determine_field_assignment(self, field_info: Dict[str, Any]) -> Dict[str, Any]:
        """
        Determine update_fields_assignment based on field type and rules
        """
        field_type = field_info.get("field_type", "text").lower()
        label = (field_info.get("label") or "").lower()
        name = (field_info.get("name") or "").lower()
        options = field_info.get("options", [])
        
        # Rule 1: Description/Summary/Comments → random text
        if any(kw in label or kw in name for kw in ["description", "summary", "comment", "note", "detail", "remark", "explanation"]):
            return {"type": "assign_random_text", "size": "100"}
        
        # Rule 2: Name fields → random name
        if any(kw in label or kw in name for kw in ["first_name", "last_name", "fname", "lname", "full_name", "name"]):
            return {"type": "assign_random_name"}
        
        # Rule 3: Email → random email
        if "email" in field_type or "email" in label or "email" in name:
            return {"type": "assign_random_email"}
        
        # Rule 4: Phone → fixed Israeli phone
        if any(kw in label or kw in name for kw in ["phone", "mobile", "tel"]):
            if "+972" in label or "international" in label:
                return {"type": "assign_value", "value": "972526966920"}
            return {"type": "assign_value", "value": "0526966920"}
        
        # Rule 5: Date → fixed date
        if field_type == "date" or "date" in label or "birth" in label:
            return {"type": "assign_value", "value": "2025-01-15"}
        
        # Rule 6: URL → random URL
        if field_type == "url" or any(kw in label or kw in name for kw in ["url", "website", "link"]):
            return {"type": "assign_random_url"}
        
        # Rule 7: Dropdown/Select → random from list
        if field_type == "select" and options:
            return {
                "type": "assign_random_item_from_a_list",
                "value": options
            }
        
        # Rule 8: Checkbox → random true/false
        if field_type == "checkbox":
            return {"type": "assign_for_checkbox_random_choice_between_true_false"}
        
        # Rule 9: Radio → random from options
        if field_type == "radio" and options:
            return {
                "type": "assign_random_item_from_a_list",
                "value": options
            }
        
        # Rule 10: Float/Decimal (price, amount, cost, rate)
        if any(kw in label or kw in name for kw in ["price", "amount", "cost", "rate", "decimal", "float"]):
            return {
                "type": "assign_random_float_in_specific_range",
                "from": "10",
                "to": "100",
                "precision": "3"
            }
        
        # Rule 11: Integer (quantity, count, age, number)
        if field_type == "number" or any(kw in label or kw in name for kw in ["quantity", "count", "age", "number"]):
            return {
                "type": "assign_random_int_in_specific_range",
                "from": "1",
                "to": "100",
                "precision": ""
            }
        
        # Rule 12: General text fields
        if field_type in ["text", "textarea"]:
            if any(kw in label or kw in name for kw in ["occupation", "address", "city", "state", "country"]):
                return {"type": "assign_random_text", "size": "50"}
            return {"type": "assign_random_text", "size": "50"}
        
        # Default: random text
        return {"type": "assign_random_text", "size": "50"}
    
    def _simplify_html(self, html: str) -> str:
        """Simplify HTML while preserving structure for better AI analysis"""
        # Remove scripts and styles
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        
        # Remove inline styles but keep structure
        html = re.sub(r' style="[^"]*"', '', html)
        
        # Normalize whitespace but preserve line breaks for readability
        html = re.sub(r'[ \t]+', ' ', html)  # Multiple spaces/tabs to single space
        html = re.sub(r'\n\s*\n', '\n', html)  # Multiple newlines to single
        
        return html.strip()
    
    def _extract_json_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Extract JSON array from AI response"""
        # Try to find JSON in code block first
        json_match = re.search(r'```(?:json)?\s*(\[.*\])\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            # Find the outermost [...] array (greedy match)
            json_match = re.search(r'\[[\s\S]*\]', response)
            if json_match:
                json_str = json_match.group(0)
            else:
                print(f"[AIHelper] Warning: Could not find JSON in response")
                return []
        
        try:
            return json.loads(json_str)
        except json.JSONDecodeError as e:
            print(f"[AIHelper] Error parsing JSON: {e}")
            print(f"[AIHelper] Response was: {response[:500]}")
            return []
    
    def suggest_field_value(self, field_info: Dict[str, Any]) -> str:
        """Suggest test value for a field (simple heuristic fallback)"""
        field_type = field_info.get("field_type", "text")
        label = field_info.get("label", "")
        name = field_info.get("name", "")
        
        if "email" in field_type.lower() or "email" in label.lower() or "email" in name.lower():
            return "test.user@example.com"
        elif "phone" in label.lower() or "phone" in name.lower():
            return "5551234567"
        elif "password" in field_type.lower():
            return "TestPass123!"
        elif field_type == "number":
            return "42"
        elif field_type == "date":
            return "2025-01-01"
        elif "name" in label.lower() or "name" in name.lower():
            if "first" in label.lower() or "first" in name.lower():
                return "John"
            elif "last" in label.lower() or "last" in name.lower():
                return "Doe"
            else:
                return "John Doe"
        else:
            return "Test Value"
    
    def extract_parent_reference_fields(self, form_name: str, page_html: str, screenshot_base64: str = None) -> List[Dict[str, Any]]:
        """
        Extract parent reference fields from form page.
        These are dropdowns or autocomplete fields where user selects values from OTHER form pages.
        
        Args:
            form_name: Name of the form (to help locate it in HTML)
            page_html: Full page HTML
            screenshot_base64: Base64-encoded screenshot of the form for vision analysis
            
        Returns:
            List of parent reference fields with name, type, and label
        """
        print(f"[AIHelper] Extracting parent reference fields for form: {form_name}")
        
        simplified_html = self._simplify_html(page_html)
        
        # DEBUG: Save HTML to file for inspection
        debug_html_path = f"/tmp/ai_debug_{form_name}_html.txt"
        try:
            with open(debug_html_path, "w", encoding="utf-8") as f:
                f.write(simplified_html[:30000])
            print(f"[AIHelper] 🔍 DEBUG: Saved HTML to {debug_html_path}")
        except Exception as e:
            print(f"[AIHelper] ⚠️  Could not save debug HTML: {e}")
        
        system_prompt = """You are an expert at analyzing web forms to identify parent reference fields.

Parent reference fields are fields that reference OTHER form pages/entities (like Employees, Events, Currencies, Departments, Projects, etc.).

CRITICAL: Look for BOTH traditional HTML elements AND modern framework components:

1. DROPDOWN/SELECT fields:
   - Traditional: <select name="employee_id">...</select>
   - Vue.js/React: <div class="oxd-select-wrapper">...<div class="oxd-select-text-input">-- Select --</div>...
   - Angular: <mat-select>...</mat-select>
   - ANY element with classes like: select-wrapper, dropdown, select-text, select-input

2. AUTOCOMPLETE/HINT fields:
   - Traditional: <input type="text" placeholder="Type for hints..." list="employees">
   - Vue.js/React: <div class="oxd-autocomplete-wrapper">...<input placeholder="Type for hints...">...
   - Angular: <input matAutocomplete>
   - ANY element with classes like: autocomplete-wrapper, autocomplete-text-input, combobox, type-ahead
   - Inputs with placeholders containing: "Type for hints", "Search", "Start typing", etc.

3. Field LABELS that suggest entity selection (look for labels NEAR the fields):
   - "Employee Name", "Employee", "Staff Member"
   - "Event", "Event Type", "Event Name"
   - "Currency", "Currency Type"
   - "Project", "Department", "Location", "Supervisor", "Manager", "Customer", "Vendor"
   - ANY label that suggests selecting from a list of entities

IMPORTANT: The field structure might be deeply nested in divs with Vue.js classes (data-v-*). The label and input may be in separate divs. Look for the PATTERN:
- A label element with entity-like text
- Followed by a select-wrapper OR autocomplete-wrapper div
- This indicates a parent reference field

Return ONLY a valid JSON array:
[
  {
    "field_name": "best guess at logical field name (from label or nearby text)",
    "field_type": "dropdown|autocomplete",
    "field_label": "exact text from the visible label"
  }
]

If no parent reference fields found, return empty array: []"""

        prompt = f"""Analyze this form page and extract ALL parent reference fields (dropdowns and autocomplete fields).

Form Name: {form_name}

HTML (first 30000 chars):
{simplified_html[:30000]}

INSTRUCTIONS:
1. Look for LABELS with entity-like text: "Employee Name", "Event", "Currency", "Project", "Department", etc.
2. Near each label, look for EITHER:
   - A <div class="oxd-select-wrapper"> (this is a DROPDOWN)
   - A <div class="oxd-autocomplete-wrapper"> (this is an AUTOCOMPLETE field)
   - Traditional <select> elements
   - Traditional <input> with autocomplete attributes

3. For EACH field you find, extract:
   - field_name: derive from the label text (e.g., "Employee Name" → "employee_name", "Event" → "event")
   - field_type: "dropdown" or "autocomplete"
   - field_label: exact label text (e.g., "Employee Name", "Event", "Currency")

EXAMPLE from OrangeHRM form:
```html
<label class="oxd-label">Employee Name</label>
<div class="oxd-autocomplete-wrapper">
  <input placeholder="Type for hints...">
</div>
```
Should return: {{"field_name": "employee_name", "field_type": "autocomplete", "field_label": "Employee Name"}}

```html
<label class="oxd-label">Event</label>
<div class="oxd-select-wrapper">
  <div class="oxd-select-text-input">-- Select --</div>
</div>
```
Should return: {{"field_name": "event", "field_type": "dropdown", "field_label": "Event"}}

Return the complete JSON array of ALL parent reference fields you find."""

        # Build content array for API call
        content = []
        
        # Add screenshot first if available (AI sees image first)
        if screenshot_base64:
            print(f"[AIHelper] 📸 Including screenshot in vision analysis")
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_base64
                }
            })
            # Add instruction to look at the screenshot
            content.append({
                "type": "text",
                "text": f"""FIRST: Look at the screenshot of the form page above.

{prompt}

IMPORTANT: Use the screenshot to visually identify the form fields. The HTML is provided for reference, but the screenshot shows the ACTUAL rendered form."""
            })
        else:
            # No screenshot, use text only
            content.append({
                "type": "text",
                "text": prompt
            })
        
        # Make API call with vision
        try:
            messages = [{"role": "user", "content": content}]
            
            kwargs = {
                "model": self.model,
                "max_tokens": MAX_TOKENS,
                "temperature": TEMPERATURE,
                "messages": messages,
                "system": system_prompt
            }
            
            api_response = self.client.messages.create(**kwargs)
            
            # Track token usage
            self.api_call_count += 1
            self.total_input_tokens += api_response.usage.input_tokens
            self.total_output_tokens += api_response.usage.output_tokens
            
            response = api_response.content[0].text
            
        except Exception as e:
            print(f"[AIHelper] Error calling Claude API with vision: {e}")
            response = "[]"
        
        # DEBUG: Print AI response to console
        print(f"[AIHelper] 🔍 AI Response (first 500 chars): {response[:500]}")
        
        # DEBUG: Save AI response
        debug_response_path = f"/tmp/ai_debug_{form_name}_response.txt"
        try:
            with open(debug_response_path, "w", encoding="utf-8") as f:
                f.write(response)
            print(f"[AIHelper] 🔍 DEBUG: Saved AI response to {debug_response_path}")
        except Exception as e:
            print(f"[AIHelper] ⚠️  Could not save debug response: {e}")
        
        fields = self._extract_json_from_response(response)
        
        # DEBUG: Print parsed fields
        print(f"[AIHelper] 🔍 Parsed fields: {fields}")
        
        print(f"[AIHelper] Found {len(fields)} parent reference fields")
        return fields

    def generate_login_steps(self, page_html: str, screenshot_base64: str = None) -> List[Dict[str, Any]]:
        """
        Use AI Vision to analyze login page and generate login steps.
        
        Args:
            page_html: HTML of the login page
            screenshot_base64: Base64-encoded screenshot of the login page
            
        Returns:
            List of login steps with action, selector, value
        """
        print(f"[AIHelper] 🔐 Generating login steps using AI Vision...")
        
        system_prompt = """You are an expert at analyzing login pages and generating automation steps.
Your task is to identify the login form fields and generate steps to fill and submit the form."""

        user_prompt = """Analyze this login page screenshot and HTML to generate login automation steps.

Look for:
1. Username/email input field
2. Password input field  
3. Submit/Login button

For each element, provide:
- action: "fill" for input fields, "click" for buttons
- selector: CSS selector to find the element (prefer id, then name, then type attributes)
- value: Use "{{username}}" for username field, "{{password}}" for password field, empty string "" for buttons

Return ONLY a JSON array of steps in order, like:
[
  {"action": "fill", "selector": "input[name='username']", "value": "{{username}}"},
  {"action": "fill", "selector": "input[type='password']", "value": "{{password}}"},
  {"action": "click", "selector": "button[type='submit']", "value": ""}
]

IMPORTANT:
- Return ONLY the JSON array, no other text
- Use the most reliable CSS selectors you can find from the HTML
- Steps must be in correct order: username, password, then submit
- Every step MUST have action, selector, and value fields
"""

        # Build message content with image if available
        content = []
        
        if screenshot_base64:
            content.append({
                "type": "image",
                "source": {
                    "type": "base64",
                    "media_type": "image/png",
                    "data": screenshot_base64
                }
            })
        
        # Add HTML context (truncated if too long)
        html_truncated = page_html[:15000] if len(page_html) > 15000 else page_html
        content.append({
            "type": "text",
            "text": f"{user_prompt}\n\nHTML:\n{html_truncated}"
        })
        
        messages = [{"role": "user", "content": content}]
        
        try:
            kwargs = {
                "model": self.model,
                "max_tokens": 1000,
                "temperature": 0,
                "messages": messages,
                "system": system_prompt
            }
            
            api_response = self.client.messages.create(**kwargs)
            
            # Track token usage
            self.api_call_count += 1
            self.total_input_tokens += api_response.usage.input_tokens
            self.total_output_tokens += api_response.usage.output_tokens
            
            response = api_response.content[0].text
            
        except Exception as e:
            print(f"[AIHelper] Error calling Claude API for login steps: {e}")
            return []
        
        print(f"[AIHelper] 🔐 AI Response: {response[:500]}")
        
        steps = self._extract_json_from_response(response)
        
        print(f"[AIHelper] 🔐 Generated {len(steps)} login steps")
        return steps
