# Form Page Crawler - 3-File Structure

## 📦 Project Files

This project is now split into **3 clean, modular files**:

```
form_page_crawler_base/
├── main.py                          # Entry point, orchestration, config
├── ai_prompter.py                   # AI logic and prompts
├── selenium_actions.py              # Selenium actions and DOM handling
└── generic_form_page_crawler_test_cases.json  # Test cases
```

---

## 📄 File Descriptions

### 1. **main.py** (~800 lines)
**Purpose:** Entry point and test orchestration

**Contains:**
- Configuration (paths, constants)
- `run()` function - main entry point
- `TestOrchestrator` class - orchestrates test execution
- `TestContext` class - tracks form state
- `TestCaseRepository` class - loads test cases
- WebDriver initialization
- Logging setup
- Entry point `if __name__ == "__main__"`

**Key Classes:**
```python
class TestContext:
    # Tracks form fields, choices, tabs, credentials
    
class TestCaseRepository:
    # Loads test cases from JSON
    
class TestOrchestrator:
    # Main orchestration logic
    def run_with_ai()      # AI mode execution
    def run_from_json()    # Replay mode execution
```

---

### 2. **ai_prompter.py** (~600 lines)
**Purpose:** All AI-related functionality

**Contains:**
- `AIHelper` class
- `generate_test_steps()` - massive AI prompt for step generation
- `discover_test_scenarios()` - exploratory testing
- Claude API integration
- JSON parsing from AI responses

**Key Class:**
```python
class AIHelper:
    def generate_test_steps(dom_html, test_cases, ...) -> List[Dict]
    def discover_test_scenarios(dom_html, ...) -> List[Dict]
```

**Why separate?**
- Isolates AI logic from execution
- Easy to modify prompts
- Can swap AI providers easily

---

### 3. **selenium_actions.py** (~1300 lines)
**Purpose:** All Selenium and DOM handling

**Contains:**
- `DOMCache` class - caching with hash validation
- `DOMExtractor` class - minimal DOM extraction (80-90% reduction)
- `DOMChangeDetector` class - detects DOM changes
- `ContextAnalyzer` class - smart context detection
- `StepExecutor` class - executes all Selenium actions

**Key Classes:**
```python
class DOMCache:
    # Cache DOM by URL with hash validation
    
class DOMExtractor:
    # Extract minimal DOM (huge cost savings!)
    
class DOMChangeDetector:
    # Detect when DOM changes
    
class ContextAnalyzer:
    # Determine if verification elements needed
    
class StepExecutor:
    # Execute all actions: click, fill, select, verify, etc.
    def execute_step(step) -> bool
```

**Why separate?**
- All Selenium logic in one place
- DOM optimizations grouped together
- Easy to add new actions

---

## 🚀 How to Use

### Quick Start

1. **Set API Key:**
```bash
export ANTHROPIC_API_KEY="your-api-key"
```

2. **Edit Configuration in main.py:**
```python
FORM_PAGE_KEY = "my_contact_form"
URL = "https://example.com/contact"
MODE = "ai"
HEADLESS = False
```

3. **Run:**
```bash
python form_page_main.py
```

---

## 📁 File Organization

### Output Structure
```
~/automation_product_config/
└── form_page_crawler_base/          ← Base directory
    └── my_contact_form/             ← Your form_page_key
        ├── ai_generated_steps.json  ← Generated test steps
        └── screenshots/
            ├── failure_*.png
            └── ...
```

### Example - Multiple Forms
```
~/automation_product_config/
└── form_page_crawler_base/
    ├── contact_form/
    │   ├── ai_generated_steps.json
    │   └── screenshots/
    ├── registration_form/
    │   ├── ai_generated_steps.json
    │   └── screenshots/
    └── survey_form/
        ├── ai_generated_steps.json
        └── screenshots/
```

---

## 🔧 Configuration Options

### In main.py (bottom of file):

```python
# Identifier for file organization
FORM_PAGE_KEY = "my_form_test"

# Target URL - REQUIRED!
URL = "https://example.com/form"

# Mode: "ai" or "replay"
MODE = "ai"

# Browser visibility
HEADLESS = False

# API Key (from environment variable)
API_KEY = os.environ.get("ANTHROPIC_API_KEY")

# Regeneration strategy
REGENERATE_ONLY_ON_URL_CHANGE = True
```

---

## 💡 Key Features

### ✅ AI-Powered
- Analyzes form structure automatically
- Generates realistic test data
- Adapts to DOM changes

