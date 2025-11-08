# main.py
# Form Page Crawler - Main Entry Point and Orchestration
# Project: AI-Driven Form Page Test Automation (OPTIMIZED)

import os
import sys
import time
import json
import logging
from typing import List, Dict, Optional, Any
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.chrome.options import Options
from webdriver_manager.chrome import ChromeDriverManager

# Import our modules
from ai_prompter import AIHelper
from selenium_actions import (
    DOMExtractor, DOMChangeDetector, 
    ContextAnalyzer, StepExecutor
)

# ============================================================
# CONFIGURATION
# ============================================================
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
GENERIC_TEST_CASES_FILE = os.path.join(SCRIPT_DIR, "generic_form_page_crawler_test_cases.json")
PROJECTS_BASE_DIR = os.path.expanduser("~/automation_product_config/form_page_crawler_base")

# ============================================================
# LOGGING SETUP
# ============================================================
from inits.log import Logger
import inits.environment as environment
environment.test_mode = "single_test_first"

my_log = Logger(is_full_test=True)
my_log.init_logger()

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S'
)

logger = logging.getLogger('init_logger.form_page_test')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_test')


# ============================================================
# TEST CONTEXT
# ============================================================
class TestContext:
    """Stores test session state for form page testing"""

    def __init__(self):
        # User credentials (for login scenarios)
        self.registered_email = None
        self.registered_password = None
        self.registered_name = None
        
        # Form tracking
        self.filled_fields = {}  # Track fields filled during test
        self.selected_path = []  # Track choices made at junctions (dropdowns, radio buttons, etc.)
        self.current_tab = None  # Track current tab if form has tabs
        self.form_data = {}  # Store all form data entered

    def has_credentials(self):
        """Check if credentials are stored"""
        return self.registered_email is not None
    
    def track_field(self, field_name: str, value: Any):
        """Track a field that was filled"""
        self.filled_fields[field_name] = value
        self.form_data[field_name] = value
        print(f"[FormTracking] Field '{field_name}' = '{value}'")
        result_logger_gui.info(f"[FormTracking] Filled field: {field_name}")
    
    def track_choice(self, junction_name: str, choice: str):
        """Track a choice made at a junction (dropdown, radio, checkbox)"""
        self.selected_path.append({
            "junction": junction_name,
            "choice": choice
        })
        print(f"[PathTracking] At '{junction_name}' chose '{choice}'")
        result_logger_gui.info(f"[PathTracking] Choice: {junction_name} -> {choice}")
    
    def set_tab(self, tab_name: str):
        """Track current tab in multi-tab form"""
        self.current_tab = tab_name
        print(f"[TabTracking] Now on tab: {tab_name}")
        result_logger_gui.info(f"[TabTracking] Current tab: {tab_name}")


# ============================================================
# TEST CASE REPOSITORY
# ============================================================
class TestCaseRepository:
    """Load generic test cases from JSON file"""

    def __init__(self, cache_file: str = GENERIC_TEST_CASES_FILE):
        self.test_cases_file = cache_file
        script_dir = os.path.dirname(os.path.abspath(__file__))
        self.cache_path = os.path.join(script_dir, cache_file)
    
    def load_cached_test_cases(self) -> List[Dict[str, Any]]:
        """Load test cases from cache file"""
        try:
            with open(self.cache_path, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)
                logger.info(f"[TestCaseRepository] Loaded {len(test_cases)} test cases from cache")
                print(f"[TestCaseRepository] Loaded {len(test_cases)} test cases from cache")
                return test_cases
        except Exception as e:
            result_logger_gui.error(f"[TestCaseRepository] Error loading cache: {e}")
            print(f"[TestCaseRepository] Error loading cache: {e}")
            return []
    
    def get_test_cases(self) -> List[Dict]:
        """Load generic test cases from JSON file"""

        if not os.path.exists(self.test_cases_file):
            print(f"[TestCaseRepository] ❌ File not found: {self.test_cases_file}")
            result_logger_gui.error(f"Test cases file not found: {self.test_cases_file}")
            return []

        try:
            with open(self.test_cases_file, 'r', encoding='utf-8') as f:
                test_cases = json.load(f)

            print(f"[TestCaseRepository] Loaded {len(test_cases)} generic test cases")
            logger.info(f"[TestCaseRepository] Loaded {len(test_cases)} test cases")

            return test_cases

        except Exception as e:
            print(f"[TestCaseRepository] ❌ Error loading test cases: {e}")
            result_logger_gui.error(f"Error loading test cases: {e}")
            return []


