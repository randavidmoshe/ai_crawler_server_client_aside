# Web Application Form Page Discovery Feature

## Overview
New feature that automatically discovers all form pages in a web application using AI-powered exploration with Depth-First Search (DFS) strategy.

## Files Created

### 1. `all_form_pages_main.py`
- **Based on**: `form_page_main.py` (copy with minimal modifications)
- **Changes**:
  - Added new parameters: `all_form_pages`, `url_for_login`, `username_for_login`, `password_for_login`
  - Added login logic at entry point
  - Switches between exploration AI and testing AI based on `all_form_pages` flag
  - Tracks cataloged form pages
  - Saves discovered form pages to JSON file
  - Handles form page detection after initial generation and DOM changes

### 2. `ai_all_form_pages_main_prompter.py`
- **Based on**: `ai_form_page_main_prompter.py` (copy)
- **New Method**: `generate_exploration_steps()`
- **Exploration Logic**:
  - Analyzes current page to detect if it's a form page
  - Generates navigation steps using DFS strategy
  - Prevents loops by checking executed steps
  - Handles backtracking when exploration path exhausted
  - Detects exploration completion

## How It Works

### Entry Configuration
```python
config = {
    "all_form_pages": True,  # Enable discovery mode
    "url_for_login": "http://localhost:8000/login",
    "username_for_login": "admin",
    "password_for_login": "password123",
    # ... other params
}
```

### Workflow
1. **Login**: Navigate to login URL → fill credentials → login → dashboard becomes base_url
2. **Initial Analysis**: AI analyzes dashboard → decides first exploration steps
3. **Execution Loop**:
   - Execute steps one by one
   - After each step, check for DOM/field changes
   - If changed → call AI with new state
   - If form page detected → catalog it and continue
4. **Form Page Detection**: AI identifies pages with:
   - Multiple input fields (various types)
   - Save/submit button
   - Purpose is to create/edit data
5. **Completion**: When all navigation paths explored, save cataloged pages

### AI Strategy (DFS)
- Click tabs, menu items, dropdown options
- Dive deep into each option before moving to siblings
- When form page found → catalog and backtrack
- When no more options → backtrack to last junction
- Continue until all paths explored

### Output
Saved to: `/home/{username}/automation_product_config/ai_projects/local_web_site/form_pages_discovery/all_form_pages/discovered_form_pages.json`

Format:
```json
[
  {
    "form_name": "User Management Form",
    "navigation_path": "Admin → User Management → Add User",
    "entry_point": "Click Add User button",
    "field_types": ["text", "email", "select", "checkbox"],
    "submit_button": "Save User"
  },
  ...
]
```

## Key Design Decisions

### What Was NOT Changed
1. **agent_selenium.py**: No changes (used by other systems)
2. **Agent function signatures**: Kept intact
3. **Core orchestrator loop**: Same execution logic
4. **Alert recovery**: Reuses existing `ai_form_page_alert_recovery_prompter.py`
5. **UI verification**: Kept for detecting visual defects

### What Was Added
1. **Login logic**: Only in `all_form_pages_main.py`
2. **Exploration intelligence**: All in AI prompter
3. **Form page cataloging**: Tracking and saving
4. **Mode switching**: Between exploration and testing AI

### Optimizations
- **Full DOM**: Keeps complete structure for better AI understanding
- **DOM/Field change detection**: Only calls AI when necessary (not every step)
- **Loop prevention**: AI checks executed steps to avoid revisiting
- **Junction tracking**: AI understands where to backtrack

## AI Prompt Strategy

### Form Page Detection
AI checks for:
1. Multiple input fields (text, select, checkbox, etc.)
2. Save/submit/update button present
3. Purpose is data entry/editing

### Navigation Rules
**Click:**
- Tabs, menu items, dropdown options
- Entry point buttons (Add, Create, New, Edit, +)

**Don't Click:**
- Verify/Search buttons (not navigation)
- Data table rows
- Read-only displays

**Stop Generation:**
- When form page detected, don't include steps beyond it

### Modal Handling
- Check if modal is form page → catalog
- If not → close and continue

## Testing
To test the feature:
1. Set `all_form_pages: True` in config
2. Provide login credentials
3. Run `python all_form_pages_main.py`
4. Check output JSON for discovered pages

## Future Enhancements (Not Implemented)
- DOM thinning/squeezing for token optimization
- AI-powered login field detection (currently uses common selectors)
- Depth limit configuration
- Exclusion patterns (e.g., skip logout, settings)
- Visual similarity detection for already-visited pages
