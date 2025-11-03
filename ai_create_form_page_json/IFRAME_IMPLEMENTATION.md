# iframe Handling Implementation - Complete Guide

## ✅ What's Implemented

**Clean, simple two-way communication:**
- AI → Orchestrator: Optional `iframes_to_explore` array
- Orchestrator → AI: Optional `iframe_contents` object

---

## 🔄 The Flow

### Iteration 1: AI Discovers iframes

**Orchestrator sends:**
```json
{
  "iteration": 1,
  "current_dom": "<html><input name='field1'/><iframe id='address'/><input name='field2'/></html>",
  "iframe_contents": {}  // Empty - no iframes requested yet
}
```

**AI responds:**
```json
{
  "gui_fields": [
    {"name": "field1", "iframe_context": null, ...}
  ],
  "iframes_to_explore": [
    {
      "iframe_id": "address",
      "iframe_xpath": "//iframe[@id='address']",
      "description": "Address form iframe"
    }
  ],
  "interaction_request": {...},  // Can also request tab clicks, etc.
  "mapping_complete": false
}
```

---

### Iteration 2: Orchestrator Provides iframe Contents

**Orchestrator:**
1. Sees `iframes_to_explore` in AI response
2. Switches into each iframe
3. Extracts DOM from inside
4. Switches back

**Orchestrator sends:**
```json
{
  "iteration": 2,
  "current_dom": "...",  // Main document DOM
  "iframe_contents": {
    "address": "<html><body><input name='street'/><input name='city'/></body></html>"
  }
}
```

**AI responds:**
```json
{
  "gui_fields": [
    {"name": "field1", "iframe_context": null, ...},
    {"name": "street", "iframe_context": "address", ...},  // NEW!
    {"name": "city", "iframe_context": "address", ...}      // NEW!
  ],
  "iframes_to_explore": [],  // No new iframes
  "interaction_request": {...}
}
```

---

### Iteration 3: Continue Normally

**Orchestrator sends:**
```json
{
  "iteration": 3,
  "current_dom": "...",
  "iframe_contents": {}  // Empty - AI didn't request any
}
```

AI continues mapping...

---

## 📋 Response Formats

### AI → Orchestrator

```json
{
  "gui_fields": [
    {
      "name": "field_name",
      "iframe_context": null,  // or "iframe_id" if inside iframe
      "create_action": {...},
      "update_fields_assignment": {...},
      ...
    }
  ],
  "iframes_to_explore": [  // OPTIONAL - only if iframes found
    {
      "iframe_id": "address_frame",
      "iframe_xpath": "//iframe[@id='address']",
      "description": "Address input form"
    }
  ],
  "interaction_request": {...},  // OPTIONAL - normal interactions
  "mapping_complete": false,
  "reasoning": "..."
}
```

### Orchestrator → AI

```json
{
  "iteration": 3,
  "form_name": "checkout_form",
  "current_dom": "...",
  "previous_dom": "...",
  "current_json": {...},
  "clicked_xpaths": [...],
  "last_interaction": {...},
  "iframe_contents": {  // OPTIONAL - only if AI requested
    "iframe_id_1": "<html>...</html>",
    "iframe_id_2": "<html>...</html>"
  }
}
```

---

## 🧠 AI Understanding

The AI knows:
1. **iframes are opaque** - can't see inside from outside
2. **Two-step process:**
   - Step 1: Report iframe existence
   - Step 2: Receive contents, map fields
3. **Sequential execution** - gui_fields is the execution order
4. **iframe_context** - Each field knows which iframe it belongs to

---

## 🎯 Example: Complete Flow

### Form Structure:
```html
<html>
  <body>
    <input name="main_field" />
    <iframe id="address">
      <!-- AI can't see this yet -->
      <input name="street" />
      <input name="city" />
    </iframe>
    <input name="another_field" />
  </body>
</html>
```

### Iteration 1:

**Orchestrator → AI:**
- DOM shows: `<input name="main_field"/>`, `<iframe id="address"/>`, `<input name="another_field"/>`