# ============================================================
# TEST ORCHESTRATOR (WITH ALL OPTIMIZATIONS)
# ============================================================
class TestOrchestrator:
    """Main orchestrator for test execution - WITH OPTIMIZATIONS"""
    
    def __init__(
        self,
        driver: WebDriver,
        form_page_key: str,
        url: str,
        api_key: Optional[str] = None,
        use_ai: bool = True,
        regenerate_only_on_url_change: bool = False
    ):
        self.driver = driver
        self.url = url
        self.form_page_key = form_page_key
        self.regenerate_only_on_url_change = regenerate_only_on_url_change
        self.use_ai = use_ai
        
        # Create project directory
        self.project_dir = os.path.join(PROJECTS_BASE_DIR, form_page_key)
        os.makedirs(self.project_dir, exist_ok=True)
        
        # Initialize components
        self.test_context = TestContext()
        self.test_case_repo = TestCaseRepository()
        self.dom_extractor = DOMExtractor(driver)
        self.dom_detector = DOMChangeDetector()

        self.step_executor = StepExecutor(
            self.driver,
            self.test_context,
            self.url,
            self.form_page_key,
            self.project_dir
        )
        
        self.mode = None
        
        # AI helper (only if using AI mode)
        if use_ai:
            if not api_key:
                raise ValueError("API key required for AI mode")
            self.ai_helper = AIHelper(api_key)
        else:
            self.ai_helper = None
        
        # Load test cases
        self.all_test_cases = self.test_case_repo.get_test_cases()

        logger.info(f"[Orchestrator] Initialized for {form_page_key}")
        print(f"[Orchestrator] Initialized for {form_page_key}")
        print(f"[Orchestrator] Total test cases: {len(self.all_test_cases)}")
        print(f"[Orchestrator] Project directory: {self.project_dir}")
    
    def wait_for_page_stable(self, timeout: int = 5) -> bool:
        """
        Wait for page DOM to stabilize (no changes for 1 second)
        
        Args:
            timeout: Maximum time to wait in seconds
            
        Returns:
            True if page stabilized, False if timeout
        """
        import hashlib
        
        last_hash = None
        stable_count = 0
        required_stable_checks = 2  # Need 2 consecutive stable checks (1 second)
        
        for _ in range(timeout * 2):  # Check every 0.5s
            try:
                current_html = self.driver.page_source
                current_hash = hashlib.md5(current_html.encode('utf-8')).hexdigest()
                
                if current_hash == last_hash:
                    stable_count += 1
                    if stable_count >= required_stable_checks:
                        print(f"[PageStability] Page stabilized after {(_ + 1) * 0.5:.1f}s")
                        return True
                else:
                    stable_count = 0
                
                last_hash = current_hash
                time.sleep(0.5)
            except:
                # If error getting page source, consider it unstable
                time.sleep(0.5)
                continue
        
        print(f"[PageStability] Timeout after {timeout}s, proceeding anyway")
        return False

    def run_with_ai(self):
        """
        Run tests using AI to generate steps dynamically
        ✅ WITH ALL OPTIMIZATIONS ENABLED
        """
        print("\n" + "="*70)
        print("🤖 AI-POWERED FORM PAGE TEST EXECUTION (OPTIMIZED)")
        print("="*70)
        print(f"✅ Optimization 1: Minimal DOM (saves 80-90% tokens)")
        print(f"✅ Optimization 2: Smart Context Detection")
        print(f"Expected API cost savings: 70-80%")
        print("="*70)

        self.mode = 'ai'
        
        if not self.ai_helper:
            print("❌ AI helper not initialized")
            return
        
        # Use all test cases as a single group
        print(f"\n{'=' * 70}")
        print(f"📋 FORM PAGE TEST EXECUTION")
        print(f"   Total Test Cases: {len(self.all_test_cases)}")
        print("=" * 70)

        # Filter out skipped tests
        skipped_tests = [tc for tc in self.all_test_cases if tc.get('skip', False)]
        active_test_cases = [tc for tc in self.all_test_cases if not tc.get('skip', False)]

        if skipped_tests:
            print(f"[Phase 1] Skipping {len(skipped_tests)} test(s):")
            for tc in skipped_tests:
                print(f"   ⏭️  {tc['name']} (skip=true)")
            logger.info(f"Skipped {len(skipped_tests)} tests")

        if not active_test_cases:
            print(f"\n⏭️  No active tests to run (all tests marked skip=true)")
            logger.info(f"No active tests - all marked skip=true")
            return

        print(f"[Phase 1] Running {len(active_test_cases)} test cases")
        
        # Navigate to form page
        print(f"[Phase 2] Navigating to {self.url}...")
        self.driver.get(self.url)
        time.sleep(3)
        
        # Extract fresh DOM (no cache)
        print(f"[Phase 3] Extracting DOM from {self.driver.current_url}...")
        initial_dom = self.dom_extractor.get_form_dom_with_js()
        current_hash = self.dom_extractor.get_dom_hash()
        self.dom_detector.last_dom_hash = current_hash
        
        # DEBUG: Dump initial DOM
        with open('/tmp/initial_dom.html', 'w') as f:
            f.write(initial_dom)
        print(f"[DEBUG] Initial DOM dumped to /tmp/initial_dom.html")
        
        # Generate steps for all test cases
        print(f"[Phase 3] Generating test steps with AI...")
        generated_steps = self.ai_helper.generate_test_steps(
            dom_html=initial_dom,
            test_cases=active_test_cases,
            previous_steps=None,
            step_where_dom_changed=None,
            test_context=self.test_context,
            is_first_iteration=True
        )
        
        if not generated_steps:
            print("❌ No steps generated by AI")
            result_logger_gui.error("AI failed to generate test steps")
            logger.error("AI failed to generate test steps")
            return
        
        print(f"[Phase 4] Generated {len(generated_steps)} steps")
        result_logger_gui.info(f"Generated {len(generated_steps)} steps")
        
        # Print generated steps
        print("\n" + "="*70)
        print("📋 GENERATED TEST STEPS")
        print("="*70)
        for i, step in enumerate(generated_steps, 1):
            action = step.get('action', 'unknown')
            desc = step.get('description', 'No description')
            selector = step.get('selector', '')
            value = step.get('value', '')
            print(f"[{i}] {action.upper()}: {desc}")
            if selector:
                print(f"    Selector: {selector}")
            if value:
                print(f"    Value: {value}")
        print("="*70 + "\n")
        
        # Save generated steps to JSON
        self._save_generated_steps(generated_steps, "ai_generated_steps.json")
        
        # Execute steps with DOM change detection
        print(f"[Phase 5] Executing {len(generated_steps)} steps...")
        result_logger_gui.info("="*70)
        result_logger_gui.info("STARTING TEST EXECUTION")
        result_logger_gui.info("="*70)
        
        executed_steps = []
        failed_steps_count = {}  # Track failed steps: {step_key: attempt_count}
        i = 0  # Manual index control
        
        while i < len(generated_steps):
            step = generated_steps[i]
            step_num = step.get('step_number', i+1)
            
            # Execute the step
            success = self.step_executor.execute_step(step)
            
            if not success:
                # Track failure attempts
                step_key = f"{step.get('action', '')}:{step.get('selector', '')}:{step.get('description', '')}"
                failed_steps_count[step_key] = failed_steps_count.get(step_key, 0) + 1
                
                if failed_steps_count[step_key] >= 2:
                    # Failed twice on same step - give up
                    print(f"❌ Step {step_num} failed twice after recovery attempt - stopping execution")
                    result_logger_gui.error(f"Step {step_num} failed twice - stopping")
                    logger.error(f"Step {step_num} failed twice after recovery")
                    raise Exception(f"Step {step_num} failed twice: {step.get('description')}")
                
                # First failure - attempt recovery
                print(f"⚠️ Step {step_num} failed (attempt {failed_steps_count[step_key]}/2) - attempting recovery...")
                result_logger_gui.warning(f"Step {step_num} failed (attempt {failed_steps_count[step_key]}/2) - attempting recovery")
                
                # Try AI-powered recovery
                recovery_successful = self._attempt_recovery(
                    failed_step=step,
                    executed_steps=executed_steps,
                    generated_steps=generated_steps,
                    step_num=step_num,
                    active_test_cases=active_test_cases,
                    attempt_number=failed_steps_count[step_key]
                )
                
                if recovery_successful:
                    # Recovery generated new steps - update master list
                    # Continue from current position (will retry failed step)
                    continue
                else:
                    # Recovery failed
                    print(f"❌ Recovery failed for step {step_num} - stopping execution")
                    result_logger_gui.error(f"Recovery failed for step {step_num} - stopping")
                    logger.error(f"Recovery failed for step {step_num}")
                    break
            
            executed_steps.append(step)
            
            # Check for alerts/popups after step execution
            alert_info = self._check_for_alert()
            
            if alert_info:
                # Alert detected - need to handle it
                print(f"⚠️ Alert detected after step {step_num}: {alert_info['text']}")
                result_logger_gui.warning(f"Alert detected after step {step_num}: {alert_info['type']}")
                
                # Generate steps to handle the alert
                alert_handled = self._handle_alert_with_ai(
                    alert_info=alert_info,
                    executed_steps=executed_steps,
                    generated_steps=generated_steps,
                    step_num=step_num,
                    active_test_cases=active_test_cases
                )
                
                if not alert_handled:
                    print(f"❌ Failed to handle alert after step {step_num}")
                    result_logger_gui.error(f"Failed to handle alert after step {step_num}")
                    break
                
                # Continue to next step (alert handling steps were inserted)
                i += 1
                continue
            
            # Check for DOM changes after step (only if no alert)
            new_hash = self.dom_extractor.get_dom_hash()
            
            # Check if this action changes context (iframe, shadow root)
            step_action = step.get('action', '')
            context_change_actions = ['switch_to_frame', 'switch_to_parent_frame']
            force_dom_change = (step_action in context_change_actions)
            
            if self.dom_detector.has_dom_changed(new_hash) or force_dom_change:
                if force_dom_change:
                    print(f"\n[Context Changed] After step {step_num} - Switched context (iframe/shadow root)")
                    result_logger_gui.info(f"[Context Changed] After step {step_num} - Context switch detected")
                else:
                    print(f"\n[DOM Changed] After step {step_num}")
                    result_logger_gui.info(f"[DOM Changed] After step {step_num}")
                
                # Wait for page to stabilize before extracting DOM
                print(f"[PageStability] Waiting for page to stabilize...")
                self.wait_for_page_stable(timeout=5)
                
                # Get new URL and extract fresh DOM (now that page is stable)
                new_url = self.driver.current_url
                
                # Always extract fresh DOM (forms + JS inlined)
                new_dom = self.dom_extractor.get_form_dom_with_js()
                
                # DEBUG: Dump regenerated DOM
                with open(f'/tmp/regenerated_dom_step_{step_num}.html', 'w') as f:
                    f.write(new_dom)
                print(f"[DEBUG] Regenerated DOM (after step {step_num}) dumped to /tmp/regenerated_dom_step_{step_num}.html")
                
                # Update hash
                self.dom_detector.update_hash(new_hash)
                
                # Check if we need to regenerate remaining steps
                remaining_steps = generated_steps[i+1:]
                
                # Determine if we should regenerate
                should_regenerate = False
                
                if remaining_steps:
                    if force_dom_change:
                        # Always regenerate for context switches (iframe, shadow root)
                        should_regenerate = True
                        print(f"[Regenerating] Context switch detected, regenerating remaining steps...")
                    elif self.regenerate_only_on_url_change:
                        # Only regenerate if URL actually changed
                        old_url = getattr(self, '_last_url', self.url)
                        if new_url != old_url:
                            should_regenerate = True
                            print(f"[Regenerating] URL changed from {old_url} to {new_url}...")
                        else:
                            print(f"[Skipping Regeneration] URL unchanged, continuing with original steps...")
                    else:
                        # Regenerate on any DOM change
                        should_regenerate = True
                        print(f"[Regenerating] DOM changed, regenerating remaining steps...")
                    
                    # Store current URL for next comparison
                    self._last_url = new_url
                
                if should_regenerate:
                    print(f"[Regenerating] Analyzing new DOM and generating steps...")
                    result_logger_gui.info(f"[Regenerating] Steps for new DOM state")
                    
                    # Generate new steps for remaining test cases
                    new_steps = self.ai_helper.generate_test_steps(
                        dom_html=new_dom,
                        test_cases=active_test_cases,
                        previous_steps=executed_steps,
                        step_where_dom_changed=step_num,
                        test_context=self.test_context,
                        is_first_iteration=False
                    )
                    
                    if new_steps:
                        print(f"[Regenerated] {len(new_steps)} new steps")
                        
                        # Print regenerated steps
                        print("\n" + "="*70)
                        print("📋 REGENERATED TEST STEPS")
                        print("="*70)
                        for idx, step in enumerate(new_steps, 1):
                            action = step.get('action', 'unknown')
                            desc = step.get('description', 'No description')
                            selector = step.get('selector', '')
                            value = step.get('value', '')
                            print(f"[{idx}] {action.upper()}: {desc}")
                            if selector:
                                print(f"    Selector: {selector}")
                            if value:
                                print(f"    Value: {value}")
                        print("="*70 + "\n")
                        
                        # Update master list: keep executed steps + new regenerated steps
                        generated_steps = executed_steps + new_steps
                        
                        # Note: 'i' will increment at end of loop, so next iteration
                        # will be i+1, which is len(executed_steps), which is the
                        # first new step. Perfect!
                    else:
                        print("[Regeneration] Failed, continuing with original steps")
            
            # Move to next step
            i += 1
        
        # Summary
        print("\n" + "="*70)
        print("📊 TEST EXECUTION SUMMARY")
        print("="*70)
        print(f"Total Steps Executed: {len(executed_steps)}/{len(generated_steps)}")
        print(f"Test Cases: {len(active_test_cases)}")
        print(f"Form Page Key: {self.form_page_key}")
        print("="*70)
        
        result_logger_gui.info("="*70)
        result_logger_gui.info("TEST EXECUTION COMPLETE")
        result_logger_gui.info(f"Steps Executed: {len(executed_steps)}/{len(generated_steps)}")
        result_logger_gui.info("="*70)
        
        logger.info(f"Test execution complete - {len(executed_steps)}/{len(generated_steps)} steps executed")
    
    def _attempt_recovery(
        self,
        failed_step: Dict,
        executed_steps: List[Dict],
        generated_steps: List[Dict],
        step_num: int,
        active_test_cases: List[Dict],
        attempt_number: int
    ) -> bool:
        """
        Attempt to recover from a failed step using AI analysis with screenshot
        
        Args:
            failed_step: The step that failed
            executed_steps: Steps completed so far
            generated_steps: Current master list of steps
            step_num: The number of the failed step
            active_test_cases: Test cases being executed
            attempt_number: Which attempt this is (1 or 2)
            
        Returns:
            True if recovery successful and generated_steps updated, False otherwise
        """
        try:
            print(f"[Recovery] Analyzing failure with AI (attempt {attempt_number}/2)...")
            
            # 1. Capture full page screenshot
            screenshot_path = self._capture_full_page_screenshot(step_num)
            
            # 2. Wait for page stability
            self.wait_for_page_stable(timeout=3)
            
            # 3. Extract fresh DOM
            fresh_dom = self.dom_extractor.get_form_dom_with_js()
            
            # 4. Call AI with vision to analyze and suggest recovery
            recovery_steps = self.ai_helper.analyze_failure_and_recover(
                failed_step=failed_step,
                executed_steps=executed_steps,
                fresh_dom=fresh_dom,
                screenshot_path=screenshot_path,
                test_cases=active_test_cases,
                test_context=self.test_context,
                attempt_number=attempt_number
            )
            
            if recovery_steps:
                print(f"[Recovery] AI generated {len(recovery_steps)} recovery + remaining steps")
                
                # Print recovery steps
                print("\n" + "="*70)
                print("🔧 RECOVERY STEPS")
                print("="*70)
                for idx, step in enumerate(recovery_steps, 1):
                    action = step.get('action', 'unknown')
                    desc = step.get('description', 'No description')
                    selector = step.get('selector', '')
                    value = step.get('value', '')
                    print(f"[{idx}] {action.upper()}: {desc}")
                    if selector:
                        print(f"    Selector: {selector}")
                    if value:
                        print(f"    Value: {value}")
                print("="*70 + "\n")
                
                # Update master list: executed + recovery steps
                generated_steps.clear()
                generated_steps.extend(executed_steps + recovery_steps)
                
                return True
            else:
                print("[Recovery] AI could not generate recovery steps")
                return False
                
        except Exception as e:
            print(f"[Recovery] Error during recovery: {e}")
            logger.error(f"Recovery error: {e}")
            return False
    
    def _capture_full_page_screenshot(self, step_num: int) -> str:
        """
        Capture full page screenshot by scrolling
        
        Args:
            step_num: Step number for filename
            
        Returns:
            Path to screenshot file
        """
        import time
        
        try:
            # Scroll to top first
            self.driver.execute_script("window.scrollTo(0, 0);")
            time.sleep(0.5)
            
            # Get page dimensions
            total_height = self.driver.execute_script("return document.body.scrollHeight")
            viewport_height = self.driver.execute_script("return window.innerHeight")
            
            # For now, take screenshot of current viewport
            # TODO: Could stitch multiple screenshots for truly full page
            screenshot_path = os.path.join(
                self.project_dir,
                "screenshots",
                f"recovery_{step_num}_{int(time.time())}.png"
            )
            
            os.makedirs(os.path.dirname(screenshot_path), exist_ok=True)
            self.driver.save_screenshot(screenshot_path)
            
            print(f"[Recovery] Screenshot saved: {screenshot_path}")
            logger.info(f"Recovery screenshot: {screenshot_path}")
            
            return screenshot_path
            
        except Exception as e:
            print(f"[Recovery] Error capturing screenshot: {e}")
            logger.error(f"Screenshot error: {e}")
            return None
    
    def _check_for_alert(self) -> Optional[Dict]:
        """
        Check if a JavaScript alert/confirm/prompt is present
        
        Returns:
            Dict with alert info if present: {
                'type': 'alert' | 'confirm' | 'prompt',
                'text': alert text
            }
            None if no alert present
        """
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            
            # Determine alert type by testing if it accepts input
            alert_type = "alert"  # Default
            
            try:
                # Try to send empty string - if it works, it's a prompt
                alert.send_keys("")
                alert_type = "prompt"
            except:
                # Can't send keys - it's alert or confirm
                # Check if text suggests confirm (has question/choice language)
                if any(word in alert_text.lower() for word in ['sure', 'confirm', 'continue', 'ok', 'cancel', 'yes', 'no']):
                    alert_type = "confirm"
                else:
                    alert_type = "alert"
            
            return {
                'type': alert_type,
                'text': alert_text
            }
            
        except:
            # No alert present
            return None
    
    def _handle_alert_with_ai(
        self,
        alert_info: Dict,
        executed_steps: List[Dict],
        generated_steps: List[Dict],
        step_num: int,
        active_test_cases: List[Dict]
    ) -> bool:
        """
        Use AI to generate steps to handle an alert (with screenshot)
        
        Args:
            alert_info: Dict with alert type and text
            executed_steps: Steps completed so far
            generated_steps: Current master list
            step_num: Step number where alert appeared
            active_test_cases: Test cases being executed
            
        Returns:
            True if alert handling steps generated and inserted
        """
        try:
            print(f"[Alert] Type: {alert_info['type']}, Text: '{alert_info['text']}'")
            print(f"[Alert] Generating handling steps with AI...")
            
            # NOTE: Cannot capture screenshot while alert is present
            # Alert blocks all Selenium interactions including screenshots
            screenshot_path = None
            
            # Call AI to generate alert handling steps (without screenshot)
            alert_steps = self.ai_helper.generate_alert_handling_steps(
                alert_info=alert_info,
                executed_steps=executed_steps,
                screenshot_path=screenshot_path,
                test_cases=active_test_cases,
                test_context=self.test_context,
                step_where_alert_appeared=step_num
            )
            
            if alert_steps:
                print(f"[Alert] AI generated {len(alert_steps)} steps to handle alert + continue")
                
                # Print alert handling steps
                print("\n" + "="*70)
                print("🔔 ALERT HANDLING STEPS")
                print("="*70)
                for idx, step in enumerate(alert_steps, 1):
                    action = step.get('action', 'unknown')
                    desc = step.get('description', 'No description')
                    selector = step.get('selector', '')
                    value = step.get('value', '')
                    print(f"[{idx}] {action.upper()}: {desc}")
                    if selector:
                        print(f"    Selector: {selector}")
                    if value:
                        print(f"    Value: {value}")
                print("="*70 + "\n")
                
                # Update master list: executed + alert handling + remaining steps
                generated_steps.clear()
                generated_steps.extend(executed_steps + alert_steps)
                
                return True
            else:
                print("[Alert] AI could not generate alert handling steps")
                return False
                
        except Exception as e:
            print(f"[Alert] Error handling alert with AI: {e}")
            logger.error(f"Alert handling error: {e}")
            return False

    def run_from_json(self):
        """Run tests from pre-generated JSON file (replay mode)"""
        print("\n" + "="*70)
        print("📼 REPLAY MODE - Executing from JSON")
        print("="*70)
        
        self.mode = 'replay'
        
        # Load steps from JSON
        json_file = os.path.join(self.project_dir, "ai_generated_steps.json")
        
        if not os.path.exists(json_file):
            print(f"❌ JSON file not found: {json_file}")
            result_logger_gui.error(f"JSON file not found: {json_file}")
            logger.error(f"JSON file not found: {json_file}")
            return
        
        try:
            with open(json_file, 'r') as f:
                steps = json.load(f)
            
            print(f"[Loaded] {len(steps)} steps from JSON")
            result_logger_gui.info(f"Loaded {len(steps)} steps from JSON")
            
            # Navigate to form page
            print(f"[Navigating] to {self.url}...")
            self.driver.get(self.url)
            time.sleep(3)
            
            # Execute steps
            print(f"[Executing] {len(steps)} steps...")
            result_logger_gui.info("="*70)
            result_logger_gui.info("STARTING REPLAY EXECUTION")
            result_logger_gui.info("="*70)
            
            for i, step in enumerate(steps):
                success = self.step_executor.execute_step(step)
                
                if not success:
                    print(f"❌ Step {i+1} failed, stopping")
                    result_logger_gui.error(f"Step {i+1} failed - stopping replay")
                    logger.error(f"Replay stopped at step {i+1}")
                    break
            
            print("\n" + "="*70)
            print("📊 REPLAY EXECUTION SUMMARY")
            print("="*70)
            print(f"Steps Executed: {i+1}/{len(steps)}")
            print("="*70)
            
            result_logger_gui.info("="*70)
            result_logger_gui.info("REPLAY EXECUTION COMPLETE")
            result_logger_gui.info(f"Steps Executed: {i+1}/{len(steps)}")
            result_logger_gui.info("="*70)
            
        except Exception as e:
            print(f"❌ Error in replay mode: {e}")
            result_logger_gui.error(f"Replay error: {e}")
            logger.error(f"Replay mode error: {e}")
            import traceback
            traceback.print_exc()

    def _save_generated_steps(self, steps: List[Dict], filename: str):
        """Save generated steps to JSON file"""
        try:
            output_file = os.path.join(self.project_dir, filename)
            
            with open(output_file, 'w') as f:
                json.dump(steps, f, indent=2)
            
            print(f"[Saved] Steps to: {output_file}")
            logger.info(f"Saved generated steps to: {output_file}")
            
        except Exception as e:
            print(f"⚠️ Could not save steps: {e}")
            logger.warning(f"Failed to save generated steps: {e}")


