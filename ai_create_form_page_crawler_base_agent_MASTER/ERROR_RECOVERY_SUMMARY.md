# Form Page Run Error Recovery - Feature Summary

## Files Created/Modified

### 1. **agent_selenium.py** (MODIFIED - 1 new method added)
- Added `capture_error_context()` method
- Returns: `{dom_html, screenshot_base64, screenshot_path}`
- No signature changes to existing methods ✅

### 2. **ai_form_page_run_error.py** (NEW)
- AI-powered error analysis
- Method: `analyze_error(failed_stage, dom_html, screenshot_base64, all_stages, error_message)`
- Returns decision: locator_changed, general_error, need_healing, correction_steps

### 3. **form_page_run.py** (MODIFIED - major updates)
- Added AI error handling integration
- Added retry configurations
- Added error recovery methods

---

## AI Decision Cases

### **Case 1: locator_changed**
Selector/locator is outdated but element exists.

**Flow:**
1. Retry with new locator (max: `max_retries_locator_changed`)
2. If succeeds → Update JSON, continue
3. If fails → Call AI again
4. If fails again → Exit

**Log:** Updates JSON with new locator

---

### **Case 2: general_error**
Page-level issue (404, blank, network error).

**Flow:**
1. Refresh page
2. Retry step once (max: `max_retries_general_error`)
3. If succeeds → Continue
4. If fails → Exit peacefully

**Log:** Error with "check_traffic" flag

---

### **Case 3: need_healing**
Major UI changes (field removed, moved, new fields).

**Flow:**
1. Exit gracefully immediately
2. No retries

**Log:** Error with description + "check_traffic" flag

---

### **Case 4: correction_steps**
Locator fine, page fine, but step needs correction.

**Two sub-types:**

#### 4a. present_only
Just fix present step.

**Flow:**
1. Retry corrected step (max: `max_retries_correction_steps`)
2. If succeeds → Update JSON with corrected step, continue
3. If fails → Call AI again
4. If fails again → Exit

#### 4b. with_presteps
Need preparation steps + corrected step.

**Flow:**
1. Execute all pre-steps
2. Execute corrected step (max: `max_retries_correction_steps`)
3. If succeeds → Update JSON with all steps, continue
4. If fails → Call AI again
5. If fails again → Exit

---

## Configuration (in main())

```python
config = {
    "api_key": os.getenv("ANTHROPIC_API_KEY"),
    "max_retries_locator_changed": 2,     # Retries for locator changes
    "max_retries_general_error": 1,       # Retries for page errors
    "max_retries_correction_steps": 2     # Retries for step corrections
}
```

---

## Error Flow Diagram

```
Stage Fails
    ↓
Capture DOM + Screenshot (agent.capture_error_context())
    ↓
AI Analyzes Error
    ↓
Decision?
    ↓
┌───┴────────────────────────────┐
│                                │
locator_changed    general_error    need_healing    correction_steps
│                  │               │               │
Retry with         Refresh +       Exit            present_only OR with_presteps
new locator        Retry           gracefully      │
│                  │                               Retry corrected (+ presteps)
Success?           Success?                        │
│                  │                               Success?
Update JSON        Continue                        │
Continue                                           Update JSON
                                                   Continue
```

---

## Logging

All error cases log to agent with appropriate messages:

- **locator_changed**: Updates JSON silently
- **general_error**: `[FormPageRunner] general_error failed after refresh - check_traffic`
- **need_healing**: `[FormPageRunner] need_healing - {description} - check_traffic`
- **correction_steps**: Updates JSON on success

---

## Usage

```python
runner = FormPageRunner(
    browser="chrome",
    headless=False,
    api_key=ANTHROPIC_API_KEY,
    max_retries_locator_changed=2,
    max_retries_general_error=1,
    max_retries_correction_steps=2
)

success = runner.run_stages_from_file(
    json_file_path="path/to/stages.json",
    url="http://localhost:8000"
)
```

---

## Files Ready

1. [agent_selenium.py](computer:///mnt/user-data/outputs/agent_selenium.py) - With new capture_error_context() method
2. [ai_form_page_run_error.py](computer:///mnt/user-data/outputs/ai_form_page_run_error.py) - AI error handler
3. [form_page_run.py](computer:///mnt/user-data/outputs/form_page_run.py) - Updated with error recovery

All ready to use!
