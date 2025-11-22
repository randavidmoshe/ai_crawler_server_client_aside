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
        """Simplify HTML by removing scripts, styles"""
        html = re.sub(r'<script[^>]*>.*?</script>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<style[^>]*>.*?</style>', '', html, flags=re.DOTALL | re.IGNORECASE)
        html = re.sub(r'<!--.*?-->', '', html, flags=re.DOTALL)
        html = re.sub(r' style="[^"]*"', '', html)
        html = re.sub(r'\s+', ' ', html)
        return html.strip()
    
    def _extract_json_from_response(self, response: str) -> List[Dict[str, Any]]:
        """Extract JSON array from AI response"""
        json_match = re.search(r'```(?:json)?\s*(\[.*?\])\s*```', response, re.DOTALL)
        if json_match:
            json_str = json_match.group(1)
        else:
            json_match = re.search(r'\[.*?\]', response, re.DOTALL)
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
