# Split Architecture: Agent + Server

## Overview

The form crawler has been split into two components:

1. **Agent** (`agent_form_pages.py`) - Runs on customer desktop with Selenium
2. **Server** (`form_pages_crawler_server.py`) - Runs on your server with AI

Currently they run in the same process for testing, but they're designed to be separated via network later.

## Files

### Agent Side (Customer Desktop)
- **agent_form_pages.py** (1,119 lines)
  - ALL Selenium/WebDriver operations
  - Maintains state (visited_urls, visited_states, etc.)
  - Calls back to server for AI analysis and file operations

### Server Side (Your Server)
- **form_pages_crawler_server.py** (412 lines)
  - ALL AI operations (Claude API calls)
  - ALL file/folder operations
  - JSON creation and updates
  - No Selenium code

### Main Runner
- **ai_form_explorer_main_split.py**
  - Shows how to use both together
  - Creates server first
  - Creates agent with server reference
  - Links them together
  - Currently runs in same process

## How It Works

### Agent → Server Calls

When the agent needs server functionality, it calls:

```python
# AI analysis
form_name = self.server.extract_form_name_with_ai(url, button_text)
is_submit = self.server.is_submission_button_ai(button_text)
candidates = self.server.find_form_page_candidates(page_html, page_url)

# File operations
self.server.update_relationships_json(form_name, url, id_fields)
self.server.create_minimal_json_for_form(form_entry)
self.server.update_form_json(form)
self.server.save_forms_list(forms)

# Hierarchy building
hierarchy = self.server.build_hierarchy(forms)

# Cost tracking
self.server.print_ai_cost_summary()
```

### Server → Agent Calls

When the server needs Selenium operations, it calls:

```python
# Form verification
self.agent._verify_and_fix_form(form)
```

## Running the Code

### Same Process (Current - For Testing)

```python
from agent_form_pages import AgentFormPages
from form_pages_crawler_server import FormPagesCrawler

# 1. Create server (no agent yet)
server = FormPagesCrawler(
    agent=None,
    project_name="my_project",
    use_ai=True,
    api_key="your_key"
)

# 2. Create agent with server reference
agent = AgentFormPages(
    driver=driver,
    start_url=url,
    base_url=base_url,
    server=server,  # Agent knows server
    project_name="my_project",
    max_pages=50,
    max_depth=20,
    use_ai=True,
    target_form_pages=[],
    discovery_only=True,
    slow_mode=True
)

# 3. Link server back to agent
server.agent = agent

# 4. Run
agent.crawl()
```

### Future: Network Separation

Later, replace direct calls with HTTP requests:

**Agent Side:**
```python
# Instead of: form_name = self.server.extract_form_name_with_ai(url, text)
# Do:
response = requests.post("http://server/api/extract_form_name", json={
    "url": url,
    "button_text": text
})
form_name = response.json()["form_name"]
```

**Server Side:**
```python
@app.post("/api/extract_form_name")
def extract_form_name(data: dict):
    url = data["url"]
    button_text = data["button_text"]
    form_name = crawler.extract_form_name_with_ai(url, button_text)
    return {"form_name": form_name}
```

## What Moved Where

### Agent (35 functions with self.driver)
- `_check_dropdown_opened()`
- `_check_if_modal_opened()`
- `_close_modal()`
- `_find_dropdown_items()`
- `_matches_target()`
- `_should_skip_element()`
- `_is_constrained_field()`
- `_extract_id_fields_from_dom()`
- `_update_relationships_json()` - delegates to server
- `_manage_windows()`
- `_safe_click_with_protection()`
- `_gather_all_form_pages()` - main crawler
- `_simple_form_name_cleanup()`
- `_extract_form_name_with_ai()` - delegates to server
- `_is_submission_button_ai()` - delegates to server
- `_wait_for_page_stable()`
- `_save_forms_list()` - delegates to server
- `_is_likely_user_dropdown()`
- `_get_state_key()`
- `_navigate_to_state()`
- `_find_shortest_path()`
- `_find_form_opening_buttons()` - uses server for AI
- `_find_all_clickables()`
- `_find_element_by_selector_or_text()`
- `_get_selector_for_element()`
- `_get_unique_selector()`
- `_get_css_preferred_selector()`
- `_convert_path_to_steps()`
- `_fix_failing_step()`
- `_verify_and_fix_form()`
- `_update_form_json()` - delegates to server
- `_build_hierarchy()` - delegates to server
- `crawl()`
- `close_logger()`

### Server (AI & File Operations)
- `get_existing_form_urls()` - file reading
- `update_relationships_json()` - JSON updates
- `extract_form_name_with_ai()` - AI analysis
- `_simple_form_name_cleanup()` - fallback
- `is_submission_button_ai()` - AI analysis
- `_is_submission_button_keyword()` - fallback
- `find_form_page_candidates()` - AI analysis
- `save_forms_list()` - JSON writing
- `create_minimal_json_for_form()` - folder/JSON creation
- `update_form_json()` - JSON updates
- `build_hierarchy()` - relationship building
- `print_ai_cost_summary()` - cost tracking
- `close_logger()` - cleanup

## Key Changes Made

1. **NO refactoring** - Functions moved AS-IS
2. **ONLY changes**: Added `self.server.` calls where agent needs server functionality
3. **State management**: Agent maintains visited_urls, visited_states, etc.
4. **AI operations**: All moved to server with proper delegation
5. **File operations**: All moved to server

## Benefits

1. **Customer Privacy**: Selenium runs on customer machine, HTML stays local
2. **Cost Optimization**: Only necessary data sent to server for AI analysis
3. **Easy Migration**: Replace direct calls with HTTP requests when ready
4. **Clean Separation**: Agent = browser automation, Server = intelligence & storage
5. **Testable**: Can run in same process now, separate later

## Next Steps

To convert to network architecture:

1. Add Flask/FastAPI to server side
2. Create API endpoints for each server method
3. Replace `self.server.method()` with `requests.post()` in agent
4. Add error handling for network issues
5. Consider authentication/security

## File Sizes

- Original: 2,718 lines (monolithic)
- Agent: 1,119 lines (Selenium only)
- Server: 412 lines (AI & files only)
- Main: 430 lines (initialization)
- **Total: 1,961 lines** (more modular, easier to maintain)
