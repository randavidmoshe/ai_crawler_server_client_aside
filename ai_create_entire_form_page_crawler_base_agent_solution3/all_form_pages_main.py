# form_page_main.py
# LOCAL TESTING MODE
# Run everything on one machine for testing/development

import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../agent'))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../server'))

from agent_selenium import AgentSelenium
from ai_all_form_pages_main_prompter import AIHelper
from ai_form_page_alert_recovery_prompter import AIErrorRecovery
from ai_form_page_end_prompter import AIFormPageEndPrompter
import time
import json
import hashlib
from typing import List, Dict, Optional

import logging
logger = logging.getLogger('init_logger.main_from_page')
result_logger_gui = logging.getLogger('init_result_logger_gui.main_from_page')

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
        headless: bool = False,
        screenshot_folder: Optional[str] = None,
        enable_ui_verification: bool = False,
        form_page_name: Optional[str] = None,
        max_retries: int = 2,
        use_detect_fields_change: bool = True,
        url_for_login: Optional[str] = None,
        username_for_login: Optional[str] = None,
        password_for_login: Optional[str] = None,
        project_name: Optional[str] = None
    ):
        # Initialize Selenium (from agent code) with screenshot folder
        self.selenium = AgentSelenium(screenshot_folder=screenshot_folder)
        
        # Initialize AI helper (server code)
        self.ai = AIHelper(api_key=anthropic_api_key)
        
        # Initialize AI error recovery (for alert handling)
        self.ai_error_recovery = AIErrorRecovery(api_key=anthropic_api_key)
        
        # Initialize AI form page end prompter (for assigning test_case to stages)
        self.ai_end_prompter = AIFormPageEndPrompter(api_key=anthropic_api_key)
        
        # Configuration
        self.browser = browser
        self.headless = headless
        self.enable_ui_verification = enable_ui_verification
        self.form_page_name = form_page_name
        self.max_retries = max_retries
        self.use_detect_fields_change = use_detect_fields_change
        self.url_for_login = url_for_login
        self.username_for_login = username_for_login
        self.password_for_login = password_for_login
        self.project_name = project_name
        
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
        self.base_url = None  # Will be set when test starts
        self.critical_fields_checklist = None  # For Scenario B alert recovery
        
        # Create screenshots folder for AI screenshots
        import getpass
        username = getpass.getuser()
        self.ai_screenshots_folder = f"/home/{username}/automation_product_config/ai_projects/{self.project_name}/screenshots"
        os.makedirs(self.ai_screenshots_folder, exist_ok=True)
        print(f"📁 AI Screenshots folder: {self.ai_screenshots_folder}")
        
        print(f"✅ Local orchestrator initialized")
        print(f"   Browser: {browser}")
        print(f"   Headless: {headless}")
        print(f"   UI Verification: {'ENABLED' if enable_ui_verification else 'DISABLED'}")
        print(f"   Detect Fields Change: {'ENABLED' if use_detect_fields_change else 'DISABLED'}")
        print(f"   Test cases: {len(self.test_cases)}")
    
    def _save_ai_screenshot(self, screenshot_base64: str, description: str) -> str:
        """
        Save screenshot that's being sent to AI with timestamp
        
        Args:
            screenshot_base64: Base64 encoded screenshot
            description: Description for filename
            
        Returns:
            Path to saved screenshot file
        """
        from datetime import datetime
        import base64
        
        # Generate filename with timestamp including seconds
        timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
        filename = f"{description}_{timestamp}.png"
        filepath = os.path.join(self.ai_screenshots_folder, filename)
        
        # Decode and save
        screenshot_bytes = base64.b64decode(screenshot_base64)
        with open(filepath, 'wb') as f:
            f.write(screenshot_bytes)
        
        return filepath
    
    def _save_steps_to_file(self, steps: List[Dict]):
        """
        Save generated steps to JSON file in automation_product_config directory
        
        Args:
            steps: List of test steps to save
        """
        if not self.form_page_name:
            raise ValueError("FORM_PAGE_NAME parameter is required but was not provided")
        
        # Call AI to assign test_case to each step
        print("\n🤖 Assigning test cases to stages with AI...")
        updated_steps = self.ai_end_prompter.assign_test_cases(steps, self.test_cases)
        print(f"✅ Test cases assigned to {len(updated_steps)} stages")
        
        import getpass
        username = getpass.getuser()
        
        base_path = f"/home/{username}/automation_product_config/ai_projects/local_web_site/form_pages_discovery/{self.form_page_name}/create_view_stages"
        
        os.makedirs(base_path, exist_ok=True)
        
        filename = f"create_verify_{self.form_page_name}.json"
        filepath = os.path.join(base_path, filename)
        
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(updated_steps, f, indent=2, ensure_ascii=False)
        
        print(f"\n💾 Steps saved to: {filepath}")
    
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
            
            # Handle login if credentials provided
            if self.url_for_login:
                print(f"\n🔐 Performing login...")
                print(f"   Login URL: {self.url_for_login}")
                
                # Navigate to login page
                login_result = self.selenium.navigate_to_url(self.url_for_login)
                if not login_result["success"]:
                    print(f"❌ Failed to navigate to login page: {login_result.get('error')}")
                    return False
                
                print(f"✅ Navigated to login page")
                
                # Wait for page to load
                time.sleep(2)
                
                # Extract DOM from login page
                print("📄 Extracting login page DOM...")
                dom_result = self.selenium.extract_form_dom_with_js()
                if not dom_result["success"]:
                    print(f"❌ Failed to extract login page DOM: {dom_result.get('error')}")
                    return False
                
                # Capture screenshot of login page
                print("📸 Capturing login page screenshot...")
                screenshot_result = self.selenium.capture_screenshot(
                    scenario_description="login_page",
                    encode_base64=True,
                    save_to_folder=False
                )
                
                if not screenshot_result["success"]:
                    print(f"❌ Failed to capture login page screenshot: {screenshot_result.get('error')}")
                    return False
                
                screenshot_base64 = screenshot_result["screenshot"]
                
                # Save screenshot for AI analysis
                saved_path = self._save_ai_screenshot(screenshot_base64, "login_page")
                print(f"💾 AI screenshot saved: {saved_path}")
                
                # Ask AI to discover login fields and generate login steps
                print("🤖 Using AI to discover login fields...")
                
                login_steps = self.ai.discover_login_fields(
                    dom_html=dom_result["dom_html"],
                    screenshot_base64=screenshot_base64
                )
                
                if not login_steps or len(login_steps) != 3:
                    print(f"❌ Expected 3 login steps, got {len(login_steps)}")
                    return False
                
                print(f"✅ AI discovered login fields: {len(login_steps)} steps")
                
                # Create account folder and save login steps
                import getpass
                username = getpass.getuser()
                account_folder = f"/home/{username}/automation_product_config/ai_projects/{self.project_name}/account"
                os.makedirs(account_folder, exist_ok=True)
                print(f"📁 Created account folder: {account_folder}")
                
                # Save login steps to JSON
                login_steps_path = os.path.join(account_folder, "login_steps.json")
                with open(login_steps_path, 'w', encoding='utf-8') as f:
                    json.dump(login_steps, f, indent=2, ensure_ascii=False)
                print(f"💾 Saved login steps to: {login_steps_path}")
                
                # Execute login steps with actual credentials
                print("🔐 Executing login steps...")
                for step in login_steps:
                    # Replace placeholders with actual credentials
                    if step.get("value") == "{{USERNAME}}":
                        step["value"] = self.username_for_login
                    elif step.get("value") == "{{PASSWORD}}":
                        step["value"] = self.password_for_login
                    
                    result = self.selenium.execute_step(step)
                    if not result["success"]:
                        print(f"❌ Login step failed: {step.get('description')} - {result.get('error')}")
                        return False
                    
                    print(f"✅ {step.get('description')}")
                
                print(f"✅ Login completed")
                
                # Wait for redirect to dashboard
                time.sleep(3)
                
                # Get current URL after login
                current_url = self.selenium.driver.current_url
                print(f"✅ After login, landed on: {current_url}")
                
                # Store base URL
                self.base_url = current_url
                
                # Test from current page (dashboard)
                return self.run_test_from_current_page()
            
            # Log test configuration to both logs
            config = {
                "test_url": url,
                "form_page_name": self.form_page_name,
                "browser": self.browser,
                "headless": self.headless,
                "enable_ui_verification": self.enable_ui_verification,
                "screenshot_folder": self.selenium.screenshots_path,
                "test_cases_file": "test_cases1.json",
                "max_retries": self.max_retries
            }
            self.selenium.log_test_start(config)
            
            # Navigate to URL
            print(f"\n🌐 Navigating to {url}...")
            result = self.selenium.navigate_to_url(url)
            
            if not result["success"]:
                print(f"❌ Navigation failed: {result.get('error')}")
                return False
            
            print(f"✅ Navigated to: {result['url']}")
            
            # Store base URL for potential alert recovery
            self.base_url = result['url']
            
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
        
        # Generate initial steps with AI (with screenshot ONLY if enabled)
        print("\n🤖 Generating test steps with AI...")
        
        # Conditionally capture screenshot based on enable_ui_verification
        screenshot_base64 = None
        if self.enable_ui_verification:
            print("📸 Capturing screenshot for UI verification...")
            
            # Capture screenshot (base64, not saved to folder)
            screenshot_result = self.selenium.capture_screenshot(
                scenario_description="initial_ui_check",
                encode_base64=True,
                save_to_folder=False
            )
            
            if not screenshot_result["success"]:
                print(f"⚠️  Failed to capture screenshot: {screenshot_result.get('error')}")
                screenshot_base64 = None
            else:
                screenshot_base64 = screenshot_result["screenshot"]
                print("✅ Screenshot captured for AI analysis")
                
                # Save screenshot for AI analysis
                saved_path = self._save_ai_screenshot(screenshot_base64, "initial_page")
                print(f"💾 AI screenshot saved: {saved_path}")
        else:
            print("ℹ️  UI verification disabled - skipping screenshot")
        
        # Generate exploration steps
        result = self.ai.generate_exploration_steps(
            dom_html=dom_html,
            executed_steps=[],
            screenshot_base64=screenshot_base64,
            already_cataloged_pages=[]
        )
        
        steps = result.get("steps", [])
        ui_issue = result.get("ui_issue", "")
        
        if not steps:
            print("❌ Failed to generate steps")
            return False
        
        print(f"✅ Generated {len(steps)} steps")
        
        all_generated_steps = list(steps)
        
        # Handle UI issue if detected (only if UI verification is enabled)
        if self.enable_ui_verification and ui_issue:
            print(f"\n⚠️  UI ISSUE DETECTED: {ui_issue}")
            
            # Add to reported issues list (split by comma to handle multiple issues)
            for issue in ui_issue.split(','):
                issue = issue.strip()
                if issue and issue not in self.test_context.reported_ui_issues:
                    self.test_context.reported_ui_issues.append(issue)
            
            # Log to both loggers
            import logging
            logger = logging.getLogger('init_logger.form_page_test')
            result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')
            
            logger.warning(f"UI Issue detected: {ui_issue}")
            result_logger_gui.warning(f"UI Issue detected: {ui_issue}")
            
            # Log to agent loggers
            self.selenium.log_message(f"⚠️ UI ISSUE DETECTED: {ui_issue}", level="warning")
            
            # Capture and save screenshot to folder
            ui_screenshot_result = self.selenium.capture_screenshot(
                scenario_description="ui_issue",
                encode_base64=False,
                save_to_folder=True
            )
            
            if ui_screenshot_result["success"]:
                print(f"📸 UI issue screenshot saved: {ui_screenshot_result['filename']}")
                # Log screenshot filename to agent
                self.selenium.log_message(f"📸 UI issue screenshot saved: {ui_screenshot_result['filename']}", level="info")
            
            print("⚠️  Continuing test despite UI issue...\n")
        
        self._print_steps(steps)
        
        # Execute steps
        print("\n" + "="*70)
        print("⚙️ EXECUTING STEPS")
        print("="*70)
        
        executed_steps = []
        consecutive_failures = 0
        i = 0
        
        while i < len(steps):
            step = steps[i]
            step_num = i + 1
            
            print(f"\n[Step {step_num}/{len(steps)}] {step.get('action').upper()}: {step.get('description')}")
            
            # Execute step - NOW RETURNS EVERYTHING IN ONE CALL
            result = self.selenium.execute_step(step)
            
            # Get old DOM hash from result
            old_dom_hash = result.get("old_dom_hash", self.current_dom_hash)
            
            if not result["success"]:
                print(f"❌ Step failed: {result.get('error')}")
                
                # Check if this is a verification failure
                is_verification_failure = (step.get('action') == 'verify' and result.get('action') == 'verify')
                
                if is_verification_failure:
                    # For verification failures, just log and move to next step immediately (no AI recovery)
                    print(f"⚠️  Verification failed. Moving to next step...")
                    consecutive_failures = 0  # Reset counter
                    executed_steps.append(step)  # Add failed verification step to executed_steps
                    i += 1
                    continue
                else:
                    # For non-verification failures, use normal retry logic
                    consecutive_failures += 1
                    print(f"⚠️  Consecutive failures: {consecutive_failures}/{self.max_retries}")
                    
                    # Check if we've hit the max consecutive failures
                    if consecutive_failures >= self.max_retries:
                        print(f"\n❌ TERMINATING: Reached maximum consecutive failures ({self.max_retries})")
                        print(f"   Last failed step: {step.get('description')}")
                        return False
                
                # Try failure recovery with AI
                print("\n🔧 Attempting failure recovery with AI...")
                
                # Wait a moment for page to settle
                time.sleep(1)
                
                # Extract current DOM
                fresh_dom_result = self.selenium.extract_form_dom_with_js()
                if not fresh_dom_result["success"]:
                    print("❌ Failed to extract DOM for recovery")
                    return False
                
                # Capture screenshot with descriptive scenario
                step_description = step.get('description', 'unknown_step')
                screenshot_result = self.selenium.capture_screenshot(
                    scenario_description=f"error_{step_description}",
                    encode_base64=False
                )
                
                if not screenshot_result["success"]:
                    print("❌ Failed to capture screenshot for recovery")
                    return False
                
                screenshot_path = screenshot_result["filepath"]
                print(f"📸 Screenshot saved: {screenshot_result['filename']}")
                
                # Ask AI to analyze failure and generate recovery steps
                recovery_steps = self.ai.analyze_failure_and_recover(
                    failed_step=step,
                    executed_steps=executed_steps,
                    fresh_dom=fresh_dom_result["dom_html"],
                    screenshot_path=screenshot_path,
                    test_cases=self.test_cases,
                    test_context=self.test_context,
                    attempt_number=consecutive_failures
                )
                
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
            
            # Step succeeded - reset consecutive failure counter
            consecutive_failures = 0
            print(f"✅ Step completed")
            executed_steps.append(step)
            
            # Check if this step has form_page_info
            if step.get("form_page_info"):
                form_page_info = step["form_page_info"]
                form_name = form_page_info.get("form_name", "unknown_form")
                
                print(f"\n✅ FORM PAGE DETECTED: {form_name}")
                print(f"   Navigation Path: {form_page_info.get('navigation_path', 'N/A')}")
                
                # Print parent fields if detected
                parent_fields = form_page_info.get("parent_fields", [])
                if parent_fields:
                    print(f"   Parent References: {len(parent_fields)}")
                    for pf in parent_fields:
                        print(f"      - {pf.get('field_name')} → {pf.get('parent_entity')} (via {pf.get('identified_by')})")
                
                # Create folder for this form page
                import getpass
                username = getpass.getuser()
                form_folder = f"/home/{username}/automation_product_config/ai_projects/{self.project_name}/{form_name}"
                os.makedirs(form_folder, exist_ok=True)
                print(f"📁 Created folder: {form_folder}")
                
                # Save navigation steps to JSON file
                navigation_steps = form_page_info.get("navigation_steps", [])
                if navigation_steps:
                    nav_file_path = os.path.join(form_folder, "navigation_steps.json")
                    with open(nav_file_path, 'w', encoding='utf-8') as f:
                        json.dump(navigation_steps, f, indent=2, ensure_ascii=False)
                    print(f"💾 Saved navigation steps to: {nav_file_path}")
            
            # Small delay between steps
            time.sleep(0.5)
            
            # Check for alerts - NOW FROM RESULT
            if result.get("alert_present"):
                alert_type = result.get("alert_type", "alert")
                alert_text = result.get("alert_text", "")
                
                print(f"\n⚠️ Alert detected: {alert_type}")
                print(f"   Text: {alert_text}")
                
                # Create alert_info dict for compatibility with existing code
                alert_info = {
                    "success": True,
                    "alert_present": True,
                    "alert_type": alert_type,
                    "alert_text": alert_text
                }
                
                # Alert already accepted by agent
                print("ℹ️  Alert was already accepted by agent")
                
                # Small delay for page to stabilize after alert
                time.sleep(0.5)
                
                # ADD ACCEPT_ALERT STEP TO EXECUTED_STEPS (as documentation)
                accept_alert_step = {
                    "step_number": len(executed_steps) + 1,
                    "action": "accept_alert",
                    "selector": "",
                    "value": "",
                    "description": f"Accept {alert_type} alert: {alert_text[:50]}..."
                }
                executed_steps.append(accept_alert_step)
                print(f"📝 Added accept_alert step to executed_steps (step {len(executed_steps)})")
                
                # EXTRACT FRESH DOM (now that alert is gone)
                print("📄 Extracting DOM after alert...")
                fresh_dom_result = self.selenium.extract_form_dom_with_js()
                
                if not fresh_dom_result["success"]:
                    print(f"❌ Failed to extract DOM after alert: {fresh_dom_result.get('error')}")
                    return False
                
                fresh_dom_html = fresh_dom_result["dom_html"]
                print(f"✅ DOM extracted: {len(fresh_dom_html)} chars")
                
                # Generate alert handling steps with AI
                print("\n🤖 Generating alert recovery steps with AI...")
                
                alert_response = self.ai_error_recovery.regenerate_steps_after_alert(
                    alert_info=alert_info,
                    executed_steps=executed_steps,
                    dom_html=fresh_dom_html,
                    screenshot_path=None,  # No screenshot for JS alerts
                    test_cases=self.test_cases,
                    test_context=self.test_context,
                    step_where_alert_appeared=len(executed_steps),
                    include_accept_step=False  # NEW: Don't tell AI to include accept_alert
                )
                
                if not alert_response:
                    print("❌ Failed to generate alert handling steps")
                    return False
                
                # Extract scenario from response
                scenario = alert_response.get("scenario", "B")
                
                # Check if Scenario B with real_issue
                if scenario == "B" and alert_response.get("issue_type") == "real_issue":
                    # Real system bug detected
                    print("\n" + "="*70)
                    print("🔴 REAL ISSUE DETECTED - System Bug")
                    print("="*70)
                    explanation = alert_response.get("explanation", "")
                    problematic_field = alert_response.get("problematic_field_claimed", "")
                    our_action = alert_response.get("our_action", "")
                    
                    print(f"📋 Alert Text: {alert_text}")
                    print(f"💡 Explanation: {explanation}")
                    print(f"⚠️  Problematic Field: {problematic_field}")
                    print(f"✅ Our Action: {our_action}")
                    
                    # Log error to agent with check_traffic flag
                    error_msg = f"[REAL_ISSUE] {explanation} - Alert: {alert_text} - check_traffic"
                    logger.error(error_msg)
                    result_logger_gui.error(error_msg)
                    
                    print("\n🛑 Exiting peacefully - This is a system issue, not a test failure")
                    print("="*70)
                    
                    # Return with system_issue status
                    return {"status": "system_issue", "explanation": explanation, 
                            "alert_text": alert_text, "problematic_field": problematic_field}
                
                # Get steps
                alert_steps = alert_response.get("steps", [])
                
                if not alert_steps:
                    print("❌ Failed to generate alert handling steps")
                    return False

                # Extract scenario and steps from response
                scenario = alert_response.get("scenario", "B")
                alert_steps = alert_response.get("steps", [])
                
                print(f"✅ Generated {len(alert_steps)} alert handling steps")
                print(f"📋 Detected Scenario: {scenario}")
                self._print_steps(alert_steps)
                
                # Determine where to start executing based on scenario
                # Case A: Simple alert (append steps and continue normally)
                # Case B: Validation error (navigate back and start fresh)
                
                if scenario == "A":
                    # Case A: Append new steps after executed steps (including accept_alert)
                    print(f"📋 Case A: Appending steps after step {len(executed_steps)}")
                    steps = executed_steps + alert_steps
                    # No need for +1, just continue normally like DOM regeneration
                    i = len(executed_steps)  # Continue from next position
                else:
                    # Case B: Validation error
                    issue_type = alert_response.get("issue_type", "ai_issue")
                    print(f"📋 Case B ({issue_type}): Using complete new step list (smart recovery)")
                    
                    # Get problematic fields from AI response (includes alert + DOM + screenshot analysis)
                    problematic_fields_list = alert_response.get("problematic_fields", [])
                    
                    if problematic_fields_list:
                        # Convert list to dict format for critical_fields_checklist
                        # All fields from AI are marked as "MUST FILL" since they had errors
                        critical_fields = {field: "MUST FILL" for field in problematic_fields_list}
                        self.critical_fields_checklist = critical_fields
                        print(f"⚠️  CRITICAL FIELDS CHECKLIST created with {len(critical_fields)} fields:")
                        for field_name, issue_type in critical_fields.items():
                            print(f"   - {field_name}: {issue_type}")
                    else:
                        # Fallback: parse from alert text if AI didn't provide list
                        print(f"⚠️  No problematic_fields from AI, falling back to alert text parsing")
                        critical_fields = self._parse_critical_fields_from_alert(alert_text)
                        if critical_fields:
                            self.critical_fields_checklist = critical_fields
                            print(f"⚠️  CRITICAL FIELDS CHECKLIST created with {len(critical_fields)} fields:")
                            for field_name, issue_type in critical_fields.items():
                                print(f"   - {field_name}: {issue_type}")
                        else:
                            print(f"⚠️  Could not identify critical fields")
                            self.critical_fields_checklist = None
                    
                    print(f"🔄 Navigating back to base URL for fresh start...")
                    
                    # Navigate back to base URL
                    if self.base_url:
                        navigate_result = self.selenium.navigate_to_url(self.base_url)
                        if not navigate_result["success"]:
                            print(f"❌ Failed to navigate back to base URL: {navigate_result.get('error')}")
                            return False
                        print(f"✅ Navigated back to: {self.base_url}")
                        
                        # Wait for page to load
                        time.sleep(2)
                    else:
                        print("⚠️  No base URL stored, continuing from current page")
                    
                    # Use complete new step list
                    steps = alert_steps
                    executed_steps = []  # Reset executed steps since we're starting fresh
                    
                    # Start from the very beginning (step 1)
                    i = 0
                    print(f"▶️  Starting fresh from step 1 (executing all {len(steps)} steps)")
                
                continue
            
            # Check for DOM changes - NOW FROM RESULT
            new_dom_hash = result.get("new_dom_hash")
            
            if new_dom_hash and new_dom_hash != self.current_dom_hash:
                print(f"\n🔄 DOM changed (hash: {new_dom_hash[:16]}...)")
                print("   Regenerating remaining steps...")
                
                # Wait for page to stabilize
                time.sleep(1.5)
                
                # Re-extract DOM
                stable_dom = self.selenium.extract_form_dom_with_js()
                
                # Check for validation errors in the new DOM
                validation_errors = self._detect_validation_errors_from_dom(stable_dom["dom_html"])
                
                if validation_errors["has_errors"]:
                    print(f"\n⚠️  VALIDATION ERRORS DETECTED in DOM!")
                    print(f"   Error fields: {len(validation_errors['error_fields'])}")
                    print(f"   Error messages: {len(validation_errors['error_messages'])}")
                    
                    # Capture screenshot
                    print("📸 Capturing screenshot for validation error analysis...")
                    screenshot_result = self.selenium.capture_screenshot(
                        scenario_description="validation_error",
                        encode_base64=False,
                        save_to_folder=True
                    )
                    
                    if not screenshot_result["success"]:
                        print(f"❌ Failed to capture screenshot for validation errors")
                        return False
                    
                    screenshot_path = screenshot_result["filepath"]
                    print(f"📸 Screenshot saved: {screenshot_result['filename']}")
                    
                    # Build validation info similar to alert_info
                    validation_info = {
                        "success": True,
                        "alert_present": False,  # Not a real alert, but validation error
                        "alert_type": "validation_error",
                        "alert_text": f"Validation errors found: {', '.join(validation_errors['error_messages'][:3])}"  # First 3 messages
                    }
                    
                    # Build additional context for AI
                    gathered_info = {
                        "error_fields": validation_errors["error_fields"],
                        "error_messages": validation_errors["error_messages"]
                    }
                    
                    print("\n🤖 Generating validation error recovery steps with AI...")
                    print(f"   Gathered error fields: {gathered_info['error_fields']}")
                    print(f"   Gathered error messages: {gathered_info['error_messages']}")
                    
                    # Call AI with validation error info (reuse alert handling)
                    alert_response = self.ai_error_recovery.regenerate_steps_after_alert(
                        alert_info=validation_info,
                        executed_steps=executed_steps,
                        dom_html=stable_dom["dom_html"],
                        screenshot_path=screenshot_path,
                        test_cases=self.test_cases,
                        test_context=self.test_context,
                        step_where_alert_appeared=len(executed_steps),
                        include_accept_step=False,
                        gathered_error_info=gathered_info  # NEW: Pass gathered info
                    )
                    
                    if not alert_response:
                        print("❌ Failed to generate validation error recovery steps")
                        return False
                    
                    # Extract scenario from response
                    scenario = alert_response.get("scenario", "B")
                    
                    # Check if Scenario B with real_issue
                    if scenario == "B" and alert_response.get("issue_type") == "real_issue":
                        # Real system bug detected
                        print("\n" + "="*70)
                        print("🔴 REAL ISSUE DETECTED - System Bug (Validation Error)")
                        print("="*70)
                        explanation = alert_response.get("explanation", "")
                        problematic_field = alert_response.get("problematic_field_claimed", "")
                        our_action = alert_response.get("our_action", "")
                        
                        print(f"📋 Validation Info: {validation_info.get('alert_text', '')}")
                        print(f"💡 Explanation: {explanation}")
                        print(f"⚠️  Problematic Field: {problematic_field}")
                        print(f"✅ Our Action: {our_action}")
                        
                        # Log error to agent with check_traffic flag
                        error_msg = f"[REAL_ISSUE] {explanation} - Validation: {validation_info.get('alert_text', '')} - check_traffic"
                        logger.error(error_msg)
                        result_logger_gui.error(error_msg)
                        
                        print("\n🛑 Exiting peacefully - This is a system issue, not a test failure")
                        print("="*70)
                        
                        # Return with system_issue status
                        return {"status": "system_issue", "explanation": explanation, 
                                "validation_info": validation_info, "problematic_field": problematic_field}
                    
                    # Get steps
                    alert_steps = alert_response.get("steps", [])
                    
                    if not alert_steps:
                        print("❌ Failed to generate validation error recovery steps")
                        return False
                    
                    # Extract scenario and steps from response
                    scenario = alert_response.get("scenario", "B")
                    alert_steps = alert_response.get("steps", [])
                    
                    print(f"✅ Generated {len(alert_steps)} validation error recovery steps")
                    print(f"📋 Detected Scenario: {scenario}")
                    self._print_steps(alert_steps)
                    
                    # Should be Scenario B (validation error)
                    if scenario == "B":
                        issue_type = alert_response.get("issue_type", "ai_issue")
                        print(f"📋 Case B ({issue_type}): Using complete new step list (validation error recovery)")
                        
                        # Get problematic fields from AI response
                        problematic_fields_list = alert_response.get("problematic_fields", [])
                        
                        if problematic_fields_list:
                            critical_fields = {field: "MUST FILL" for field in problematic_fields_list}
                            self.critical_fields_checklist = critical_fields
                            print(f"⚠️  CRITICAL FIELDS CHECKLIST created with {len(critical_fields)} fields:")
                            for field_name, issue_type in critical_fields.items():
                                print(f"   - {field_name}: {issue_type}")
                        
                        # Navigate back to base URL
                        print(f"🔄 Navigating back to base URL for fresh start...")
                        if self.base_url:
                            navigate_result = self.selenium.navigate_to_url(self.base_url)
                            if not navigate_result["success"]:
                                print(f"❌ Failed to navigate back to base URL: {navigate_result.get('error')}")
                                return False
                            print(f"✅ Navigated back to: {self.base_url}")
                            time.sleep(2)
                        
                        # Use complete new step list
                        steps = alert_steps
                        executed_steps = []
                        i = 0
                        print(f"▶️  Starting fresh from step 1 (executing all {len(steps)} steps)")
                        continue
                    else:
                        print(f"⚠️  Unexpected scenario {scenario} for validation errors, treating as DOM change")
                
                # No validation errors or Scenario A - continue with normal regeneration
                # Capture screenshot for UI verification (base64, not saved) ONLY if enabled
                screenshot_base64 = None
                if self.enable_ui_verification:
                    print("📸 Capturing screenshot for UI verification...")
                    screenshot_result = self.selenium.capture_screenshot(
                        scenario_description="dom_change_ui_check",
                        encode_base64=True,
                        save_to_folder=False
                    )
                    
                    if not screenshot_result["success"]:
                        print(f"⚠️  Failed to capture screenshot: {screenshot_result.get('error')}")
                        screenshot_base64 = None
                    else:
                        screenshot_base64 = screenshot_result["screenshot"]
                        print("✅ Screenshot captured for AI analysis")
                        
                        # Save screenshot for AI analysis
                        saved_path = self._save_ai_screenshot(screenshot_base64, "dom_change")
                        print(f"💾 AI screenshot saved: {saved_path}")
                else:
                    print("ℹ️  UI verification disabled - skipping screenshot")
                
                # Check if fields changed (if feature is enabled)
                if self.use_detect_fields_change:
                    fields_changed = result.get("fields_changed", True)
                    
                    if not fields_changed:
                        print("ℹ️  Fields did not change - skipping AI regeneration")
                        i += 1
                        continue
                    else:
                        print("✅ Fields changed - proceeding with AI regeneration")
                
                # Regenerate exploration steps
                result = self.ai.generate_exploration_steps(
                    dom_html=stable_dom["dom_html"],
                    executed_steps=executed_steps,
                    screenshot_base64=screenshot_base64,
                    already_cataloged_pages=[]
                )
                
                new_steps = result.get("steps", [])
                ui_issue = result.get("ui_issue", "")
                
                if new_steps:
                    steps = executed_steps + new_steps
                    all_generated_steps.extend(new_steps)
                    self.current_dom_hash = stable_dom["dom_hash"]
                    print(f"✅ Regenerated {len(new_steps)} new steps")
                    
                    # Handle UI issue if detected (only if UI verification is enabled)
                    if self.enable_ui_verification and ui_issue:
                        print(f"\n⚠️  UI ISSUE DETECTED: {ui_issue}")
                        
                        # Add to reported issues list (split by comma to handle multiple issues)
                        for issue in ui_issue.split(','):
                            issue = issue.strip()
                            if issue and issue not in self.test_context.reported_ui_issues:
                                self.test_context.reported_ui_issues.append(issue)
                        
                        # Log to both loggers
                        import logging
                        logger = logging.getLogger('init_logger.form_page_test')
                        result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')
                        
                        logger.warning(f"UI Issue detected after DOM change: {ui_issue}")
                        result_logger_gui.warning(f"UI Issue detected after DOM change: {ui_issue}")
                        
                        # Log to agent loggers
                        self.selenium.log_message(f"⚠️ UI ISSUE DETECTED (after DOM change): {ui_issue}", level="warning")
                        
                        # Capture and save screenshot to folder
                        ui_screenshot_result = self.selenium.capture_screenshot(
                            scenario_description="ui_issue",
                            encode_base64=False,
                            save_to_folder=True
                        )
                        
                        if ui_screenshot_result["success"]:
                            print(f"📸 UI issue screenshot saved: {ui_screenshot_result['filename']}")
                            # Log screenshot filename to agent
                            self.selenium.log_message(f"📸 UI issue screenshot saved: {ui_screenshot_result['filename']}", level="info")
                        
                        print("⚠️  Continuing test despite UI issue...\n")
                    
                    self._print_steps(new_steps)
            
            i += 1
        
        # CONTINUOUS EXPLORATION LOOP - Keep checking until AI says complete
        exploration_complete = False
        max_exploration_iterations = 20  # Safety limit to prevent infinite loops
        exploration_iteration = 0
        
        while not exploration_complete and exploration_iteration < max_exploration_iterations:
            exploration_iteration += 1
            
            print("\n" + "="*70)
            print(f"📊 CHECKING EXPLORATION STATUS (Iteration {exploration_iteration})")
            print("="*70)
            print("🤖 Asking AI if exploration is complete...")
            
            # Extract fresh DOM
            fresh_dom_result = self.selenium.extract_form_dom_with_js()
            if not fresh_dom_result["success"]:
                print("⚠️  Could not extract DOM for exploration check - assuming complete")
                break
            
            # Capture screenshot if enabled
            screenshot_base64 = None
            if self.enable_ui_verification:
                screenshot_result = self.selenium.capture_screenshot(
                    scenario_description=f"exploration_check_{exploration_iteration}",
                    encode_base64=True,
                    save_to_folder=False
                )
                if screenshot_result["success"]:
                    screenshot_base64 = screenshot_result["screenshot"]
                    
                    # Save screenshot for AI analysis
                    saved_path = self._save_ai_screenshot(screenshot_base64, f"exploration_check_{exploration_iteration}")
                    print(f"💾 AI screenshot saved: {saved_path}")
            
            # Ask AI if exploration is complete
            result = self.ai.generate_exploration_steps(
                dom_html=fresh_dom_result["dom_html"],
                executed_steps=executed_steps,
                screenshot_base64=screenshot_base64,
                already_cataloged_pages=[]
            )
            
            exploration_complete = result.get("exploration_complete", False)
            new_steps = result.get("steps", [])
            
            if not exploration_complete and new_steps:
                print(f"🔄 Exploration NOT complete - continuing with {len(new_steps)} more steps")
                steps.extend(new_steps)
                all_generated_steps.extend(new_steps)
                self._print_steps(new_steps)
                
                # Execute the new steps
                while i < len(steps):
                    step = steps[i]
                    step_num = i + 1
                    
                    print(f"\n[Step {step_num}/{len(steps)}] {step.get('action').upper()}: {step.get('description')}")
                    
                    result = self.selenium.execute_step(step)
                    
                    if not result["success"]:
                        print(f"❌ Step failed: {result.get('error')}")
                        consecutive_failures += 1
                        
                        if consecutive_failures >= self.max_retries:
                            print(f"\n❌ Stopping exploration: Max retries reached")
                            exploration_complete = True  # Force stop
                            break
                        
                        print("\n🔧 Attempting failure recovery...")
                        time.sleep(1)
                        
                        recovery_dom = self.selenium.extract_form_dom_with_js()
                        if not recovery_dom["success"]:
                            print("❌ Failed to extract DOM for recovery")
                            break
                        
                        recovery_screenshot = self.selenium.capture_screenshot(
                            scenario_description=f"error_{step.get('description', 'unknown')}",
                            encode_base64=False
                        )
                        
                        if not recovery_screenshot["success"]:
                            print("❌ Failed to capture recovery screenshot")
                            break
                        
                        recovery_steps = self.ai.analyze_failure_and_recover(
                            failed_step=step,
                            executed_steps=executed_steps,
                            fresh_dom=recovery_dom["dom_html"],
                            screenshot_path=recovery_screenshot["filepath"],
                            test_cases=self.test_cases,
                            test_context=self.test_context,
                            attempt_number=consecutive_failures
                        )
                        
                        if recovery_steps:
                            print(f"✅ Generated {len(recovery_steps)} recovery steps")
                            steps = executed_steps + recovery_steps
                            i = len(executed_steps)
                            continue
                        else:
                            print("❌ No recovery steps generated")
                            break
                    
                    consecutive_failures = 0
                    print(f"✅ Step completed")
                    executed_steps.append(step)
                    
                    # Check for form page detection
                    if step.get("form_page_info"):
                        form_page_info = step["form_page_info"]
                        form_name = form_page_info.get("form_name", "unknown_form")
                        print(f"\n✅ FORM PAGE DETECTED: {form_name}")
                        
                        import getpass
                        username = getpass.getuser()
                        form_folder = f"/home/{username}/automation_product_config/ai_projects/{self.project_name}/{form_name}"
                        os.makedirs(form_folder, exist_ok=True)
                        
                        navigation_steps = form_page_info.get("navigation_steps", [])
                        if navigation_steps:
                            nav_file_path = os.path.join(form_folder, "navigation_steps.json")
                            with open(nav_file_path, 'w', encoding='utf-8') as f:
                                json.dump(navigation_steps, f, indent=2, ensure_ascii=False)
                            print(f"💾 Saved navigation steps to: {nav_file_path}")
                    
                    time.sleep(0.5)
                    
                    # Check for DOM changes
                    new_dom_hash = result.get("new_dom_hash")
                    if new_dom_hash and new_dom_hash != self.current_dom_hash:
                        print(f"\n🔄 DOM changed")
                        self.current_dom_hash = new_dom_hash
                    
                    i += 1
                
                # After executing all steps in this batch, loop back to check if more exploration needed
            elif not new_steps:
                print("⚠️  AI returned no steps - assuming exploration complete")
                exploration_complete = True
            else:
                print("✅ Exploration is COMPLETE - no more forms to discover")
        
        if exploration_iteration >= max_exploration_iterations:
            print(f"\n⚠️  Reached max exploration iterations ({max_exploration_iterations}) - stopping")
        
        print("\n" + "="*70)
        print("✅ TEST COMPLETED")
        print(f"   Total steps executed: {len(executed_steps)}")
        print(f"   Exploration iterations: {exploration_iteration}")
        print("="*70)
        
        # Clear critical fields checklist on successful completion
        if self.critical_fields_checklist:
            print("✅ Critical fields checklist cleared (test completed successfully)")
            self.critical_fields_checklist = None
        
        self._save_steps_to_file(executed_steps)
        
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
    
    def _detect_validation_errors_from_dom(self, dom_html: str) -> Dict:
        """
        Detect validation errors in DOM by looking for error indicators
        
        Returns:
            Dict with:
            - has_errors: bool
            - error_fields: list of field selectors/ids that have errors
            - error_messages: list of error message texts found
        """
        from bs4 import BeautifulSoup
        
        result = {
            "has_errors": False,
            "error_fields": [],
            "error_messages": []
        }
        
        try:
            soup = BeautifulSoup(dom_html, 'html.parser')
            
            # Common error classes to look for
            error_classes = [
                'error', 'invalid', 'has-error', 'is-invalid', 
                'field-error', 'ng-invalid', 'validation-error',
                'form-error', 'input-error', 'error-field'
            ]
            
            # Find fields with error classes
            for error_class in error_classes:
                error_elements = soup.find_all(class_=lambda x: x and error_class in x.lower())
                for elem in error_elements:
                    # Try to get field identifier
                    field_id = elem.get('id', '')
                    field_name = elem.get('name', '')
                    field_label = None
                    
                    # Try to find associated label
                    if field_id:
                        label = soup.find('label', {'for': field_id})
                        if label:
                            field_label = label.get_text(strip=True)
                    
                    identifier = field_label or field_id or field_name or elem.get('placeholder', '')
                    if identifier and identifier not in result["error_fields"]:
                        result["error_fields"].append(identifier)
            
            # Find error message elements
            error_msg_selectors = [
                {'class': lambda x: x and 'error' in x.lower()},
                {'class': lambda x: x and 'invalid' in x.lower()},
                {'role': 'alert'},
                {'aria-live': 'polite'}
            ]
            
            for selector in error_msg_selectors:
                error_msgs = soup.find_all(attrs=selector)
                for msg in error_msgs:
                    text = msg.get_text(strip=True)
                    # Only include non-empty messages that look like errors
                    if text and len(text) > 3 and text not in result["error_messages"]:
                        result["error_messages"].append(text)
            
            # Determine if errors exist
            if result["error_fields"] or result["error_messages"]:
                result["has_errors"] = True
            
        except Exception as e:
            print(f"⚠️  Error detecting validation errors from DOM: {e}")
        
        return result
    
    def _parse_critical_fields_from_alert(self, alert_text: str) -> Dict[str, str]:
        """
        Parse alert text to extract problematic fields
        Returns dict of {field_name: issue_type}
        
        Examples:
        "Street Address is required" -> {"Street Address": "MUST FILL"}
        "Email is invalid" -> {"Email": "INVALID FORMAT"}
        "Please fill: Name, City" -> {"Name": "MUST FILL", "City": "MUST FILL"}
        """
        import re
        
        critical_fields = {}
        
        # Pattern 1: "Field X is required" or "Field X is missing"
        required_pattern = r'([A-Z][a-zA-Z\s]+?)\s+is\s+(required|missing)'
        for match in re.finditer(required_pattern, alert_text, re.IGNORECASE):
            field_name = match.group(1).strip()
            critical_fields[field_name] = "MUST FILL"
        
        # Pattern 2: "Field Y is invalid" or "Field Y has wrong format"
        invalid_pattern = r'([A-Z][a-zA-Z\s]+?)\s+is\s+(invalid|has\s+wrong\s+format|has\s+invalid\s+format)'
        for match in re.finditer(invalid_pattern, alert_text, re.IGNORECASE):
            field_name = match.group(1).strip()
            critical_fields[field_name] = "INVALID FORMAT"
        
        # Pattern 3: "Please fill in: Field1, Field2, Field3"
        fill_in_pattern = r'[Pp]lease\s+fill\s+in?:\s*(.+?)(?:\.|$)'
        match = re.search(fill_in_pattern, alert_text)
        if match:
            fields_text = match.group(1)
            # Split by comma and extract field names
            field_list = [f.strip() for f in fields_text.split(',')]
            for field in field_list:
                # Clean up phrases like "is required"
                field_clean = re.sub(r'\s+is\s+(required|missing)', '', field, flags=re.IGNORECASE).strip()
                if field_clean:
                    critical_fields[field_clean] = "MUST FILL"
        
        # Pattern 4: "The following fields are required: Field1, Field2"
        following_pattern = r'[Tt]he\s+following\s+fields\s+are\s+required:\s*(.+?)(?:\.|$)'
        match = re.search(following_pattern, alert_text)
        if match:
            fields_text = match.group(1)
            field_list = [f.strip() for f in fields_text.split(',')]
            for field in field_list:
                field_clean = re.sub(r'\s+is\s+(required|missing)', '', field, flags=re.IGNORECASE).strip()
                if field_clean:
                    critical_fields[field_clean] = "MUST FILL"
        
        # Pattern 5: "Field Z must be..." (validation requirement)
        must_be_pattern = r'([A-Z][a-zA-Z\s]+?)\s+must\s+be'
        for match in re.finditer(must_be_pattern, alert_text, re.IGNORECASE):
            field_name = match.group(1).strip()
            critical_fields[field_name] = "INVALID FORMAT"
        
        return critical_fields


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
        
        # UI issue tracking - list of all issues reported so far
        self.reported_ui_issues = []
    
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
        "test_url": "https://opensource-demo.orangehrmlive.com/web/index.php/dashboard/index",
        "test_cases_file": "test_cases1.json",
        "browser": "chrome",  # chrome, firefox, edge
        "headless": False,
        "screenshot_folder": None,  # None = default to Desktop, or specify path like "screenshots" or "/path/to/folder"
        "enable_ui_verification": True,  # ← Set to False to disable screenshot-based UI verification
        "form_page_name": "person",  # ← REQUIRED: Name of the form page for saving steps
        "max_retries": 3,  # ← Number of retries for failed steps before moving on
        "use_detect_fields_change": False,  # ← Set to False to disable field change detection
        "url_for_login": "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login",  # ← Login page URL (e.g., "https://example.com/login")
        "username_for_login": "Admin",  # ← Username for login
        "password_for_login": "admin123",  # ← Password for login
        "project_name": "orange_app_ai"  # ← Project name for folder structure (e.g., "orange_app_ai")
    }
    
    print("="*70)
    print("🚀 LOCAL TEST MODE")
    print("="*70)
    print(f"URL: {config['test_url']}")
    print(f"Browser: {config['browser']}")
    print(f"Headless: {config['headless']}")
    print(f"Screenshot folder: {config['screenshot_folder'] or 'Desktop (default)'}")
    print(f"UI Verification: {'ENABLED' if config['enable_ui_verification'] else 'DISABLED'}")
    print("="*70)
    
    # Create orchestrator
    orchestrator = LocalTestOrchestrator(
        anthropic_api_key=config["anthropic_api_key"],
        test_cases_file=config["test_cases_file"],
        browser=config["browser"],
        headless=config["headless"],
        screenshot_folder=config["screenshot_folder"],
        enable_ui_verification=config["enable_ui_verification"],
        form_page_name=config["form_page_name"],
        max_retries=config["max_retries"],
        use_detect_fields_change=config["use_detect_fields_change"],
        url_for_login=config["url_for_login"],
        username_for_login=config["username_for_login"],
        password_for_login=config["password_for_login"],
        project_name=config["project_name"]
    )
    
    # Run test
    success = orchestrator.run_test(config["test_url"])
    
    if success:
        print("\n✅ TEST PASSED")
    else:
        print("\n❌ TEST FAILED")


if __name__ == "__main__":
    main()