# ============================================================
# DRIVER INITIALIZATION
# ============================================================
def initialize_driver(headless: bool = False) -> WebDriver:
    """Initialize Chrome WebDriver"""
    options = Options()
    
    if headless:
        options.add_argument('--headless=new')
        options.add_argument('--disable-gpu')
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--window-size=1920,1080')
    options.add_argument('--disable-blink-features=AutomationControlled')
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    
    try:
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        print("[WebDriver] ✅ Initialized successfully")
        return driver
    except Exception:
        print("[WebDriver] Default initialization failed, downloading ChromeDriver...")
        downloaded_binary_path = ChromeDriverManager().install()
        service = Service(executable_path=downloaded_binary_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.set_page_load_timeout(40)
        print("[WebDriver] ✅ Initialized successfully")
        return driver


# ============================================================
# MAIN EXECUTION
# ============================================================
def run(
    form_page_key: str,
    url: str,
    mode: str = "ai",
    headless: bool = False,
    api_key: Optional[str] = None,
    regenerate_only_on_url_change: bool = False,
):
    """
    Main entry point for test automation
    
    Args:
        form_page_key: Identifier for this form page test (for file organization)
        url: Target form page URL
        mode: "ai" for AI-powered generation, "replay" for JSON replay
        headless: Run browser in headless mode
        api_key: Anthropic API key (required for AI mode)
        regenerate_only_on_url_change: Only regenerate steps when URL changes (not just DOM)
    """
    
    result_logger_gui.info("="*70)
    result_logger_gui.info("INITIALIZING FORM PAGE TEST AUTOMATION")
    result_logger_gui.info("="*70)
    
    logger.info("Starting form page test automation")

    if not url:
        print("❌ ERROR: URL is required")
        result_logger_gui.error("URL parameter is required")
        logger.error("URL not provided")
        return
    
    target_url = url
    
    print("\n" + "="*70)
    print("📝 FORM PAGE TEST AUTOMATION (OPTIMIZED)")
    print("="*70)
    print(f"Form Page Key: {form_page_key}")
    print(f"Target URL: {target_url}")
    print(f"Mode: {mode.upper()}")
    print(f"Headless: {headless}")
    if mode == "ai":
        print(f"✅ Cost Optimizations: Minimal DOM + Smart Context")
        print(f"✅ Expected Savings: 70-80% on API costs")
    print("="*70)
    
    result_logger_gui.info(f"Form Page Key: {form_page_key}")
    result_logger_gui.info(f"Target URL: {target_url}")
    result_logger_gui.info(f"Mode: {mode.upper()}")
    result_logger_gui.info(f"Headless: {headless}")
    result_logger_gui.info(f"regenerate_only_on_url_change: {regenerate_only_on_url_change}")

    logger.info(f"Configuration - Form: {form_page_key}, Mode: {mode}, Headless: {headless}")
    
    if mode == "ai":
        result_logger_gui.info("✓ Cost Optimizations Enabled:")
        result_logger_gui.info("  - Minimal DOM extraction")
        result_logger_gui.info("  - Smart context detection")
        logger.info("AI mode enabled with cost optimizations")
    
    driver = None
    
    try:
        # Initialize WebDriver
        logger.info("\nInitializing browser...")
        logger.info("="*70)
        
        driver = initialize_driver(headless=headless)
        
        result_logger_gui.info("✓ Browser initialized successfully")
        
        # Create orchestrator
        result_logger_gui.info("Preparing test environment...")
        result_logger_gui.info("="*70)
        
        logger.info("Creating test orchestrator")
        orchestrator = TestOrchestrator(
            driver=driver,
            form_page_key=form_page_key,
            url=url,
            api_key=api_key,
            use_ai=(mode == "ai"),
            regenerate_only_on_url_change=regenerate_only_on_url_change
        )
        
        logger.info(f"✓ Loaded {len(orchestrator.all_test_cases)} test cases")
        
        # Run based on mode
        if mode == "ai":
            orchestrator.run_with_ai()
        elif mode == "replay":
            orchestrator.run_from_json()
        else:
            print(f"❌ Invalid mode: {mode}. Use 'ai' or 'replay'")
            result_logger_gui.info(f"✗ Invalid mode: {mode}")
            logger.error(f"Invalid mode specified: {mode}")
        
    except KeyboardInterrupt:
        print("\n⌨️ User interrupted execution (Ctrl+C)")
        result_logger_gui.info("\n\n✗ Test execution interrupted by user")
        logger.info("User interrupted execution (Ctrl+C)")
    except Exception as e:
        print(f"❌ Error during execution: {e}")
        result_logger_gui.info(f"✗ Error during execution: {str(e)}")
        logger.error(f"Error during execution: {e}")
        import traceback
        traceback.print_exc()
        logger.error(traceback.format_exc())
    finally:
        if driver:
            driver.quit()
            print("\n[Main] Browser closed")
            result_logger_gui.info("\n✓ Browser closed")
            logger.info("Browser closed")


# ============================================================
# CONFIGURATION & ENTRY POINT
# ============================================================
if __name__ == "__main__":
    
    # ============================================================
    # CONFIGURATION
    # ============================================================
    
    # Identifier for this form page test (used for file organization)
    FORM_PAGE_KEY = "my_form_page"

    # Target form page URL - REQUIRED!
    URL = "http://localhost:8000/index.html"
    
    # Mode: "ai" = generate with AI, "replay" = use saved JSON
    MODE = "ai"

    # Browser settings
    HEADLESS = False
    
    # AI settings
    API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    # Regeneration strategy:
    # False (default) = Regenerate on any DOM change (recommended for most forms)
    # True = Only regenerate when URL changes (saves API calls but may miss dynamic content)
    REGENERATE_ONLY_ON_URL_CHANGE = False
    
    # Validate configuration
    if not API_KEY and MODE == "ai":
        print("="*70)
        print("❌ ERROR: ANTHROPIC_API_KEY not found in environment")
        print("Please set the API key or switch to 'replay' mode")
        print("="*70)
        sys.exit(1)
    
    if not URL:
        print("="*70)
        print("❌ ERROR: URL is required")
        print("Please set the URL variable")
        print("="*70)
        sys.exit(1)
    
    # Display configuration
    print("\n" + "="*70)
    print("📋 CONFIGURATION")
    print("="*70)
    print(f"Form Page Key: {FORM_PAGE_KEY}")
    print(f"Target URL: {URL}")
    print(f"Test Cases File: {GENERIC_TEST_CASES_FILE}")
    print(f"Project Directory: {os.path.join(PROJECTS_BASE_DIR, FORM_PAGE_KEY)}")
    print(f"Mode: {MODE}")
    print(f"Headless: {HEADLESS}")
    if MODE == "ai":
        print(f"✅ OPTIMIZATIONS ENABLED:")
        print(f"   - Minimal DOM extraction (80-90% size reduction)")
        print(f"   - Smart context detection")
    print("="*70)
    
    # ============================================================
    # RUN THE AUTOMATION
    # ============================================================
    
    run(
        form_page_key=FORM_PAGE_KEY,
        url=URL,
        mode=MODE,
        headless=HEADLESS,
        api_key=API_KEY,
        regenerate_only_on_url_change=REGENERATE_ONLY_ON_URL_CHANGE
    )
