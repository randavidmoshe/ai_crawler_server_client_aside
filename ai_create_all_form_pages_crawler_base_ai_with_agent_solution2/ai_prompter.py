# ai_prompter.py
# Handles all AI interactions with Claude API for form discovery

import json
import hashlib
from typing import Dict, List, Optional
import anthropic
from bs4 import BeautifulSoup


class AIPrompter:
    """
    Handles all AI interactions for form discovery
    - Simplifies DOMs before sending to Claude
    - Constructs prompts
    - Parses Claude responses
    - Caches results to minimize API costs
    """
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.cache = {}  # Cache DOM analyses
        self.model = "claude-sonnet-4-20250514"
        
    def analyze_page(self, dom: str, current_url: str, interaction_path: List[Dict], _list_of_visited_paths: list) -> Dict:
        """
        Main method: Analyze a page's DOM to determine if it's a form and find navigation opportunities
        
        Args:
            dom: Full HTML page source
            current_url: Current page URL
            interaction_path: List of interactions taken to reach this page
            
        Returns:
            {
                "is_form_page": bool,
                "form_name": str,
                "fields": [...],
                "navigation_items": [...],
                "tabs": [...],
                "dropdowns": [...]
            }
        """
        # Check cache first
        dom_hash = self._hash_dom(dom)
        if dom_hash in self.cache:
            print(f"[AI] Cache hit for DOM hash {dom_hash[:8]}")
            return self.cache[dom_hash]
        
        # Simplify DOM to reduce tokens
        simplified_dom = self._simplify_dom(dom)
        
        # Construct prompt
        prompt = self._construct_analysis_prompt(simplified_dom, current_url, interaction_path, _list_of_visited_paths)
        
        # Call Claude
        print(f"[AI] Calling Claude API... (DOM size: {len(simplified_dom)} chars)")
        response = self._call_claude(prompt)
        
        # Parse response
        analysis = self._parse_response(response)
        
        # Cache result
        self.cache[dom_hash] = analysis
        
        return analysis
    
    def _simplify_dom(self, full_dom: str) -> str:
        """
        Extract only relevant interactive elements from DOM
        Reduces token count for API calls
        """
        soup = BeautifulSoup(full_dom, 'html.parser')
        
        # Remove script and style tags
        for tag in soup(['script', 'style', 'noscript']):
            tag.decompose()
        
        # Keep only interactive and structural elements
        relevant_tags = [
            'form', 'input', 'select', 'textarea', 'button',
            'a', 'nav', 'ul', 'li', 'label',
            '[role="button"]', '[role="tab"]', '[role="navigation"]',
            '[onclick]', '[data-toggle]', '[data-tab]',
            'h1', 'h2', 'h3'  # Headers for context
        ]
        
        relevant_elements = []
        for tag_selector in relevant_tags:
            if tag_selector.startswith('['):
                # Attribute selector
                elements = soup.find_all(attrs={tag_selector[1:-1].split('=')[0]: True})
            else:
                elements = soup.find_all(tag_selector)
            relevant_elements.extend(elements)
        
        # Build simplified HTML
        simplified = []
        for elem in relevant_elements[:400]:  # Increased limit to capture more elements (including top nav)
            # Get tag with essential attributes
            attrs = []
            for attr in ['id', 'class', 'name', 'type', 'role', 'href', 'data-toggle', 'data-tab']:
                if elem.get(attr):
                    attrs.append(f'{attr}="{elem.get(attr)}"')
            
            tag_str = f"<{elem.name} {' '.join(attrs)}>"
            # Get all text content (including from child elements)
            text = elem.get_text(strip=True)
            if text:
                tag_str += text[:50]  # Limit text to 50 chars
            simplified.append(tag_str)
        
        # DEBUG: Save simplified DOM to file for inspection
        debug_file = '/tmp/simplified_dom_debug.html'
        with open(debug_file, 'w') as f:
            f.write('\n'.join(simplified))
        print(f"[AI] 💾 DEBUG: Saved simplified DOM to {debug_file} ({len(simplified)} elements)")
        
        return '\n'.join(simplified)
    
    def _construct_analysis_prompt(self, simplified_dom: str, current_url: str, interaction_path: List[Dict], _list_of_visited_paths: list) -> str:
        """
        Construct the prompt for Claude to analyze the page
        """
        path_description = " -> ".join([step.get('description', '') for step in interaction_path]) if interaction_path else "Starting page"
        
        prompt = f"""Analyze this web page to find form pages for test automation.

**Current URL:** {current_url}
**Navigation Path:** {path_description}

**Your Tasks:**

1. **IS_FORM_PAGE** (true/false):
   Determine if THIS page is a DATA ENTRY form for creating or editing records.
   
   ✅ TRUE - Form page for data entry if ALL of these:
   - Has multiple input fields for entering NEW data or editing existing records
   - Has a button that SAVES data (Save, Submit, Create, Update, Add, Apply)
   - Purpose is to CREATE or MODIFY database records
   
   ❌ FALSE - NOT a form page if:
   - Page is for SEARCHING/FILTERING data (has Search, Filter, Find, Reset, Generate buttons)
   - Has only search criteria fields (Employee Name, From Date, To Date, Status, etc.)
   - Is a list/table page showing existing records
   - Is view-only (no ability to modify data)
   
   CRITICAL: If the main button says "Search", "Filter", "Find", or "Reset" → return FALSE!

2. **FORM_NAME** (string or null):
   If this IS a form page, give it a descriptive name.
   Use lowercase_with_underscores format.
   Examples: "add_employee", "submit_claim", "employee_personal_details"

3. **RELATIONSHIP_FIELDS** (list):
   If this IS a form page, list fields that show relationships to other data:
   - Employee ID, Customer ID, Order ID, Reference numbers
   - Parent/Foreign key fields
   - Hidden fields with "id", "parent", "ref" in the name
   
   Format: {{"label": "...", "type": "...", "value": "...", "selector": "..."}}

4. **NAVIGATION_ITEMS** (list):
   If this is NOT a form page, list clickable items that help navigate to find form pages:
   
   **CRITICAL**: Following is a list of paths which lead to target clickables which we already have in our queue. At all levels dont list these target clickables: 
   For example if the list includes "'Click 'Admin' → Click 'Job'" then dont list 'Job' again
   {_list_of_visited_paths}
   
   INCLUDE:
   - Sidebar menu links (Admin, PIM, Leave, Time, etc.)
   - Top navigation tabs
   - Dropdown menus that reveal options (Job ▼, Configuration ▼, Reports ▼)
   - Buttons that open form pages (Add Employee, Create Claim, New Record, Edit, etc.)
   
   IGNORE:
   - Buttons/links inside table rows or data lists
   - Pagination controls (Next, Previous, Page numbers)
   - Search, Filter, Print, View buttons
   - Sort controls in table headers
   
   If already ON a form page, return empty list.
   
   IMPORTANT: NO :contains() pseudo-selector, NO contains(text() . Use proper robust CSS selectors that Selenium supports well
   Important: In case of dropdowns give a locator that will succeed to open the dropdown
   Format: {{"text": "button/link text", "type": "sidebar/tab/dropdown/button", "selector": "css selector"}}
   

**DOM to analyze:**
{simplified_dom}

**Respond with valid JSON only (no markdown):**
{{
  "is_form_page": true or false,
  "form_name": "name" or null,
  "relationship_fields": [...],
  "navigation_items": [...]
}}
"""
        return prompt
    
    def _call_claude(self, prompt: str) -> str:
        """
        Call Claude API with the prompt
        """
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=4000,
                messages=[
                    {"role": "user", "content": prompt}
                ]
            )
            return message.content[0].text
        except Exception as e:
            print(f"[AI] Error calling Claude API: {e}")
            raise
    
    def _parse_response(self, response: str) -> Dict:
        """
        Parse Claude's JSON response
        """
        try:
            # Remove markdown code blocks if present
            response = response.strip()
            if response.startswith("```json"):
                response = response[7:]
            if response.startswith("```"):
                response = response[3:]
            if response.endswith("```"):
                response = response[:-3]
            response = response.strip()
            
            # Parse JSON
            data = json.loads(response)
            
            # Validate structure
            if not isinstance(data, dict):
                raise ValueError("Response is not a dictionary")
            
            # Set defaults for missing keys
            data.setdefault('is_form_page', False)
            data.setdefault('form_name', None)
            data.setdefault('relationship_fields', [])
            data.setdefault('navigation_items', [])
            
            return data
            
        except json.JSONDecodeError as e:
            print(f"[AI] Failed to parse JSON response: {e}")
            print(f"[AI] Response was: {response[:500]}")
            # Return empty analysis
            return {
                "is_form_page": False,
                "form_name": None,
                "fields": [],
                "navigation_items": [],
                "tabs": [],
                "dropdowns": []
            }
    
    def _hash_dom(self, dom: str) -> str:
        """
        Create hash of DOM for caching
        """
        return hashlib.md5(dom.encode()).hexdigest()