### ✅ Cost Optimized
- **Minimal DOM:** 80-90% size reduction
- **Smart Caching:** Hash-validated cache
- **Context Detection:** Only includes verification elements when needed
- **Expected savings: 75-85%**

### ✅ Modular Design
- 3 clean files with clear responsibilities
- Easy to understand and modify
- Easy to extend with new features

### ✅ Robust
- Screenshot capture on failures
- Detailed logging
- DOM change detection
- Replay mode for regression testing

---

## 📊 How It Works

### AI Mode Flow:
```
1. main.py calls run()
   ↓
2. Initialize driver and orchestrator
   ↓
3. Navigate to form URL
   ↓
4. DOMExtractor gets minimal DOM (selenium_actions.py)
   ↓
5. Check DOMCache for existing data (selenium_actions.py)
   ↓
6. AIHelper generates steps (ai_prompter.py)
   ↓
7. StepExecutor runs steps (selenium_actions.py)
   ↓
8. Detect DOM changes (selenium_actions.py)
   ↓
9. Regenerate if needed (back to step 5)
   ↓
10. Save results
```

### Replay Mode Flow:
```
1. main.py calls run() with mode="replay"
   ↓
2. Load steps from JSON
   ↓
3. Navigate to form URL
   ↓
4. StepExecutor runs each step
   ↓
5. Complete
```

---

## 🎯 Module Dependencies

```
main.py
  ├── imports ai_prompter.AIHelper
  └── imports selenium_actions.*
      ├── DOMCache
      ├── DOMExtractor
      ├── DOMChangeDetector
      ├── ContextAnalyzer
      └── StepExecutor

ai_prompter.py
  └── standalone (only external: anthropic)

selenium_actions.py
  └── standalone (only external: selenium, beautifulsoup4)
```

---

## 🔄 Adding New Features

### Add a new Selenium action:
→ Edit `selenium_actions.py` → `StepExecutor.execute_step()`

### Modify AI prompt:
→ Edit `ai_prompter.py` → `AIHelper.generate_test_steps()`

### Add new test orchestration logic:
→ Edit `main.py` → `TestOrchestrator` class

### Add form tracking features:
→ Edit `main.py` → `TestContext` class

---

## 🐛 Troubleshooting

### Import Errors
Make sure all 3 files are in the same directory:
```
form_page_crawler_base/
├── main.py
├── ai_prompter.py
└── selenium_actions.py
```

### "Module not found"
Run from the directory containing the files:
```bash
cd /path/to/form_page_crawler_base
python form_page_main.py
```

### Check Logs
Logs show which file is executing what:
```
[AIHelper] Sending request...     ← ai_prompter.py
[DOMExtractor] Minimal DOM...     ← selenium_actions.py
[Orchestrator] Running tests...   ← main.py
```

---

## 📈 Performance

### File Sizes:
- **main.py:** ~800 lines (orchestration)
- **ai_prompter.py:** ~600 lines (AI logic)
- **selenium_actions.py:** ~1300 lines (Selenium + DOM)
- **Total:** ~2700 lines (same as before, just organized!)

### Benefits of 3-File Structure:
✅ **Easier to navigate** - Find code faster
✅ **Easier to modify** - Change one area without affecting others
✅ **Easier to debug** - Isolate issues to specific modules
✅ **Easier to extend** - Add features to appropriate file
✅ **Better organization** - Clear separation of concerns

---

## 🎓 Quick Reference

### To Run AI Mode:
```bash
python form_page_main.py
```

### To Run Replay Mode:
```python
# Edit form_page_main.py
MODE = "replay"
```
```bash
python form_page_main.py
```

### To Test Different Forms:
```python
# Edit form_page_main.py for each form
FORM_PAGE_KEY = "contact_form"
URL = "https://example.com/contact"
```

### To Add Custom Test Cases:
Edit `generic_form_page_crawler_test_cases.json`

---

## 🎉 Summary

**3 clean files:**
1. **main.py** - Runs everything
2. **ai_prompter.py** - Talks to AI
3. **selenium_actions.py** - Controls browser

**Same functionality, better organization!**

✅ All optimizations preserved  
✅ Same 75-85% cost savings  
✅ Same robust error handling  
✅ Now easier to understand and modify!

---

## 📞 Need Help?

Check the code comments - each file is well-documented!

Each class has:
- Clear purpose description
- Method documentation
- Inline comments for complex logic

Happy testing! 🧪✨
