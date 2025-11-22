# AI-Powered Form Discovery System

## Overview

This system automatically discovers all form pages in a web application by intelligently exploring navigation menus, tabs, and dropdowns using AI (Claude) + Selenium.

## Architecture

```
ai_form_explorer_main.py (Entry Point)
    ↓
orchestrator.py (Exploration Algorithm)
    ↓
ai_prompter.py (AI Analysis) + agent_selenium.py (Browser Automation)
```

## Files

1. **ai_form_explorer_main.py** - Entry point, handles login and setup
2. **orchestrator.py** - Core discovery algorithm (BFS exploration, state tracking)
3. **ai_prompter.py** - AI integration (Claude API calls, DOM analysis)
4. **agent_selenium.py** - Selenium agent (unchanged, uses existing methods)

## How It Works

1. **Start**: Logs into the application and reaches the dashboard
2. **Explore**: Uses AI to analyze each page and find:
   - Is this page a form? (has input fields + submit)
   - What navigation items lead to other pages? (sidebar, tabs, dropdowns)
3. **Queue**: Adds promising navigation paths to exploration queue
4. **Repeat**: Visits each queued state, analyzes, queues more
5. **Track**: Records the exact path to reach each form
6. **Save**: Outputs JSON with all discovered forms and their paths

## Output Format

```json
[
  {
    "id": "form_1",
    "name": "Add Employee",
    "url": "https://app.com/pim/addEmployee",
    "path": [
      {
        "action": "click",
        "selector": "a[href='/pim']",
        "description": "Click 'PIM'"
      },
      {
        "action": "click",
        "selector": "#add-employee-btn",
        "description": "Click 'Add Employee' button"
      }
    ],
    "fields": [
      {"type": "text", "label": "First Name", "selector": "#firstName"},
      {"type": "text", "label": "Last Name", "selector": "#lastName"}
    ],
    "depth": 2
  }
]
```

## Installation

```bash
pip install selenium anthropic beautifulsoup4 webdriver-manager
```

## Usage

### Basic Usage

```python
python ai_form_explorer_main.py
```

### Configuration (in main file)

```python
PROJECT_NAME = "orange_app"
START_URL = "https://your-app.com/login"
USERNAME = "your_username"
PASSWORD = "your_password"

MAX_DEPTH = 10    # How many levels deep to explore
MAX_STATES = 100  # Maximum number of pages to visit

API_KEY = os.environ.get("ANTHROPIC_API_KEY")
```

### Environment Variables

```bash
export ANTHROPIC_API_KEY="your-api-key"
```

## Key Features

### ✅ Comprehensive Discovery
- Finds forms behind sidebar navigation
- Finds forms behind tabs
- Finds forms behind dropdown selections
- Explores combinations (e.g., tab + dropdown)

### ✅ Smart Exploration
- AI prioritizes likely form locations ("Add", "Create", "Edit" buttons)
- Avoids redundant paths
- Tracks visited states to prevent loops
- Configurable depth and state limits

### ✅ Path Recording
- Records exact Selenium steps to reach each form
- Steps are replayable for testing
- Includes selectors and descriptions

### ✅ Cost Optimization
- Simplifies DOMs before sending to AI (reduces tokens)
- Caches AI analysis results
- Only analyzes unique page states

## Algorithm Details

### Exploration Strategy: Breadth-First with Priority

```
1. Start at dashboard (depth 0)
2. Get DOM, send to AI
3. AI returns:
   - is_form_page: true/false
   - navigation_items: [{selector, text, priority}, ...]
   - tabs: [{selector, text}, ...]
   - dropdowns: [{selector, options}, ...]
4. If form found → Register it with path
5. Queue all opportunities (high priority first)
6. Pop next state from queue
7. Navigate to state (replay interaction path)
8. Go to step 2
9. Stop when:
   - Queue empty
   - Max depth reached
   - Max states explored
```

### State Hashing

Each page state is hashed based on:
- URL
- Form structure (input fields present)
- Page headings

This prevents revisiting the same page multiple times.

## Example Run

```
==================================================================
🔍 STARTING FORM DISCOVERY
==================================================================
Start URL: https://opensource-demo.orangehrmlive.com/web/index.php/dashboard
Max Depth: 10
Max States: 100
==================================================================

[Orchestrator] Exploring state (depth=0, queue=0)
[Orchestrator] Path: Dashboard (start)
[Orchestrator] 🤖 Analyzing page with AI...
[AI] Calling Claude API... (DOM size: 3421 chars)
[Orchestrator] ℹ️ Not a form page
[Orchestrator] Queued 8 new states (queue size: 8)

[Orchestrator] Exploring state (depth=1, queue=7)
[Orchestrator] Path: Dashboard (start) → Click 'PIM'
[Orchestrator]   → Click 'PIM'
[Orchestrator] 🤖 Analyzing page with AI...
[AI] Calling Claude API... (DOM size: 4123 chars)
[Orchestrator] ℹ️ Not a form page
[Orchestrator] Queued 3 new states (queue size: 9)

[Orchestrator] Exploring state (depth=2, queue=8)
[Orchestrator] Path: Dashboard (start) → Click 'PIM' → Click 'Add Employee' button
[Orchestrator]   → Click 'PIM'
[Orchestrator]   → Click 'Add Employee' button
[Orchestrator] 🤖 Analyzing page with AI...
[AI] Calling Claude API... (DOM size: 5234 chars)

==================================================================
✅ FORM FOUND: Add Employee
==================================================================
URL: https://opensource-demo.orangehrmlive.com/web/index.php/pim/addEmployee
Path: Dashboard (start) → Click 'PIM' → Click 'Add Employee' button
Fields: 8
==================================================================

... continues exploring ...

==================================================================
✅ DISCOVERY COMPLETE
==================================================================
States explored: 42
Forms found: 15
==================================================================
```

## Limitations

- Only finds forms accessible via simple navigation (clicks, tabs, dropdowns)
- Does not handle:
  - Forms requiring complex multi-step setup
  - Forms behind authentication/permissions
  - Forms with context-dependent visibility
- Depth/state limits may prevent finding deeply nested forms

## Cost Estimation

- ~2000-4000 tokens per AI call
- If exploring 50 states = 50 AI calls = ~150K tokens
- Cost: ~$0.45 for input + ~$2.25 for output = ~$2.70 total

## Troubleshooting

### No API Key Error
```
export ANTHROPIC_API_KEY="your-key-here"
```

### Browser Not Opening
Check Chrome/ChromeDriver installation:
```bash
pip install webdriver-manager
```

### Forms Not Found
- Increase `MAX_DEPTH` (try 15-20)
- Increase `MAX_STATES` (try 200-300)
- Check if forms require special authentication

### AI Analysis Errors
- Check API key is valid
- Check internet connection
- Verify Claude API quota/limits

## Future Enhancements

- [ ] Support for modals/dialogs
- [ ] Support for hover menus
- [ ] Multi-step form detection
- [ ] Parallel exploration (multiple browser instances)
- [ ] Resume capability (save/load exploration state)
- [ ] Visual form tree output
