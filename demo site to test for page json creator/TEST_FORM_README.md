# 🧪 Complex Test Form - Full Feature Test Suite

## 🎯 What's Included

A complete test web application with **ALL the tricky features** to test your form mapper:

### ✨ Features Tested:

1. **Basic Fields** ✅
   - Text inputs
   - Email inputs
   - Textareas
   - Dropdowns

2. **Conditional Fields** ✅
   - Fields that show/hide based on dropdown selection
   - Non-editable conditions

3. **Dynamic AJAX Content** ✅
   - Fields that load with 2-second delay
   - Spinner/loading indicators
   - Simulates real-world async loading

4. **Tabs** ✅
   - Multiple tabs (Details, Address, Preferences)
   - Content hidden until tab is clicked

5. **iframes** ✅
   - Level 1 iframe: Address form
   - Level 2 iframe: Nested contact form inside address iframe!
   - Tests iframe context switching

6. **Shadow DOM** ✅
   - Custom web component: `<rating-widget>`
   - Fields encapsulated in shadow root
   - Tests shadow DOM access

7. **Hover Menus** ✅
   - Dropdown that appears on hover
   - Tests hover detection

---

## 🚀 Quick Start

### Step 1: Start the Server

```bash
cd /path/to/test-form
python server.py
```

You should see:
```
🚀 Test Form Server Starting...
📍 Server running at: http://localhost:8000
🧪 Open test form: http://localhost:8000/test-form.html
```

### Step 2: Open in Browser (Optional - to see it)

Visit: http://localhost:8000/test-form.html

Play with the form to see all features in action!

### Step 3: Run Form Mapper

In a **new terminal**:

```bash
# Set your API key
export ANTHROPIC_API_KEY='your-anthropic-api-key-here'

# Run the mapper
python test_mapper.py
```

---

## 📁 Files Included

```
test-form.html          # Main form page
address-form.html       # iframe level 1 (address)
contact-form.html       # iframe level 2 (nested - emergency contact)
server.py              # HTTP server
test_mapper.py         # Test script
README.md              # This file
```

---

## 🧠 What to Expect

### The Mapper Will:

1. **Discover tabs** → Click them → Map fields inside
2. **Find iframes** → Request exploration → Map iframe fields
3. **Detect conditional fields** → Trigger conditions → Map hidden fields
4. **Wait for AJAX** → Spinner disappears → Map dynamic fields
5. **Access Shadow DOM** → Extract contents → Map shadow fields
6. **Detect hover** → Map hover menu fields

### Expected Output:

```json
{
  "gui_fields": [
    {"name": "fullName", "iframe_context": null},
    {"name": "email", "iframe_context": null},
    {"name": "applicationType", "iframe_context": null},
    {"name": "companyName", "non_editable_condition": {...}},
    {"name": "taxId", ...},  // Dynamic AJAX field
    {"name": "click_address_tab", ...},
    {"name": "street", "iframe_context": "addressIframe"},
    {"name": "city", "iframe_context": "addressIframe"},
    {"name": "emergencyName", "iframe_context": "contactIframe"},  // Nested!
    {"name": "ratingComment", "shadow_host_xpath": "..."},  // Shadow DOM!
    ...
  ]
}
```

---

## 🎓 Testing Scenarios

### Test 1: Basic Mapping
Just run the mapper - it should discover everything automatically.

### Test 2: Check Conditional Logic
Look for fields with `non_editable_condition` - they should correctly identify when they're hidden.

### Test 3: Verify iframe Handling
Check that:
- Fields have `iframe_context` set correctly
- Nested iframes are handled (Level 1 and Level 2)

### Test 4: Validate Shadow DOM
Look for fields with `shadow_host_xpath` - these are inside the rating widget.

### Test 5: AJAX Timing
The mapper should wait for the spinner to disappear before mapping the Tax ID field.

---

## 🐛 Troubleshooting

### "Connection refused" when running test_mapper.py
→ Make sure `server.py` is running first!

### "ANTHROPIC_API_KEY not set"
→ Export your API key: `export ANTHROPIC_API_KEY='sk-...'`

### Form mapper gets stuck
→ Check max_iterations (default: 30) - complex form might need more

### iframes not detected
→ Check console logs - orchestrator should print "📦 AI found N iframes"

### Shadow DOM not detected
→ Shadow DOM is pre-extracted - check that rating widget appears in DOM

---

## 📊 Expected Metrics

For this test form:

| Metric | Expected Value |
|--------|----------------|
| Total fields | 20-25 |
| Main document fields | 10-12 |
| iframe fields (level 1) | 4-5 |
| iframe fields (level 2) | 2-3 |
| Shadow DOM fields | 1-2 |
| Conditional fields | 2-3 |
| Tab clicks | 2-3 |
| Iterations needed | 8-15 |
| Total time | 2-5 minutes |

---

## 🎯 Success Criteria

✅ **PASS** if:
- All visible and hidden fields are mapped
- iframe fields have correct `iframe_context`
- Conditional fields have `non_editable_condition`
- Shadow DOM fields are discovered
- No duplicate fields
- Correct execution order

❌ **FAIL** if:
- Missing fields from iframes
- No conditional logic detected
- Shadow DOM fields missing
- Execution order is wrong

---

## 🚀 Next Steps

After testing:

1. **Review the JSON output**
   - Check `complex_test_form_main_setup.json`
   - Verify all fields are present
   - Check iframe_context and conditions

2. **Test Form Filling**
   - Use the JSON to fill the form
   - Verify iframe switching works
   - Check conditional logic execution

3. **Iterate and Improve**
   - Add more complex scenarios
   - Test with your real forms
   - Adjust timeouts if needed

---

## 💡 Tips

- **Headless mode**: Uncomment `options.add_argument('--headless')` in test_mapper.py
- **Slower execution**: Increase sleep times if content loads slowly
- **More iterations**: Increase `max_iterations` for very complex forms
- **Debug mode**: Watch the browser to see what AI is doing

---

## 🎉 Have Fun Testing!

This test form has **every tricky feature** you'll encounter in real-world forms.

If your mapper handles this, it can handle anything! 🚀

---

## 📝 Notes

- Server runs on port 8000 (change in server.py if needed)
- Chrome driver must be installed and in PATH
- Requires Python 3.7+
- Tested on macOS, Linux, Windows

---

**Questions? Issues? Let me know!** 😊
