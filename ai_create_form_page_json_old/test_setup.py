"""
Test Script - Verify Form Mapper Setup
Run this to test your installation and setup
"""

def test_imports():
    """Test if all required modules can be imported"""
    print("Testing imports...")
    
    try:
        import selenium
        print("✓ Selenium imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import selenium: {e}")
        return False
    
    try:
        import lxml
        print("✓ lxml imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import lxml: {e}")
        return False
    
    try:
        from form_mapper_orchestrator import FormMapperOrchestrator
        print("✓ FormMapperOrchestrator imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import FormMapperOrchestrator: {e}")
        return False
    
    try:
        from ai_prompter import AIPrompter
        print("✓ AIPrompter imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import AIPrompter: {e}")
        return False
    
    try:
        from dom_extractor import DOMExtractor
        print("✓ DOMExtractor imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import DOMExtractor: {e}")
        return False
    
    try:
        from selenium_executor import SeleniumExecutor
        print("✓ SeleniumExecutor imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import SeleniumExecutor: {e}")
        return False
    
    try:
        from ai_client_wrapper import AIClientWrapper
        print("✓ AIClientWrapper imported successfully")
    except ImportError as e:
        print(f"✗ Failed to import AIClientWrapper: {e}")
        return False
    
    return True


def test_selenium_driver():
    """Test if Selenium WebDriver can be initialized"""
    print("\nTesting Selenium WebDriver...")
    
    try:
        from selenium import webdriver
        from selenium.webdriver.chrome.options import Options
        
        options = Options()
        options.add_argument('--headless')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        
        driver = webdriver.Chrome(options=options)
        driver.get('https://www.example.com')
        
        title = driver.title
        driver.quit()
        
        print(f"✓ WebDriver works! Page title: {title}")
        return True
        
    except Exception as e:
        print(f"✗ WebDriver failed: {e}")
        print("\nMake sure you have:")
        print("  1. Chrome browser installed")
        print("  2. ChromeDriver installed and in PATH")
        print("  3. Run: brew install chromedriver  (Mac)")
        print("     Or download from: https://chromedriver.chromium.org/")
        return False


def test_ai_client():
    """Test AI client (mock mode)"""
    print("\nTesting AI Client (mock mode)...")
    
    try:
        from ai_client_wrapper import MockAIClient
        
        client = MockAIClient()
        response = client.generate("test prompt")
        
        if response:
            print("✓ Mock AI client works!")
            return True
        else:
            print("✗ Mock AI client returned empty response")
            return False
            
    except Exception as e:
        print(f"✗ AI client test failed: {e}")
        return False


def test_ai_prompter():
    """Test AI prompter"""
    print("\nTesting AI Prompter...")
    
    try:
        from ai_prompter import AIPrompter
        
        prompter = AIPrompter()
        
        context = {
            'form_name': 'test_form',
            'iteration': 1,
            'current_json': {'gui_fields': []},
            'current_dom': '<input name="test" />',
            'clicked_xpaths': [],
            'is_first_iteration': True
        }
        
        prompt = prompter.build_prompt(context)
        
        if len(prompt) > 100:
            print("✓ AI Prompter works!")
            return True
        else:
            print("✗ AI Prompter returned short prompt")
            return False
            
    except Exception as e:
        print(f"✗ AI Prompter test failed: {e}")
        return False


def run_all_tests():
    """Run all tests"""
    print("="*60)
    print("FORM MAPPER - SETUP TEST")
    print("="*60)
    print()
    
    results = []
    
    results.append(("Imports", test_imports()))
    results.append(("Selenium WebDriver", test_selenium_driver()))
    results.append(("AI Client (Mock)", test_ai_client()))
    results.append(("AI Prompter", test_ai_prompter()))
    
    print("\n" + "="*60)
    print("TEST SUMMARY")
    print("="*60)
    
    for name, passed in results:
        status = "✓ PASS" if passed else "✗ FAIL"
        print(f"{status:10} {name}")
    
    all_passed = all(passed for _, passed in results)
    
    if all_passed:
        print("\n✓ All tests passed! You're ready to use Form Mapper.")
        print("\nNext steps:")
        print("  1. Set your API key: export ANTHROPIC_API_KEY='your-key'")
        print("  2. Run: python example_usage.py 'URL' 'form_name'")
    else:
        print("\n✗ Some tests failed. Please fix the issues above.")
    
    return all_passed


if __name__ == "__main__":
    import sys
    success = run_all_tests()
    sys.exit(0 if success else 1)
