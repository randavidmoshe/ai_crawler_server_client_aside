#!/usr/bin/env python3
"""
Test Script: Run Form Mapper Against Complex Test Form

Prerequisites:
1. Start the test server: python server.py
2. Set ANTHROPIC_API_KEY environment variable
3. Run this script: python test_mapper.py

This will test ALL features:
- Basic fields
- Conditional fields
- Dynamic AJAX content
- Tabs
- iframes (including nested!)
- Shadow DOM
- Hover menus
"""

import os
import sys
import time
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from webdriver_manager.chrome import ChromeDriverManager

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def setup_chrome_driver():
    """Setup Chrome driver with options"""
    '''
    options = Options()
    options.add_argument('--start-maximized')
    # options.add_argument('--headless')  # Uncomment to run headless
    options.add_argument('--disable-gpu')
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    
    driver = webdriver.Chrome(options=options)
    '''

    chrome_web_driver: WebDriver
    options = webdriver.ChromeOptions()
    options.add_argument("--incognito")
    options.add_argument("--allow-running-insecure-content")

    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)

    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        print("running webdriver")

    except Exception:
        downloaded_binary_path = ChromeDriverManager().install()
        service = Service(executable_path=downloaded_binary_path)
        driver = webdriver.Chrome(service=service, options=options)

        driver.set_page_load_timeout(40)
    return driver

def test_form_mapper():
    """Test the form mapper against complex test form"""
    
    print("=" * 80)
    print("🧪 TESTING FORM MAPPER ON COMPLEX TEST FORM")
    print("=" * 80)
    
    # Check API key
    api_key = os.environ.get('ANTHROPIC_API_KEY')
    if not api_key:
        print("❌ ERROR: ANTHROPIC_API_KEY environment variable not set!")
        print("   Set it with: export ANTHROPIC_API_KEY='your-key-here'")
        return
    
    # Setup output directory (using current user's home)
    home_dir = os.path.expanduser("~")
    output_dir = os.path.join(home_dir, "automation_product_config", "projects", "complex_test_form")
    print(f"\n📁 Output directory: {output_dir}")
    
    # Create directory if it doesn't exist
    os.makedirs(output_dir, exist_ok=True)
    print(f"   ✓ Directory ready")
    
    # Setup driver
    print("\n1️⃣  Setting up Chrome driver...")
    driver = setup_chrome_driver()
    
    try:
        # Navigate to test form
        test_url = "http://localhost:8000/test-form.html"
        print(f"2️⃣  Navigating to: {test_url}")
        driver.get(test_url)
        
        print("3️⃣  Waiting for page to load...")
        time.sleep(2)
        
        # Import form mapper components
        print("4️⃣  Importing form mapper...")
        from form_mapper_orchestrator import FormMapperOrchestrator
        from ai_client_wrapper import AIClientWrapper
        
        # Create AI client
        print("5️⃣  Creating AI client...")
        ai_client = AIClientWrapper(
            api_key=api_key,
            provider="claude",
            model="claude-sonnet-4-20250514"
        )
        
        # Create orchestrator
        print("6️⃣  Creating orchestrator...")
        orchestrator = FormMapperOrchestrator(
            selenium_driver=driver,
            ai_client=ai_client,
            form_name="complex_test_form",
            max_exploration_depth=5
        )
        
        # Start mapping
        print("\n" + "=" * 80)
        print("🚀 STARTING FORM MAPPING...")
        print("=" * 80)
        
        result = orchestrator.start_mapping(max_iterations=30)
        
        # Save JSON to specified directory
        output_file = os.path.join(output_dir, "complex_test_form_main_setup.json")
        print(f"\n💾 Saving JSON to: {output_file}")
        
        import json
        with open(output_file, 'w', encoding='utf-8') as f:
            json.dump(result, f, indent=4, ensure_ascii=False)
        
        print(f"   ✓ Saved successfully!")
        
        # Print results
        print("\n" + "=" * 80)
        print("✅ MAPPING COMPLETE!")
        print("=" * 80)
        
        print(f"\n📊 Results:")
        print(f"   • Total fields mapped: {len(result.get('gui_fields', []))}")
        print(f"   • Output file: {output_file}")
        
        # Check for special features
        iframe_fields = [f for f in result.get('gui_fields', []) if f.get('iframe_context')]
        shadow_fields = [f for f in result.get('gui_fields', []) if f.get('shadow_host_xpath')]
        conditional_fields = [f for f in result.get('gui_fields', []) 
                            if f.get('create_action', {}).get('non_editable_condition')]
        
        print(f"\n🎯 Feature Detection:")
        print(f"   • Fields in iframes: {len(iframe_fields)}")
        print(f"   • Fields in Shadow DOM: {len(shadow_fields)}")
        print(f"   • Conditional fields: {len(conditional_fields)}")
        
        if iframe_fields:
            print(f"\n📦 iframe Fields:")
            for field in iframe_fields[:5]:  # Show first 5
                print(f"      - {field['name']} (context: {field.get('iframe_context')})")
        
        if shadow_fields:
            print(f"\n🌑 Shadow DOM Fields:")
            for field in shadow_fields[:5]:
                print(f"      - {field['name']}")
        
        if conditional_fields:
            print(f"\n🔀 Conditional Fields:")
            for field in conditional_fields[:5]:
                condition = field['create_action']['non_editable_condition']
                print(f"      - {field['name']}: {condition}")
        
        print("\n" + "=" * 80)
        print("✨ TEST COMPLETE!")
        print("=" * 80)
        print(f"\n📂 Find your JSON at: {output_file}")
        
    except Exception as e:
        print(f"\n❌ ERROR: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\n🧹 Cleaning up...")
        time.sleep(2)
        driver.quit()
        print("👋 Done!")

if __name__ == "__main__":
    test_form_mapper()
