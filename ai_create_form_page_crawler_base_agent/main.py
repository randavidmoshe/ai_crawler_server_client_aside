# main.py
# LOCAL TESTING MODE
# Run everything on one machine for testing/development

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../agent'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../server'))

from agent_selenium import AgentSelenium
from ai_prompter import AIHelper
import time
import json
import hashlib
from typing import List, Dict, Optional


class LocalTestOrchestrator:
    """
    Local testing orchestrator
    Uses agent_selenium.py directly (no remote agent needed)
    For testing and development only
    """
    
    def __init__(
        self,
        anthropic_api_key: str,
        test_cases_file: str,
        browser: str = "chrome",
        headless: bool = False
    ):
        # Initialize Selenium (from agent code)
        self.selenium = AgentSelenium()
        
        # Initialize AI helper (server code)
        self.ai = AIHelper(api_key=anthropic_api_key)
        
        # Configuration
        self.browser = browser
        self.headless = headless
        
        # Load test cases
        import os
        if not os.path.exists(test_cases_file):
            print(f"⚠️ Test cases file not found: {test_cases_file}")
            print(f"   Using default test case")
            self.test_cases = [{
                "test_id": "generic_form_fill",
                "description": "Fill and submit a generic form",
                "test_data": {}
            }]
        else:
            with open(test_cases_file, 'r') as f:
                self.test_cases = json.load(f)
        
        # Tracking
        self.test_context = TestContext()
        self.current_dom_hash = None
        
        print(f"✅ Local orchestrator initialized")
        print(f"   Browser: {browser}")
        print(f"   Headless: {headless}")
        print(f"   Test cases: {len(self.test_cases)}")
    
    def run_test(self, url: str):
        """
        Run complete test locally
        
        Args:
            url: Starting URL to test
        """
        try:
            print("\n" + "="*70)
            print("🤖 STARTING LOCAL TEST")
            print("="*70)
            
            # Initialize browser
            print("\n🌐 Initializing browser...")
            result = self.selenium.initialize_browser(
                browser_type=self.browser,
                headless=self.headless
            )
            
            if not result["success"]:
                print(f"❌ Failed to initialize browser: {result.get('error')}")
                return False
            
            print(f"✅ Browser initialized: {result['browser']}")
            
            # Navigate to URL
            print(f"\n🌐 Navigating to {url}...")
            result = self.selenium.navigate_to_url(url)
            
            if not result["success"]:
                print(f"❌ Navigation failed: {result.get('error')}")
                return False
            
            print(f"✅ Navigated to: {result['url']}")
            
            # Test from current page
            return self.run_test_from_current_page()
            
        except Exception as e:
            print(f"\n❌ Test failed with error: {e}")
            import traceback
            traceback.print_exc()
            return False
        finally:
            # Always close browser
            print("\n🔒 Closing browser...")
            self.selenium.close_browser()
            print("✅ Browser closed")
    
    def run_test_from_current_page(self):
        """
        Test form from current page
        Assumes browser is already on the form page
        """
        print("\n" + "="*70)
        print("📋 TESTING FORM FROM CURRENT PAGE")
        print("="*70)
        
        # Extract initial DOM
        print("\n📄 Extracting initial DOM...")
        dom_result = self.selenium.extract_form_dom_with_js()
        
        if not dom_result["success"]:
            print(f"❌ DOM extraction failed: {dom_result.get('error')}")
            return False
        
        dom_html = dom_result["dom_html"]
        self.current_dom_hash = dom_result["dom_hash"]
        
        print(f"✅ DOM extracted: {len(dom_html)} chars, hash: {self.current_dom_hash[:16]}...")
        
        # Generate initial steps with AI
        print("\n🤖 Generating test steps with AI...")
        steps = self.ai.generate_test_steps(
            dom_html=dom_html,
            test_cases=self.test_cases,
            test_context=self.test_context
        )
        
        if not steps:
            print("❌ Failed to generate steps")
            return False
        
        print(f"✅ Generated {len(steps)} steps")
        self._print_steps(steps)
        
        # Execute steps
        print("\n" + "="*70)
        print("⚙️ EXECUTING STEPS")
        print("="*70)
        
        executed_steps = []
        i = 0
        
        while i < len(steps):
            step = steps[i]
            step_num = i + 1
            
            print(f"\n[Step {step_num}/{len(steps)}] {step.get('action').upper()}: {step.get('description')}")
            
            # Execute step
            result = self.selenium.execute_step(step)
            
            if not result["success"]:
                print(f"❌ Step failed: {result.get('error')}")
                
                # Try failure recovery with AI
                print("\n🔧 Attempting failure recovery with AI...")
                
                # Wait a moment for page to settle
                time.sleep(1)
                
                # Extract current DOM
                fresh_dom_result = self.selenium.extract_form_dom_with_js()
                if not fresh_dom_result["success"]:
                    print("❌ Failed to extract DOM for recovery")
                    return False
                
                # Capture screenshot for AI vision
                screenshot_result = self.selenium.capture_screenshot(encode_base64=False)
                if not screenshot_result["success"]:
                    print("❌ Failed to capture screenshot for recovery")
                    return False
                
                # Save screenshot temporarily
                import tempfile
                screenshot_path = tempfile.mktemp(suffix='.png')
                with open(screenshot_path, 'wb') as f:
                    f.write(screenshot_result["screenshot"])
                
                # Ask AI to analyze failure and generate recovery steps
                recovery_steps = self.ai.analyze_failure_and_recover(
                    failed_step=step,
                    executed_steps=executed_steps,
                    fresh_dom=fresh_dom_result["dom_html"],
                    screenshot_path=screenshot_path,
                    test_cases=self.test_cases,
                    test_context=self.test_context,
                    attempt_number=1
                )
                
                # Clean up temp screenshot
                try:
                    import os
                    os.remove(screenshot_path)
                except:
                    pass
                
                if not recovery_steps:
                    print("❌ Failed to generate recovery steps")
                    return False
                
                print(f"✅ Generated {len(recovery_steps)} recovery steps")
                self._print_steps(recovery_steps)
                
                # Replace remaining steps with recovery steps
                steps = executed_steps + recovery_steps
                
                # Continue from current position (will execute recovery steps)
                i = len(executed_steps)
                continue
            
            print(f"✅ Step completed")
            executed_steps.append(step)
            
            # Small delay between steps
            time.sleep(0.5)
            
            # Check for alerts
            alert_info = self.selenium.check_for_alert()
            
            if alert_info["success"] and alert_info.get("alert_present"):
                print(f"\n⚠️ Alert detected: {alert_info['alert_type']}")
                print(f"   Text: {alert_info['alert_text']}")
                
                # Generate alert handling steps with AI
                print("\n🤖 Generating alert handling steps with AI...")
                
                alert_steps = self.ai.generate_alert_handling_steps(
                    alert_info=alert_info,
                    executed_steps=executed_steps,
                    screenshot_path=None,  # No screenshot for JS alerts
                    test_cases=self.test_cases,
                    test_context=self.test_context,
                    step_where_alert_appeared=len(executed_steps)
                )
                
                if not alert_steps:
                    print("❌ Failed to generate alert handling steps")
                    return False
                
                print(f"✅ Generated {len(alert_steps)} alert handling steps")
                self._print_steps(alert_steps)
                
                # Insert alert handling steps into main steps list (like original)
                # Update steps: executed + alert_steps
                steps = executed_steps + alert_steps
                
                # Continue from current position (will execute alert steps in main loop)
                i = len(executed_steps)
                continue
            
            # Check for DOM changes
            new_dom_result = self.selenium.extract_form_dom_with_js()
            
            if new_dom_result["success"]:
                new_dom_hash = new_dom_result["dom_hash"]
                
                if new_dom_hash != self.current_dom_hash:
                    print(f"\n🔄 DOM changed (hash: {new_dom_hash[:16]}...)")
                    print("   Regenerating remaining steps...")
                    
                    # Wait for page to stabilize
                    time.sleep(1.5)
                    
                    # Re-extract DOM
                    stable_dom = self.selenium.extract_form_dom_with_js()
                    
                    # Regenerate steps
                    new_steps = self.ai.regenerate_steps(
                        dom_html=stable_dom["dom_html"],
                        executed_steps=executed_steps,
                        test_cases=self.test_cases,
                        test_context=self.test_context
                    )
                    
                    if new_steps:
                        steps = executed_steps + new_steps
                        self.current_dom_hash = stable_dom["dom_hash"]
                        print(f"✅ Regenerated {len(new_steps)} new steps")
                        self._print_steps(new_steps)
            
            i += 1
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED")
        print(f"   Total steps executed: {len(executed_steps)}")
        print("="*70)
        
        return True
    
    def _print_steps(self, steps: List[Dict]):
        """Print steps in readable format"""
        print("\n" + "-"*70)
        for i, step in enumerate(steps, 1):
            action = step.get('action', 'unknown').upper()
            desc = step.get('description', 'No description')
            print(f"  [{i}] {action}: {desc}")
            
            selector = step.get('selector')
            if selector:
                print(f"      Selector: {selector}")
            
            value = step.get('value')
            if value:
                print(f"      Value: {value}")
        print("-"*70)


