"""
AI Prompter
Builds prompts for AI and parses AI responses
"""

import json
from typing import Dict, List


class AIPrompter:
    """Handles prompt construction and response parsing for form mapping AI"""
    
    def __init__(self):
        self.template = self._load_template()
    
    def _load_template(self) -> str:
        """Load the prompt template with instructions"""
        return """
You are an expert at analyzing HTML forms and creating structured JSON mappings for automated form filling with Selenium.

TASK: Analyze the provided DOM and create/update a JSON mapping that describes how to fill the form programmatically.

=== CONTEXT ===
Form Name: {form_name}
Iteration: {iteration}
{last_interaction_info}
{clicked_elements_info}
{previous_dom_info}

=== CURRENT JSON ===
{current_json}

=== CURRENT DOM ===
{current_dom}

=== PREVIOUS DOM (for comparison) ===
{previous_dom}

{iframe_contents_info}

=== YOUR OBJECTIVES ===

=== 🎯 TASK 1: IDENTIFY ACCESSIBLE FIELDS (DO THIS FIRST!) ===

**CRITICAL: Before mapping fields, you must determine which fields are ACCESSIBLE in the CURRENT STATE.**

**Simple Definition:**
A field is ACCESSIBLE if the user can reach it and fill it out by NAVIGATION ONLY (scrolling, clicking tabs, clicking expand buttons).

**Key Question:** 
Looking at the CURRENT DOM, can the user get to this field WITHOUT changing any dropdown, radio button, or checkbox values?

**If YES (just navigation) → ACCESSIBLE ✅**
**If NO (need to change form data) → NOT ACCESSIBLE ❌**

**INCLUDE as Accessible:**
✅ Fields visible on the current page (inputs, selects, textareas)
✅ Interactive UI elements (buttons, tabs, hover triggers, clickable elements)
✅ Fields in other tabs (user just clicks the tab - NO form data change)
✅ Fields in collapsed sections (user just clicks expand)
✅ Fields in iframes (user just navigates into iframe)
✅ Fields that need scrolling to see

**🚨 CRITICAL: Include ALL Types of Interactive Elements! 🚨**
When identifying accessible_fields, include EVERY type of element you would normally map to gui_fields:
- Input fields (text, email, tel, etc.)
- Dropdowns (select elements)
- Textareas
- Checkboxes and radio buttons
- **Buttons** (submit buttons, action buttons)
- **Tab buttons** (elements that switch between tabs)
- **Hover triggers** (elements that need hovering)
- **Clickable actions** (expand/collapse buttons, etc.)

Don't limit accessible_fields to just form inputs - include ALL interactive elements you see!

**EXCLUDE as NOT Accessible:**
❌ Fields whose parent div has class="hidden" (these require changing a dropdown/radio/checkbox to appear)
❌ Fields that only show up when you SELECT a specific dropdown option
❌ Fields that only show up when you CLICK a specific radio button  
❌ Fields that only show up when you CHECK a checkbox
❌ Disabled or readonly fields

**SPECIAL - iframes and Shadow DOM:**
🔲 If you see an accessible iframe, include the IFRAME ID itself in accessible_fields
   - Example: `<iframe id="addressIframe">` → include "addressIframe"

**🚨 CRITICAL: Use CONSISTENT NAMING! 🚨**

**For accessible_fields:**
- If the element already exists in gui_fields → use the SAME name as in gui_fields
- If not in gui_fields yet → give it a logical name (what you normally would use)

**For gui_fields (when ADDING a new gui_field):**
- If the element exists in accessible_fields → use the SAME name as in accessible_fields
- If not in accessible_fields → give it a logical name (what you normally would use)

This ensures names match between accessible_fields and gui_fields for proper condition building.

Example:
```
accessible_fields: ["click_address_tab", "fullName"]
gui_fields: [
  {{"name": "fullName", ...}},           ← Same name as in accessible_fields!
  {{"name": "click_address_tab", ...}}   ← Same name as in accessible_fields!
]
```

**Examples:**

Example 1 - Tab Field (YES, include):
The user can click the Address tab button to access this field WITHOUT changing any form data.
```
<div class="tab-content" id="address-tab">
  <input id="street">  ← INCLUDE "street"
</div>
```

Example 2 - Conditional Field (NO, exclude):
The field's parent has class="hidden" because applicationType is "personal". To access this field, user must CHANGE the dropdown to "business".
```
<div class="form-group hidden">
  <input id="companyName">  ← DO NOT include "companyName"
</div>
```

Example 3 - Currently Visible Field (YES, include):
The field is visible right now, no action needed.
```
<input id="fullName">  ← INCLUDE "fullName"
```

Example 4 - Tab Button (YES, include):
```
<button class="tab-button">Address</button>  ← INCLUDE as "click_address_tab"
```

Example 5 - Hover Trigger (YES, include):
```
<div id="specialOptions" onmouseover="showOptions()">  ← INCLUDE as "hover_for_special_options"
```

**Return Format:**
In your JSON response, include:

"accessible_fields": ["fullName", "email", "click_address_tab", "hover_for_special_options", "street", "city", "addressIframe"]
"gui_fields": [...your regular mapping with SAME names as accessible_fields...]

(Note: All fields should be in the same JSON response)

===  🚨 CRITICAL: ORCHESTRATOR-DRIVEN SYSTEM 🚨 ===

**IMPORTANT:** The orchestrator now handles BOTH exploration AND condition building!

**Your Role:**
1. ✅ Map ALL fields from accessible_fields to gui_fields
2. ✅ Choose correct locators (CSS selectors)
3. ✅ Set create_type (enter_text, select_dropdown, click_checkbox, etc.)
4. ✅ Set verification methods
5. ✅ Return complete gui_fields

**🚨 CRITICAL MAPPING RULE: 🚨**
**EVERY field in your accessible_fields list MUST appear in gui_fields!**

Even if a field has a parent with class="hidden", you must still map it to gui_fields.
The orchestrator will handle conditional visibility automatically.

**The Orchestrator Does:**
- ✅ Discovers all interactive elements
- ✅ Explores all dropdown/tab/radio combinations systematically  
- ✅ Tracks which fields are visible in each state
- ✅ **Automatically builds non_editable_condition at the end** ← NEW!

**🚨 CRITICAL: DO NOT SET non_editable_condition! 🚨**

The orchestrator automatically builds conditions based on visibility tracking.

**ALWAYS set:**
"non_editable_condition": {{}}

**NEVER try to determine conditions yourself!** The orchestrator has complete visibility data and will set accurate conditions automatically after all exploration is complete.

{exploration_info}

{changes_info}

=== RECURSIVE EXPLORATION STRATEGY ===

**CRITICAL MISSION:** Systematically explore ALL interactive elements to discover conditional fields.

**Interactive Elements to Explore:**
1. Dropdowns (<select>) → Try EVERY option value
2. Tabs (buttons with data-tab, role="tab") → Click EVERY tab
3. Expandable sections (buttons that reveal content) → Click them
4. Checkboxes → Try both checked and unchecked
5. Radio button groups → Try each option

**Exploration Depth:** You can explore up to {max_exploration_depth} levels deep.
**Current Depth:** {current_exploration_depth}/{max_exploration_depth}
**States Explored:** {explored_states_count}

**Exploration Process:**

STEP 1 - Initial Discovery (Iteration 1):
- Map all currently visible fields
- Identify ALL interactive elements (dropdowns, tabs, buttons, checkboxes)
- Start systematic exploration

STEP 2 - Systematic Exploration:
For EACH interactive element you discover:
  a) Try EACH possible value/state
  b) Record what new fields/elements appear
  c) If NEW interactive elements appear → explore those too (recursive)
  d) Continue until depth limit reached

STEP 3 - Navigation Format:
When you want to explore, ALWAYS provide navigation from base URL:

{{
  "exploration_step": {{
    "reset_to_base_url": true,
    "navigation_sequence": [
      {{
        "action": "select_dropdown",
        "locator": "//select[@id='type']",
        "locator_type": "xpath",
        "value": "business",
        "wait_after": 2
      }},
      {{
        "action": "click_tab",
        "locator": "//button[@data-tab='details']",
        "locator_type": "xpath",
        "wait_after": 1
      }}
    ]
  }},
  "gui_fields": [...],
  "mapping_complete": false
}}

**Action Types:**
- "select_dropdown" - Select value from dropdown
- "click_tab" - Click a tab
- "click_button" - Click a button
- "click" - Generic click

STEP 4 - Condition Detection:
When a field appears after navigation sequence:
- Field's non_editable_condition = inverse of the navigation that revealed it

Example:
Navigation: select type="business" → field "company_name" appears
Condition for company_name:
{{
  "non_editable_condition": {{
    "applicationType": {{
      "operator": "or",
      "type": ["personal", "enterprise"]
    }}
  }}
}}

**Exploration Strategy Examples:**

Example 1 - Simple Dropdown:
Iteration 1: See dropdown "type" with options [personal, business, enterprise]
→ Request: Select "business" via navigation_sequence

Iteration 2: Field "company_name" appears! 
→ Map it with condition: type != "business"
→ Request: Select "enterprise" to check if same fields appear

Iteration 3: Same fields confirmed
→ Request: Select "personal" to explore other branch

Example 2 - Nested: Dropdown → Dropdown:
Iteration 1: See dropdown1 with options [A, B, C]
→ Request: Select "A"

Iteration 2: New dropdown2 appears with options [X, Y]
→ Request navigation_sequence: [select dropdown1="A", select dropdown2="X"]

Iteration 3: Field "field_nested" appears
→ Map with condition: dropdown1 != "A" OR dropdown2 != "X"
→ Request: [select dropdown1="A", select dropdown2="Y"]

Example 3 - Mixed: Dropdown → Tab → Dropdown:
Iteration 1: Select dropdown "type"="business"
Iteration 2: Tab "Details" appears, click it
Iteration 3: Inside tab, dropdown "size" appears with options [small, large]
Iteration 4: Request navigation_sequence: [
  select type="business",
  click tab "Details",
  select size="large"
]

**Backtracking:**
After exploring one branch fully, go back and try other options:
- Explored: type="business" → all its sub-options
- Next: type="personal" → explore its sub-options
- Continue until ALL combinations explored (within depth limit)

**When to Stop Exploration:**
- Reached depth limit ({max_exploration_depth})
- No new fields discovered in last 3 exploration attempts
- All discovered interactive elements have been explored
- Set mapping_complete=true

**IMPORTANT:**
- ALWAYS use navigation_sequence when exploring
- ALWAYS start from base URL (reset_to_base_url: true)
- Track what you've explored to avoid infinite loops
- Prioritize unexplored paths over re-exploring

**CRITICAL: Understanding Your Output**
The JSON you create is a SELENIUM TEST SCRIPT. 
Each gui_field is ONE STEP that Selenium will execute IN ORDER, ONE BY ONE.

Think of it like writing instructions for a robot:
- Step 1: Fill field "name"
- Step 2: Fill field "email"  
- Step 3: Click "Details" tab
- Step 4: Fill field "phone"
- Step 5: Click "Next" button

Your gui_fields array = Sequential execution steps for Selenium.
The ORDER MATTERS! Selenium cannot skip around.

**🚨 CRITICAL: MULTI-STEP ACTIONS FOR COMPLEX FIELDS! 🚨**

**For simple interactions:** Use standard Selenium commands
**For complex interactions:** Break into multi-step sequence:
1. **Fetch data** from page (using Selenium get_* actions)
2. **Process data** (using custom Python code on isolated server)
3. **Execute action** (using Selenium with processed data)

**Available Selenium Commands:**
- `click`: Click an element
- `enter_text`: Type text into input
- `select_dropdown`: Select dropdown option
- `click_checkbox`: Check/uncheck checkbox
- `switch_to_frame`: Enter iframe
- `switch_to_parent_frame`: Exit iframe
- `wait_for_element`: Wait for element (timeout in seconds)
- `get_text`: Get element's text → stores in variable
- `get_attribute`: Get element's attribute → stores in variable
- `hover`: Hover over element

**Custom Python (for isolated server - NO driver access):**
- Input: Variables from get_* actions + field_value
- Output: Processed value to use in next Selenium action
- Can use: datetime, time, re, json, math libraries
- Cannot use: driver, selenium commands, os, sys, file operations

**Use `{{field_name}}` or `{{variable_name}}` to reference values!**

**Examples:**

**Simple Field:**
```json
{{
  "name": "email",
  "create_action": {{
    "create_type": "enter_text",
    "update_css": "#email",
    "steps": [
      {{"action": "enter_text", "locator": "#email", "value": "{{email}}"}}
    ]
  }}
}}
```

**Iframe Field (Multi-step):**
```json
{{
  "name": "street",
  "iframe_context": "addressIframe",
  "create_action": {{
    "create_type": "enter_text",
    "update_css": "#street",
    "steps": [
      {{"action": "switch_to_frame", "locator": "#addressIframe"}},
      {{"action": "enter_text", "locator": "#street", "value": "{{street}}"}},
      {{"action": "switch_to_parent_frame"}}
    ]
  }}
}}
```

**Datepicker (Selenium + Python processing):**
```json
{{
  "name": "birth_date",
  "create_action": {{
    "create_type": "enter_text",
    "update_css": "#birth_date",
    "steps": [
      {{"action": "get_attribute", "locator": "#birth_date", "attribute": "data-format", "store_as": "date_format"}},
      {{"action": "custom_python", "code": "from datetime import datetime; formatted = datetime.strptime(field_value, '%Y-%m-%d').strftime(date_format or '%m/%d/%Y')", "inputs": ["field_value", "date_format"], "output": "formatted_date"}},
      {{"action": "click", "locator": "#birth_date"}},
      {{"action": "enter_text", "locator": "#birth_date", "value": "{{formatted_date}}"}}
    ]
  }}
}}
```

**Toggle Switch (Selenium + Python logic):**
```json
{{
  "name": "notifications_enabled",
  "create_action": {{
    "create_type": "click_button",
    "update_css": ".switch-toggle",
    "steps": [
      {{"action": "get_attribute", "locator": ".switch-toggle", "attribute": "data-state", "store_as": "current_state"}},
      {{"action": "custom_python", "code": "should_click = 'yes' if current_state != field_value else 'no'", "inputs": ["current_state", "field_value"], "output": "should_click"}},
      {{"action": "click", "locator": ".switch-toggle", "condition": "{{should_click}} == 'yes'"}}
    ]
  }}
}}
```

**Dynamic Wait:**
```json
{{
  "name": "async_field",
  "create_action": {{
    "create_type": "enter_text",
    "update_css": "#async_field",
    "steps": [
      {{"action": "click", "locator": ".load-more"}},
      {{"action": "wait_for_element", "locator": "#async_field", "timeout": 10}},
      {{"action": "enter_text", "locator": "#async_field", "value": "{{async_field}}"}}
    ]
  }}
}}
```

**CRITICAL RULES:**
1. **Simple scenarios:** Use basic Selenium actions (click, enter_text, wait, switch frames)
2. **Complex scenarios:** Use multi-step pattern:
   - Step 1: get_attribute or get_text (Selenium fetches data)
   - Step 2: custom_python (isolated server processes)
   - Step 3: Use result in Selenium action
3. **Custom Python:**
   - Specify "inputs": list of variable names needed
   - Specify "output": variable name for result
   - Code runs on isolated server (no driver access!)
   - Keep code simple - single line preferred (use semicolons)
4. **For iframes:** Always switch_to_frame → action → switch_to_parent_frame
5. **Use {{variable_name}} everywhere:** In values, conditions, filters

**Real Selenium execution:**
```python
# Later, when filling the form:
for field in gui_fields:
    # Selenium executes each field IN ORDER
    if field['create_action']['create_type'] == 'enter_text':
        driver.find_element(By.CSS_SELECTOR, field['create_action']['update_css']).send_keys(value)
    elif field['create_action']['create_type'] == 'click_button':
        driver.find_element(By.CSS_SELECTOR, field['create_action']['update_css']).click()
    elif field['create_action']['create_type'] == 'select_dropdown':
        select = Select(driver.find_element(By.CSS_SELECTOR, field['create_action']['update_css']))
        select.select_by_value(value)
```

So when you write gui_fields, you're literally writing the test script!

1. **Analyze the DOM** to identify all interactive elements (inputs, dropdowns, checkboxes, radio buttons, buttons, tabs)

2. **CRITICAL: Detect Conditional Fields**
   - Compare PREVIOUS DOM to CURRENT DOM
   - If NEW fields appeared after the last interaction → they are conditional!
   - If fields DISAPPEARED after the last interaction → they were conditional!
   
   **Condition Detection Rules:**
   
   A) **Field APPEARS after interaction:**
      - Last action: Selected "Application" from engagement_type
      - Field "short_description" is NOW visible (wasn't before)
      - Conclusion: Field is NOT editable when engagement_type ≠ "Application"
      - Write: "non_editable_condition": {{"operator": "or", "engagement_type": ["Network", "Asset Discovery", ...]}}
      - (List all OTHER possible values that make it non-editable)
   
   B) **Field DISAPPEARS after interaction:**
      - Last action: Selected "Application" from engagement_type
      - Field "some_field" was visible, now it's GONE
      - Conclusion: Field is NOT editable when engagement_type = "Application"
      - Write: "non_editable_condition": {{"operator": "or", "engagement_type": ["Application"]}}
   
   C) **Field visible in BOTH previous and current DOM:**
      - No condition needed (always editable)
      - Write: "non_editable_condition": {{}}
   
   **IMPORTANT:** non_editable_condition means "field is NOT editable (hidden/disabled) when this condition is TRUE"

3. **Create gui_fields entries** in the order a user would naturally fill the form. Each entry should have:
3. **Create gui_fields entries** in the order a user would naturally fill the form. Each entry should have:
   
   **REMEMBER: gui_fields is executed SEQUENTIALLY by Selenium!**
   - Position in array = Execution order
   - First field in array = First action Selenium takes
   - Last field in array = Last action Selenium takes
   
   Each field entry:
   - "name": Descriptive field name (e.g., "engagement_name", "click_next_button")
   - "iframe_context": null if in main document, or iframe_id string if inside an iframe
   - "create_action": Object with:
     * "create_type": Action type (enter_text, select_dropdown, click_button, click_checkbox, click_radio, click_tab, sleep)
     * "action_description": Human-readable description
     * "update_css": CSS selector for the element
     * "non_editable_condition": **CRITICAL** Object with conditions when field is disabled/hidden
       - "operator": "or" or "and"
       - [field_name]: [array of values] - if this evaluates to TRUE, field is NOT editable
       - Example: {{"operator": "or", "engagement_type": ["Application"]}} means NOT editable when type=Application
       - Empty {{}} means always editable
     * "update_mandatory": true/false
     * "validate_non_editable": false
     * "webdriver_sleep_before_action": seconds to wait before action (string)
   - "update_fields_assignment": Object describing what value to assign
   - "verification_fields_assignment": Object for verification
   - "verification": Verification details
   - "update_api_fields_assignment": API-related assignments
   - "update_action": Similar to create_action but for updates
   - "api_name": API field name (usually empty)

4. **Identify hidden/conditional elements**:
   - Some fields may only appear after clicking tabs, buttons, or selecting dropdown values
   - If you see tabs/buttons that likely reveal more content, request interaction

5. **Handle iframes**: Look for `<!-- IFRAME START: name -->` markers
   - Create "enter_iframe_[name]" stage before iframe fields
   - Create "exit_iframe_[name]" stage after iframe fields
   - Use selenium_actions: [{{"action": "switch_to_frame", "locator": "[IFRAME_XPATH]"}}]

6. **Handle shadow DOM**: Look for `<!-- SHADOW DOM START -->` markers
   - Create "access_shadow_[name]" stage before shadow DOM fields
   - Use selenium_actions: [{{"action": "access_shadow_root", "host_xpath": "[HOST_XPATH]"}}]

7. **Detect hover requirements**: Look for `<!-- REQUIRES_HOVER: true -->` markers
   - Create "hover_before_[field]" stage BEFORE the field
   - Use selenium_actions: [{{"action": "hover", "locator": "[xpath]"}}]

8. **Analyze visibility**: Look for `<!-- VISIBILITY: hidden -->` markers
   - These fields are conditional - determine what makes them visible
   - Set appropriate non_editable_condition

9. **Next button logic**: Only map Next button when:
   - ALL fields on current page are discovered
   - ALL tabs/sections are explored
   - Next button should be LAST field in gui_fields

10. **Sleep times**: Use longer sleeps for:
    - After tabs: "2"
    - After dropdowns with dependencies: "2"  
    - Before entering iframe: "1"
    - After hover: "0.5-1"
    - After Next button: "3"

11. **Request interactions** when needed:
11. **Request interactions** when needed:
   - If you identify an element (tab, button, dropdown) that likely reveals more fields
   - Provide the xpath, action type, and selenium actions to execute
   - Do NOT request interaction for elements already in clicked_xpaths list

12. **Signal completion** when:
   - All visible fields are mapped
   - All tabs/sections have been explored  
   - All iframes have been entered and exited
   - All shadow DOM content has been accessed
   - No more interactive elements will reveal new fields
   - Next button (if present) has been mapped as LAST field

=== OUTPUT FORMAT ===

Return a JSON object with:

{{
  "gui_fields": [
    ... array of field objects as described above ...
  ],
  "mapping_complete": true/false,
  "interaction_request": {{
    "locator": "full xpath",
    "locator_type": "xpath",
    "action_type": "click_button/select_dropdown/etc",
    "action_value": "value to select (for dropdowns)",
    "description": "Human readable description of what this does",
    "selenium_actions": [
      {{
        "action": "wait_for_element",
        "locator": "xpath",
        "locator_type": "xpath",
        "timeout": 10
      }},
      {{
        "action": "click",
        "locator": "xpath",
        "locator_type": "xpath"
      }},
      {{
        "action": "sleep",
        "duration": 1
      }}
    ]
  }},
  "exploration_step": {{
    "reset_to_base_url": true,
    "navigation_sequence": [
      {{
        "action": "select_dropdown|click_tab|click_button|click",
        "locator": "full xpath",
        "locator_type": "xpath",
        "value": "option_value",
        "wait_after": 2
      }}
    ]
  }},
  "iframes_to_explore": [
    {{
      "iframe_id": "unique identifier for this iframe",
      "iframe_xpath": "full xpath to the iframe element",
      "description": "brief description of iframe purpose (optional)"
    }}
  ],
  "reasoning": "Brief explanation of what you mapped and why"
}}

=== IFRAME HANDLING ===

**Understanding iframes:**
iframes are SEPARATE embedded documents. You CANNOT see their contents from outside.
They appear in DOM as: <iframe id="address" src="/form" />

**When you see an <iframe> tag:**
1. You don't know what's inside yet
2. Add it to "iframes_to_explore" array with its id and xpath
3. In the NEXT iteration, you'll receive "iframe_contents" with what's inside
4. Then map those fields normally

**When you receive "iframe_contents" in context:**
You'll get:
{{
  "iframe_contents": {{
    "address_frame": "<html><body><input name='street'/></body></html>",
    "payment_frame": "<html><body><input name='card'/></body></html>"
  }}
}}

Treat each iframe's content as additional DOM to map.
Add fields from iframes to gui_fields WITH iframe_context set.

**CRITICAL: Sequential Execution Order**
Think like Selenium executing a test script - fields are filled ONE BY ONE in order.
Your gui_fields array IS the execution sequence that Selenium will follow.

When Selenium runs your JSON:
```python
for field in gui_fields:  # Executes in order!
    if field['iframe_context']:
        switch_to_iframe(field['iframe_context'])
    execute_action(field['create_action'])
```

Example execution order:
1. field1 (main document, iframe_context: null)
2. field2 (main document, iframe_context: null)  
3. street (inside address_frame, iframe_context: "address_frame")
4. city (inside address_frame, iframe_context: "address_frame")
5. field3 (main document, iframe_context: null)
6. card_number (inside payment_frame, iframe_context: "payment_frame")

Each gui_field must include:
{{
  "name": "street",
  "iframe_context": "address_frame",  // null if main document, string if inside iframe
  "create_action": {{...}}
}}

**Rules:**
- iframes_to_explore: Include ALL <iframe> tags you see
- Use iframe's id/name attribute, or generate unique name like "iframe_0"
- iframe_context in fields: Which iframe the field belongs to (or null)
- You can discover iframes AND request interactions in same iteration

=== IMPORTANT RULES ===

1. **Order matters**: Map fields in the order users would fill them (top to bottom, left to right)
2. **Selenium actions**: Provide complete selenium action sequences including waits
3. **Don't repeat**: Don't request interaction with xpaths already in the clicked list
4. **Be specific**: Use precise CSS selectors (prefer IDs, then specific classes, then attributes)
5. **Non-editable conditions**: Carefully identify when fields are conditional
6. **Complete mapping**: Keep requesting interactions until entire form is mapped
7. **Tabs and sections**: Make sure to create entries for clicking tabs/buttons that reveal content
8. **Next buttons**: If there's a "Next" button at the bottom, include it as a field to click

=== EXAMPLES OF FIELD TYPES ===

**IMPORTANT: Examples of Condition Detection**

**Example 1: Field appears after selecting dropdown value**
```
Previous DOM (Iteration 1):
  <select id="type">
    <option>Network</option>
    <option>Application</option>
  </select>
  <input name="name" />

Last Action: Selected "Application" from type dropdown

Current DOM (Iteration 2):
  <select id="type">
    <option selected>Application</option>
  </select>
  <input name="name" />
  <textarea name="description"></textarea>  ← NEW FIELD!

Conclusion: "description" appeared after selecting "Application"
           → description is NOT editable when type ≠ "Application"
           → description is NOT editable when type = "Network"

Write:
{{
  "name": "description",
  "create_action": {{
    "create_type": "enter_text",
    "update_css": "textarea[name='description']",
    "non_editable_condition": {{
      "operator": "or",
      "type": ["Network"]
    }}
  }}
}}
```

**Example 2: Field disappears after clicking checkbox**
```
Previous DOM:
  <input type="checkbox" id="advanced" />
  <input name="advancedOption" />  ← Field is visible

Last Action: Clicked "advanced" checkbox (checked it)

Current DOM:
  <input type="checkbox" id="advanced" checked />
  (no advancedOption field!)  ← Field DISAPPEARED!

Conclusion: "advancedOption" was hidden when checkbox was checked
           → field is NOT editable when advanced = true/checked

Write:
{{
  "name": "advanced_option",
  "create_action": {{
    "non_editable_condition": {{
      "operator": "or",
      "advanced": [true]
    }}
  }}
}}
```

**Example 3: Multiple conditions (OR)**
```
Field "url_field" only appears when type="Application" OR type="API"
(It's hidden for "Network", "Asset Discovery")

Write:
{{
  "non_editable_condition": {{
    "operator": "or",
    "engagement_type": ["Network", "Asset Discovery"]
  }}
}}
```

**Example 4: No condition (always visible)**
```
Field appears in both previous and current DOM → no condition

Write:
{{
  "non_editable_condition": {{}}
}}
```

---

=== EXAMPLES OF FIELD TYPES ===

**Text Input:**
{{
  "name": "engagement_name",
  "create_action": {{
    "create_type": "enter_text",
    "action_description": "enter engagement name",
    "update_css": "input[name='engagementName']",
    "non_editable_condition": {{}},
    "update_mandatory": true,
    "validate_non_editable": false,
    "webdriver_sleep_before_action": "0.5"
  }},
  "update_fields_assignment": {{
    "type": "assign_random_text",
    "size": "50"
  }},
  ...
}}

**Dropdown:**
{{
  "name": "engagement_type",
  "create_action": {{
    "create_type": "select_dropdown",
    "action_description": "select engagement type",
    "update_css": "select[id='engagementType']",
    "non_editable_condition": {{}},
    "update_mandatory": true,
    "validate_non_editable": false,
    "webdriver_sleep_before_action": "0.5"
  }},
  "update_fields_assignment": {{
    "type": "assign_random_dropdown_value"
  }},
  ...
}}

**Checkbox:**
{{
  "name": "terms_checkbox",
  "create_action": {{
    "create_type": "click_checkbox",
    "action_description": "accept terms",
    "update_css": "input[type='checkbox'][id='terms']",
    "non_editable_condition": {{}},
    "update_mandatory": true,
    "validate_non_editable": false,
    "webdriver_sleep_before_action": "0.5"
  }},
  "update_fields_assignment": {{
    "type": "assign_value",
    "value": true
  }},
  ...
}}

**Button/Tab Click:**
{{
  "name": "click_details_tab",
  "create_action": {{
    "create_type": "click_button",
    "action_description": "click details tab",
    "update_css": "div[id='tab_Details']",
    "non_editable_condition": {{}},
    "update_mandatory": true,
    "validate_non_editable": false,
    "webdriver_sleep_before_action": "1"
  }},
  "update_fields_assignment": {{}},
  ...
}}

**Sleep (for waiting):**
{{
  "name": "sleep_after_save",
  "create_action": {{
    "create_type": "sleep",
    "action_description": "wait for save",
    "webdriver_sleep_before_action": "2"
  }},
  ...
}}

Now analyze the provided DOM and continue building the form mapping.
"""
    
    def build_prompt(self, context: Dict) -> str:
        """
        Build prompt for AI with current context
        
        Args:
            context: Dictionary with form_name, dom, current_json, iframe_contents, etc.
            
        Returns:
            Complete prompt string
        """
        # Format last interaction info
        last_interaction_info = ""
        if context.get('last_interaction'):
            last_int = context['last_interaction']
            last_interaction_info = f"""
LAST INTERACTION EXECUTED:
- Description: {last_int['description']}
- Action Type: {last_int['action_type']}
- Locator: {last_int['locator']}
- Value Selected: {last_int.get('action_value', 'N/A')}
- Result: Successfully executed

Use this to detect conditional fields! If new fields appeared, they depend on this interaction.
"""
        
        # Format clicked elements info
        clicked_elements_info = ""
        if context.get('clicked_xpaths'):
            clicked_elements_info = f"""
ALREADY CLICKED ELEMENTS (do not request these again):
{json.dumps(context['clicked_xpaths'], indent=2)}
"""
        
        # Format previous DOM info
        previous_dom_info = ""
        if context.get('previous_dom') and context['iteration'] > 1:
            previous_dom_info = """
**COMPARE PREVIOUS DOM TO CURRENT DOM TO DETECT CONDITIONS!**
Look for:
- NEW fields that appeared → determine what caused them to appear
- Fields that DISAPPEARED → determine what caused them to disappear
"""
        
        # Format iframe contents info
        iframe_contents_info = ""
        if context.get('iframe_contents') and context['iframe_contents']:
            iframe_contents_info = "\n=== IFRAME CONTENTS (You requested these) ===\n\n"
            for iframe_id, iframe_content in context['iframe_contents'].items():
                iframe_contents_info += f"""
**iframe: {iframe_id}**
Fields inside this iframe should have: "iframe_context": "{iframe_id}"

{iframe_content}

---
"""
        
        # Format current JSON
        current_json_str = json.dumps(
            context['current_json'], 
            indent=2, 
            ensure_ascii=False
        )
        
        # Format previous DOM (truncate if too large)
        previous_dom = context.get('previous_dom') or 'N/A (first iteration)'
        if previous_dom and previous_dom != 'N/A (first iteration)' and len(previous_dom) > 15000:
            previous_dom = previous_dom[:15000] + "\n\n... [PREVIOUS DOM TRUNCATED] ..."
        
        # Truncate current DOM if too large (keep first 20000 chars)
        dom = context['current_dom']
        if len(dom) > 20000:
            dom = dom[:20000] + "\n\n... [DOM TRUNCATED FOR LENGTH] ..."
        
        # NEW: Format exploration context (informational only)
        exploration_info = ""
        if context.get('exploration_context'):
            exp_ctx = context['exploration_context']
            if exp_ctx.get('exploration_active'):
                exploration_info = f"""
=== EXPLORATION CONTEXT (Informational) ===

The orchestrator is systematically exploring all interactive elements.

Current Status:
- Paths explored: {exp_ctx.get('paths_explored', 0)}
- Paths remaining: {exp_ctx.get('paths_remaining', 0)}
"""
        
        # NEW: Format change detection info (informational only)
        changes_info = ""
        if context.get('detected_changes'):
            changes = context['detected_changes']
            
            if changes.get('appeared') or changes.get('disappeared'):
                changes_info = f"""
=== DETECTED CHANGES (Informational) ===

"""
                
                if changes.get('appeared'):
                    appeared_list = [{'id': f.get('id'), 'name': f.get('name')} for f in changes['appeared']]
                    changes_info += f"""**✨ Fields that APPEARED:**
{json.dumps(appeared_list, indent=2)}

"""
                
                if changes.get('disappeared'):
                    disappeared_list = [{'id': f.get('id'), 'name': f.get('name')} for f in changes['disappeared']]
                    changes_info += f"""**⚠️ Fields that DISAPPEARED:**
{json.dumps(disappeared_list, indent=2)}

"""
                
                changes_info += f"""**✓ Stable fields:** {changes.get('unchanged_count', 0)} fields unchanged

Note: The orchestrator will automatically build conditions based on this data. You do NOT need to set non_editable_condition!
"""
        
        # SPECIAL DEBUG: Add direct question on iteration 3
        # COMMENTED OUT - Can be re-enabled if needed for debugging
        debug_question = ""
        # if context['iteration'] == 3:
        #     debug_question = """
        #
        # === 🚨 SPECIAL DEBUG QUESTION FOR YOU 🚨 ===
        #
        # We notice that in your accessible_fields you included "companyName" and "taxId".
        # However, in previous test runs, these fields did NOT appear in your final gui_fields array.
        #
        # **PLEASE ANSWER THESE QUESTIONS:**
        #
        # 1. Are you planning to add "companyName" and "taxId" to gui_fields in THIS iteration?
        # 2. If YES: Confirm you will add them now
        # 3. If NO: Explain why you're NOT adding them to gui_fields even though they're in accessible_fields
        # 4. Have you already added them in iteration 1 or 2? (Check your current_json above)
        #
        # **IMPORTANT:** Please include your answer in a special field in your JSON response:
        # "debug_explanation": "YOUR DETAILED ANSWER HERE"
        #
        # We need to understand your decision-making process!
        # """
        
        # Fill template
        prompt = self.template.format(
            form_name=context['form_name'],
            iteration=context['iteration'],
            last_interaction_info=last_interaction_info,
            clicked_elements_info=clicked_elements_info,
            previous_dom_info=previous_dom_info,
            current_json=current_json_str,
            current_dom=dom,
            previous_dom=previous_dom,
            iframe_contents_info=iframe_contents_info,
            exploration_info=exploration_info,
            changes_info=changes_info,
            current_exploration_depth=context.get('current_exploration_depth', 0),
            max_exploration_depth=context.get('max_exploration_depth', 5),
            explored_states_count=context.get('explored_states_count', 0)
        )
        
        # Append debug question after prompt
        prompt += debug_question
        
        return prompt
    
    def parse_response(self, ai_response: str) -> Dict:
        """
        Parse AI response and extract JSON
        
        Args:
            ai_response: Raw text response from AI
            
        Returns:
            Parsed dictionary with gui_fields, mapping_complete, interaction_request
        """
        import re
        
        # Try to extract JSON from response
        # AI might wrap it in markdown code blocks or provide explanation text
        
        # First, try to find JSON in code blocks
        code_block_match = re.search(r'```(?:json)?\s*(\{.*?\})\s*```', ai_response, re.DOTALL)
        if code_block_match:
            json_str = code_block_match.group(1)
        else:
            # Look for JSON block - find matching braces
            json_start = ai_response.find('{')
            if json_start == -1:
                raise ValueError("No JSON found in AI response")
            
            # Find the matching closing brace by counting braces
            brace_count = 0
            json_end = json_start
            for i in range(json_start, len(ai_response)):
                if ai_response[i] == '{':
                    brace_count += 1
                elif ai_response[i] == '}':
                    brace_count -= 1
                    if brace_count == 0:
                        json_end = i + 1
                        break
            
            if brace_count != 0:
                print(f"  🐛 DEBUG: Unmatched braces detected!")
                print(f"  🐛 DEBUG: Brace count: {brace_count}")
                print(f"  🐛 DEBUG: Trying to find last valid JSON object...")
                
                # Try to find the last complete JSON by searching backwards
                for i in range(len(ai_response) - 1, json_start, -1):
                    if ai_response[i] == '}':
                        # Try this as the end
                        test_str = ai_response[json_start:i+1]
                        test_count = test_str.count('{') - test_str.count('}')
                        if test_count == 0:
                            json_end = i + 1
                            brace_count = 0
                            print(f"  ✓ Found valid JSON ending at position {i}")
                            break
                
                if brace_count != 0:
                    print(f"  🐛 DEBUG: Extracted JSON (first 500 chars):")
                    print(f"  {ai_response[json_start:json_start+500]}")
                    raise ValueError("Unmatched braces in JSON")
            
            json_str = ai_response[json_start:json_end]
        
        try:
            parsed = json.loads(json_str)
        except json.JSONDecodeError as e:
            # Try to fix common JSON issues
            json_str = self._fix_common_json_issues(json_str)
            parsed = json.loads(json_str)
        
        # Validate structure
        if 'gui_fields' not in parsed:
            parsed['gui_fields'] = []
        
        if 'mapping_complete' not in parsed:
            parsed['mapping_complete'] = False
        
        # Fill in any missing fields in gui_fields
        for field in parsed['gui_fields']:
            self._fill_default_field_values(field)
        
        return parsed
    
    def _fix_common_json_issues(self, json_str: str) -> str:
        """Fix common JSON formatting issues"""
        # Remove trailing commas
        json_str = json_str.replace(',}', '}')
        json_str = json_str.replace(',]', ']')
        
        # Handle Python-style booleans
        json_str = json_str.replace('True', 'true')
        json_str = json_str.replace('False', 'false')
        json_str = json_str.replace('None', 'null')
        
        return json_str
    
    def _fill_default_field_values(self, field: Dict):
        """Fill in default values for missing field properties"""
        defaults = {
            "update_fields_assignment": {},
            "verification_fields_assignment": {},
            "verification": {},
            "update_api_fields_assignment": {},
            "update_action": {
                "webdriver_sleep_before_action": ""
            },
            "api_name": ""
        }
        
        for key, default_value in defaults.items():
            if key not in field:
                field[key] = default_value
        
        # Ensure create_action has required fields
        if 'create_action' in field:
            create_action_defaults = {
                "non_editable_condition": {},
                "update_mandatory": True,
                "validate_non_editable": False,
                "webdriver_sleep_before_action": ""
            }
            for key, default_value in create_action_defaults.items():
                if key not in field['create_action']:
                    field['create_action'][key] = default_value


def create_example_prompt():
    """
    Create an example prompt for testing
    """
    prompter = AIPrompter()
    
    context = {
        'form_name': 'engagement',
        'iteration': 1,
        'current_json': {'gui_fields': []},
        'current_dom': '''
<form>
  <input type="text" name="engagementName" placeholder="Enter name...">
  <select id="engagementType">
    <option value="application">Application</option>
    <option value="network">Network</option>
  </select>
  <div id="tab_Scope" class="tab">Scope</div>
  <button type="submit">Save</button>
</form>
        ''',
        'clicked_xpaths': [],
        'is_first_iteration': True
    }
    
    prompt = prompter.build_prompt(context)
    print(prompt)
    return prompt


if __name__ == "__main__":
    create_example_prompt()
