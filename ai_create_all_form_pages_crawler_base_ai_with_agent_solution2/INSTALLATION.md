# Installation & Setup Instructions

## Step 1: Add Method to Agent

**File:** `agent_selenium.py`

**Location:** Inside the `MultiFormsDiscoveryAgent` class (around line 1850, after existing methods)

**Add this method:** (see `agent_discovery_extension.py`)

```python
def get_stable_dom(self, timeout: int = 10) -> Dict:
    # ... (copy full method from agent_discovery_extension.py)
```

## Step 2: Copy New Files

Copy these files to your project directory:

1. ✅ **ai_prompter.py** - AI interface
2. ✅ **orchestrator.py** - Discovery algorithm  
3. ✅ **ai_form_explorer_main.py** - Entry point (replaces your old main)

## Step 3: Install Dependencies

```bash
pip install anthropic beautifulsoup4
```

(selenium and webdriver-manager should already be installed)

## Step 4: Set API Key

```bash
export ANTHROPIC_API_KEY="your-api-key-here"
```

Or set it in the code directly.

## Step 5: Configure & Run

Edit `ai_form_explorer_main.py`:

```python
PROJECT_NAME = "orange_app"
START_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
USERNAME = "Admin"
PASSWORD = "admin123"

MAX_DEPTH = 10     # How deep to explore
MAX_STATES = 100   # Max pages to visit
```

Then run:

```bash
python ai_form_explorer_main.py
```

## What It Does:

1. ✅ Logs in automatically
2. ✅ Starts from dashboard
3. ✅ Explores sidebar menus, tabs, dropdowns
4. ✅ Waits for dynamic content (AJAX)
5. ✅ AI analyzes each page
6. ✅ Finds all forms
7. ✅ Records exact path to each form
8. ✅ Saves to `discovered_forms.json`

## Output Format:

```json
[
  {
    "id": "form_1",
    "name": "Add Employee",
    "url": "https://...",
    "path": [
      {"action": "click", "selector": "...", "description": "Click 'PIM'"},
      {"action": "click", "selector": "...", "description": "Click 'Add'"}
    ],
    "fields": [
      {"type": "text", "label": "First Name", "selector": "#firstName"},
      ...
    ],
    "depth": 2
  }
]
```

## Expected Performance:

- **Time**: ~5-10 minutes for 50 pages
- **Cost**: ~$1-2 for full discovery
- **Forms Found**: All forms accessible via sidebar/tabs/dropdowns

## File Structure:

```
your_project/
├── agent_selenium.py (modified - add get_stable_dom method)
├── ai_prompter.py (new)
├── orchestrator.py (new)
├── ai_form_explorer_main.py (new - entry point)
└── discovered_forms.json (output)
```

## Troubleshooting:

**"No module named anthropic"**
```bash
pip install anthropic
```

**"API key not found"**
```bash
export ANTHROPIC_API_KEY="sk-ant-..."
```

**"Agent has no attribute get_stable_dom"**
- Make sure you added the method to `MultiFormsDiscoveryAgent` class

**Forms not being found**
- Increase MAX_DEPTH (try 15-20)
- Increase MAX_STATES (try 200)
- Check console output for errors

## Next Steps After Discovery:

Once you have `discovered_forms.json`, you can:
1. Review the forms found
2. Use the paths to navigate to each form for testing
3. Each path is a list of Selenium steps you can replay
