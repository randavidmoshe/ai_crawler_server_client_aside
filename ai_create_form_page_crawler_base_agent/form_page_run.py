# form_page_run.py
# Execute form page stages from JSON file

import sys
import os
import json
from agent_selenium import AgentSelenium


class FormPageRunner:
    """Execute test stages from JSON file"""
    
    def __init__(self, browser: str = "chrome", headless: bool = False):
        self.selenium = AgentSelenium()
        self.browser = browser
        self.headless = headless
    
    def run_stages_from_file(self, json_file_path: str, url: str) -> bool:
        """
        Run stages from JSON file
        
        Args:
            json_file_path: Path to stages JSON file
            url: Starting URL
            
        Returns:
            True if all stages executed successfully, False otherwise
        """
        # Load stages from JSON
        if not os.path.exists(json_file_path):
            print(f"❌ JSON file not found: {json_file_path}")
            return False
        
        with open(json_file_path, 'r') as f:
            stages = json.load(f)
        
        print(f"📋 Loaded {len(stages)} stages from {json_file_path}")
        
        # Initialize browser
        print(f"\n🌐 Initializing browser ({self.browser}, headless={self.headless})...")
        result = self.selenium.initialize_browser(
            browser_type=self.browser,
            headless=self.headless
        )
        
        if not result["success"]:
            print(f"❌ Failed to initialize browser: {result.get('error')}")
            return False
        
        print(f"✅ Browser initialized")
        
        # Navigate to URL
        print(f"\n🌐 Navigating to {url}...")
        result = self.selenium.navigate_to_url(url)
        
        if not result["success"]:
            print(f"❌ Navigation failed: {result.get('error')}")
            self.selenium.close_browser()
            return False
        
        print(f"✅ Navigated to: {result['url']}")
        
        # Execute stages
        print(f"\n⚙️ EXECUTING {len(stages)} STAGES")
        print("="*70)
        
        for i, stage in enumerate(stages, 1):
            step_number = stage.get('step_number', i)
            action = stage.get('action', 'unknown')
            description = stage.get('description', 'No description')
            test_case = stage.get('test_case', '')
            
            print(f"\n[Step {step_number}/{len(stages)}] {action.upper()}: {description}")
            if test_case:
                print(f"   Test Case: {test_case}")
            
            # Execute step
            result = self.selenium.execute_step(stage)
            
            if not result.get("success"):
                print(f"❌ Step failed: {result.get('error', 'Unknown error')}")
                self.selenium.close_browser()
                return False
            
            print(f"✅ Step completed")
        
        print("\n" + "="*70)
        print("✅ ALL STAGES COMPLETED SUCCESSFULLY")
        
        # Close browser
        print("\n🔒 Closing browser...")
        self.selenium.close_browser()
        print("✅ Browser closed")
        
        return True


def main():
    """Main entry point"""
    
    # Configuration
    config = {
        "browser": "chrome",  # chrome, firefox, edge
        "headless": False,
        "url": "http://localhost:8000/test-form.html",
        "json_file": "/home/ranlaser/automation_product_config/ai_projects/local_web_site/form_pages_discovery/person/create_view_stages/create_verify_person.json"
    }
    
    print("="*70)
    print("🚀 FORM PAGE RUNNER")
    print("="*70)
    print(f"Browser: {config['browser']}")
    print(f"Headless: {config['headless']}")
    print(f"URL: {config['url']}")
    print(f"JSON: {config['json_file']}")
    print("="*70)
    
    # Create runner
    runner = FormPageRunner(
        browser=config["browser"],
        headless=config["headless"]
    )
    
    # Run stages
    success = runner.run_stages_from_file(
        json_file_path=config["json_file"],
        url=config["url"]
    )
    
    if success:
        print("\n✅ TEST PASSED")
    else:
        print("\n❌ TEST FAILED")


if __name__ == "__main__":
    main()