**AI → Orchestrator:**
```json
{
  "gui_fields": [
    {"name": "main_field", "iframe_context": null}
  ],
  "iframes_to_explore": [
    {"iframe_id": "address", "iframe_xpath": "//iframe[@id='address']"}
  ]
}
```

### Iteration 2:

**Orchestrator:**
- Switches to iframe "address"
- Extracts: `<input name="street"/>`, `<input name="city"/>`
- Switches back

**Orchestrator → AI:**
```json
{
  "iframe_contents": {
    "address": "<input name='street'/><input name='city'/>"
  }
}
```

**AI → Orchestrator:**
```json
{
  "gui_fields": [
    {"name": "main_field", "iframe_context": null},
    {"name": "street", "iframe_context": "address"},
    {"name": "city", "iframe_context": "address"},
    {"name": "another_field", "iframe_context": null}
  ],
  "mapping_complete": true
}
```

---

## 🔧 Implementation Details

### In `ai_prompter.py`:
- Added iframe handling instructions to prompt
- Added `iframe_contents_info` formatting in `build_prompt()`
- Added `iframes_to_explore` to response schema

### In `form_mapper_orchestrator.py`:
- Added `iframe_contents: Dict[str, str]` to `MappingState`
- Added `_extract_iframe_contents()` method
- Updated `_process_ai_response()` to handle iframe requests
- Updated `_prepare_ai_context()` to include iframe_contents

### Orchestrator Logic:
```python
def _extract_iframe_contents(self, iframes_to_explore):
    for iframe_info in iframes_to_explore:
        # Switch to iframe
        driver.switch_to.frame(iframe_element)
        
        # Extract DOM
        iframe_dom = extractor.extract_interactive_elements()
        
        # Store
        self.state.iframe_contents[iframe_id] = iframe_dom
        
        # Switch back
        driver.switch_to.default_content()
```

---

## 🚀 Benefits

### 1. Simple & Clean
- One response format
- Optional fields on both sides
- No complex markers needed

### 2. Consistent Pattern
- Same as tabs: "I see something → explore it → map what's inside"
- AI discovers naturally, not forced

### 3. Sequential Execution
```python
for field in gui_fields:
    if field['iframe_context']:
        ensure_in_iframe(field['iframe_context'])
    fill_field(field)
```

### 4. Flexible
- AI can request iframes AND interactions in same iteration
- Orchestrator provides what was requested
- No wasted iterations

---

## 📊 Form Filler Integration

### Your form filler code:

```python
current_iframe = None

for field in gui_fields:
    required_iframe = field.get('iframe_context')
    
    # Switch iframe if needed
    if required_iframe != current_iframe:
        if current_iframe:
            driver.switch_to.default_content()
        
        if required_iframe:
            iframe_xpath = get_iframe_xpath(required_iframe)
            driver.switch_to.frame(driver.find_element(By.XPATH, iframe_xpath))
        
        current_iframe = required_iframe
    
    # Fill the field (now in correct context)
    fill_field(driver, field)

# Switch back to main at end
if current_iframe:
    driver.switch_to.default_content()
```

**Where do you store iframe XPath?**

Option A: Store in metadata section of JSON:
```json
{
  "gui_fields": [...],
  "iframe_metadata": {
    "address": {
      "xpath": "//iframe[@id='address']"
    }
  }
}
```

Option B: AI includes it in first field of iframe:
```json
{
  "name": "street",
  "iframe_context": "address",
  "iframe_xpath": "//iframe[@id='address']"  // Only on first field
}
```

**Your choice!** Let me know if you want me to implement Option A or B.

---

## ✅ Files Updated

- **[ai_prompter.py](computer:///mnt/user-data/outputs/ai_prompter.py)** - iframe instructions + response format
- **[form_mapper_orchestrator.py](computer:///mnt/user-data/outputs/form_mapper_orchestrator.py)** - iframe extraction logic

**All previous enhancements still included!** ✅

---

## 🎯 Summary

**Problem:** AI can't see inside iframes from outside DOM  
**Solution:** Two-step discovery → AI reports iframes, orchestrator provides contents  
**Result:** Clean, simple, works with existing pattern! 🚀

**YES - All fixes are cumulative!** ✅