class TestContext:
    """Test context for tracking form state"""
    
    def __init__(self):
        self.filled_fields = {}
        self.clicked_elements = []
        self.selected_options = {}
        self.credentials = {}
        
        # Registration tracking
        self.registered_name = None
        self.registered_email = None
        self.registered_password = None
    
    def add_filled_field(self, selector: str, value: str):
        self.filled_fields[selector] = value
    
    def add_clicked_element(self, selector: str):
        self.clicked_elements.append(selector)
    
    def add_selected_option(self, selector: str, value: str):
        self.selected_options[selector] = value
    
    def has_credentials(self):
        """Check if credentials are stored"""
        return bool(self.credentials)
    
    def get_credentials(self):
        """Get stored credentials"""
        return self.credentials
    
    def set_credentials(self, username: str, password: str):
        """Store credentials"""
        self.credentials = {"username": username, "password": password}
    
    def set_registered_user(self, name: str, email: str, password: str):
        """Store registered user info"""
        self.registered_name = name
        self.registered_email = email
        self.registered_password = password


def main():
    """Main entry point for local testing"""
    
    # Get API key from environment (same as original code)
    API_KEY = os.environ.get("ANTHROPIC_API_KEY")
    
    if not API_KEY:
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment")
        print("Please set it: export ANTHROPIC_API_KEY='your-key-here'")
        return
    
    # Configuration
    config = {
        "anthropic_api_key": API_KEY,  # ← From environment variable
        "test_url": "http://localhost:8000/index.html",
        "test_cases_file": "generic_form_page_crawler_test_cases.json",
        "browser": "chrome",  # chrome, firefox, edge
        "headless": False
    }
    
    print("="*70)
    print("🚀 LOCAL TEST MODE")
    print("="*70)
    print(f"URL: {config['test_url']}")
    print(f"Browser: {config['browser']}")
    print(f"Headless: {config['headless']}")
    print("="*70)
    
    # Create orchestrator
    orchestrator = LocalTestOrchestrator(
        anthropic_api_key=config["anthropic_api_key"],
        test_cases_file=config["test_cases_file"],
        browser=config["browser"],
        headless=config["headless"]
    )
    
    # Run test
    success = orchestrator.run_test(config["test_url"])
    
    if success:
        print("\n✅ TEST PASSED")
    else:
        print("\n❌ TEST FAILED")


if __name__ == "__main__":
    main()
