# form_page_runner.py
# Execute form page stages from JSON file

import sys
import os
import json
import time
import logging
from agent_selenium import AgentSelenium
from ai_form_page_runner_error_prompter import AIFormPageRunError

logger = logging.getLogger('init_logger.form_page_run')
result_logger_gui = logging.getLogger('init_result_logger_gui.form_page_run')


class FormPageRunner:
    """Execute test stages from JSON file"""
    
    def __init__(
        self, 
        browser: str = "chrome", 
        headless: bool = False,
        api_key: str = None,
        max_retries_locator_changed: int = 2,
        max_retries_general_error: int = 2,
        max_retries_correction_steps: int = 2,
        general_error_wait_time: int = 60
    ):
        self.selenium = AgentSelenium()
        self.browser = browser
        self.headless = headless
        self.ai_error_handler = AIFormPageRunError(api_key=api_key) if api_key else None
        self.max_retries_locator_changed = max_retries_locator_changed
        self.max_retries_general_error = max_retries_general_error
        self.max_retries_correction_steps = max_retries_correction_steps
        self.general_error_wait_time = general_error_wait_time
    
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
                # If accept_alert or dismiss_alert fails (no such alert), just continue
                if action in ['accept_alert', 'dismiss_alert']:
                    print(f"⏭️  Alert already handled - continuing")
                    continue
                
                # If VERIFY action fails, this is a test assertion failure - exit without AI recovery
                if action == 'verify':
                    print(f"❌ Verification failed - test assertion failure")
                    print(f"   This is an expected test result, not a system error")
                    logger.error(f"[FormPageRunner] VERIFY failed - test assertion failure - check_traffic")
                    self.selenium.close_browser()
                    return False
                
                # For other actions, use AI error handling
                error_msg = result.get('error', 'Unknown error')
                print(f"❌ Step failed: {error_msg}")
                self.selenium.log_message(f"❌ Step failed: {error_msg}", "error")
                
                if not self.ai_error_handler:
                    print("❌ No AI error handler available - exiting")
                    self.selenium.log_message("❌ No AI error handler available - exiting", "error")
                    self.selenium.close_browser()
                    return False
                
                # Handle error with AI
                self.selenium.log_message("🤖 Analyzing error with AI...", "info")
                success = self._handle_error_with_ai(
                    failed_stage=stage,
                    error_message=result.get('error', 'Unknown error'),
                    stages=stages,
                    json_file_path=json_file_path,
                    stage_index=i-1
                )
                
                if not success:
                    print("❌ Error recovery failed - exiting")
                    self.selenium.log_message("❌ Error recovery failed - exiting", "error")
                    self.selenium.close_browser()
                    return False
                
                # If recovery succeeded, continue to next stage
                print("✅ Error recovered - continuing")
                self.selenium.log_message("✅ Error recovered - continuing", "info")
            else:
                print(f"✅ Step completed")
            
            # Small delay between steps to let UI settle
            time.sleep(0.3)
        
        print("\n" + "="*70)
        print("✅ ALL STAGES COMPLETED SUCCESSFULLY")
        
        # Close browser
        print("\n🔒 Closing browser...")
        self.selenium.close_browser()
        print("✅ Browser closed")
        
        return True
    
    def _is_general_error(self, dom_html: str) -> bool:
        """
        Check if DOM indicates a general error (404, blank page, 500, etc.)
        Returns True if general error detected, False otherwise
        
        IMPORTANT: Only returns True for ACTUAL page errors, not missing elements
        """
        if not dom_html or len(dom_html.strip()) < 200:
            # Very small DOM = blank page
            return True
        
        # Convert to lowercase for case-insensitive matching
        dom_lower = dom_html.lower()
        
        # Check for EXPLICIT error indicators only
        error_patterns = [
            "this site can't be reached",
            "err_connection_refused",
            "err_connection",
            "err_name_not_resolved",
            "unable to connect",
            "connection refused",
            "404 not found",
            "404 error",
            "page not found",
            "500 internal server error",
            "502 bad gateway",
            "503 service unavailable",
            "504 gateway timeout",
            "the page isn't working",
            "can't reach this page"
        ]
        
        for pattern in error_patterns:
            if pattern in dom_lower:
                return True
        
        # If we have form elements or substantial content, it's NOT a general error
        # Check for common form indicators
        if any(indicator in dom_lower for indicator in ['<input', '<select', '<textarea', '<form']):
            # Page has form elements - not a general error
            return False
        
        return False
    
    def _handle_error_with_ai(
        self,
        failed_stage: dict,
        error_message: str,
        stages: list,
        json_file_path: str,
        stage_index: int
    ) -> bool:
        """Handle error with AI analysis and recovery"""
        
        print("\n🔍 Analyzing error...")
        
        # Capture error context (DOM + screenshot)
        context = self.selenium.capture_error_context()
        if not context.get("success"):
            print(f"❌ Failed to capture error context: {context.get('error')}")
            logger.error(f"[FormPageRunner] Failed to capture error context: {context.get('error')}")
            return False
        
        dom_html = context.get("dom_html", "")
        screenshot_base64 = context.get("screenshot_base64", "")
        
        # Check if this is a general error (without AI)
        if self._is_general_error(dom_html):
            print("🔴 General error detected (page load issue)")
            logger.warning("[FormPageRunner] General error detected - check_traffic - notify_agent_web")
            return self._handle_general_error_new(failed_stage, stages, json_file_path, stage_index)
        
        # Not a general error - call AI for analysis
        print("🤖 Calling AI for error analysis...")
        ai_result = self.ai_error_handler.analyze_error(
            failed_stage=failed_stage,
            dom_html=dom_html,
            screenshot_base64=screenshot_base64,
            all_stages=stages,
            error_message=error_message
        )
        
        decision = ai_result.get("decision")
        description = ai_result.get("description", "")
        
        print(f"\n📋 AI Decision: {decision}")
        print(f"💡 Description: {description}")
        
        self.selenium.log_message(f"📋 AI Decision: {decision}", "info")
        self.selenium.log_message(f"💡 Description: {description}", "info")
        
        # Handle based on decision
        if decision == "locator_changed":
            return self._handle_locator_changed(ai_result, failed_stage, stages, json_file_path, stage_index)
        
        elif decision == "general_error":
            # AI says it's general error - handle it
            return self._handle_general_error_new(failed_stage, stages, json_file_path, stage_index)
        
        elif decision == "need_healing":
            return self._handle_need_healing(description)
        
        elif decision == "correction_steps":
            return self._handle_correction_steps(ai_result, failed_stage, stages, json_file_path, stage_index)
        
        else:
            print(f"❌ Unknown AI decision: {decision}")
            logger.error(f"[FormPageRunner] Unknown AI decision: {decision}")
            return False
    
    def _handle_locator_changed(self, ai_result: dict, failed_stage: dict, stages: list, json_file_path: str, stage_index: int) -> bool:
        """Handle locator_changed decision"""
        
        corrected_step = ai_result.get("corrected_step")
        if not corrected_step:
            print("❌ No corrected step from AI")
            self.selenium.log_message("❌ No corrected step from AI", "error")
            logger.error("[FormPageRunner] locator_changed but no corrected step")
            return False
        
        print(f"🔄 Retrying with updated locator...")
        self.selenium.log_message(f"🔄 Retrying with updated locator...", "info")
        
        for attempt in range(self.max_retries_locator_changed):
            print(f"   Attempt {attempt + 1}/{self.max_retries_locator_changed}")
            self.selenium.log_message(f"   Attempt {attempt + 1}/{self.max_retries_locator_changed}", "info")
            
            result = self.selenium.execute_step(corrected_step)
            
            if result.get("success"):
                print("✅ Step succeeded with new locator")
                self.selenium.log_message("✅ Step succeeded with new locator", "info")
                
                # Update JSON file
                stages[stage_index] = corrected_step
                self._save_stages_to_file(stages, json_file_path)
                print(f"💾 Updated JSON file with new locator")
                logger.info(f"[FormPageRunner] Updated stage {stage_index} with new locator")
                
                return True
            
            print(f"❌ Retry failed: {result.get('error')}")
            
            # If not last attempt, call AI again
            if attempt < self.max_retries_locator_changed - 1:
                print("🤖 Calling AI again for another attempt...")
                
                context = self.selenium.capture_error_context()
                if not context.get("success"):
                    continue
                
                ai_result = self.ai_error_handler.analyze_error(
                    failed_stage=corrected_step,
                    dom_html=context.get("dom_html", ""),
                    screenshot_base64=context.get("screenshot_base64", ""),
                    all_stages=stages,
                    error_message=result.get('error', '')
                )
                
                corrected_step = ai_result.get("corrected_step")
                if not corrected_step:
                    break
        
        logger.error(f"[FormPageRunner] locator_changed failed after {self.max_retries_locator_changed} attempts")
        return False
    
    def _handle_general_error_new(self, failed_stage: dict, stages: list, json_file_path: str, stage_index: int) -> bool:
        """
        Handle general error with new mechanism:
        1. Retry loop: wait, refresh, check DOM
        2. If recovered: restart test from beginning
        """
        
        for attempt in range(self.max_retries_general_error):
            print(f"\n🔄 General error - Attempt {attempt + 1}/{self.max_retries_general_error}")
            
            message = f"General error - Attempt {attempt + 1}/{self.max_retries_general_error} - check_traffic - notify_agent_web"
            self.selenium.log_message(message, "warning")
            logger.warning(f"[FormPageRunner] {message}")
            
            # Wait before retry
            print(f"⏳ Waiting {self.general_error_wait_time} seconds before retry...")
            self.selenium.log_message(f"⏳ Waiting {self.general_error_wait_time} seconds before retry...", "info")
            time.sleep(self.general_error_wait_time)
            
            # Refresh page
            print("🔄 Refreshing page...")
            self.selenium.log_message("🔄 Refreshing page...", "info")
            try:
                self.selenium.driver.refresh()
                time.sleep(3)  # Wait for page to load
            except Exception as e:
                print(f"❌ Refresh failed: {e}")
                error_msg = f"Refresh failed: {e} - check_traffic - notify_agent_web"
                self.selenium.log_message(error_msg, "error")
                logger.error(f"[FormPageRunner] {error_msg}")
                continue
            
            # Check if page recovered (get DOM again)
            print("🔍 Checking if page recovered...")
            context = self.selenium.capture_error_context()
            if not context.get("success"):
                print(f"❌ Failed to capture context after refresh")
                continue
            
            dom_html = context.get("dom_html", "")
            
            # Check if still general error
            if self._is_general_error(dom_html):
                print(f"❌ Still general error after refresh")
                error_msg = f"Still general error after refresh - check_traffic - notify_agent_web"
                self.selenium.log_message(error_msg, "warning")
                logger.warning(f"[FormPageRunner] {error_msg}")
                continue
            
            # Page recovered!
            print("✅ Page recovered - no longer general error")
            self.selenium.log_message("✅ Page recovered - restarting test from beginning", "info")
            logger.info("[FormPageRunner] Page recovered after general error - restarting from beginning")
            
            # Restart test from beginning
            return self._restart_test_from_beginning(stages, json_file_path)
        
        # All retries exhausted
        print(f"❌ General error - all {self.max_retries_general_error} attempts failed")
        final_msg = f"General error - all {self.max_retries_general_error} attempts failed - check_traffic - notify_agent_web"
        self.selenium.log_message(final_msg, "error")
        logger.error(f"[FormPageRunner] {final_msg}")
        return False
    
    def _restart_test_from_beginning(self, stages: list, json_file_path: str) -> bool:
        """
        Restart test execution from beginning after recovering from general error
        """
        print("\n" + "="*70)
        print("🔄 RESTARTING TEST FROM BEGINNING")
        print("="*70)
        print(f"Reason: Page reset after general error recovery")
        print(f"Executing all {len(stages)} stages from start...")
        print("="*70 + "\n")
        
        self.selenium.log_message("="*70, "info")
        self.selenium.log_message("🔄 RESTARTING TEST FROM BEGINNING", "info")
        self.selenium.log_message(f"Executing all {len(stages)} stages from start", "info")
        self.selenium.log_message("="*70, "info")
        
        # Execute all stages from beginning
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
                # If step fails during restart, handle error normally
                if action in ['accept_alert', 'dismiss_alert']:
                    print(f"⏭️  Alert already handled - continuing")
                    continue
                
                if action == 'verify':
                    print(f"❌ Verification failed - test assertion failure")
                    logger.error(f"[FormPageRunner] VERIFY failed during restart - check_traffic")
                    return False
                
                # For other failures, use AI error handling
                error_msg = result.get('error', 'Unknown error')
                print(f"❌ Step failed during restart: {error_msg}")
                self.selenium.log_message(f"❌ Step failed during restart: {error_msg}", "error")
                
                if not self.ai_error_handler:
                    print("❌ No AI error handler available")
                    return False
                
                # Handle error with AI (recursive call)
                success = self._handle_error_with_ai(
                    failed_stage=stage,
                    error_message=error_msg,
                    stages=stages,
                    json_file_path=json_file_path,
                    stage_index=i-1
                )
                
                if not success:
                    print("❌ Error recovery failed during restart")
                    return False
                
                print("✅ Error recovered - continuing restart")
            else:
                print(f"✅ Step completed")
            
            time.sleep(0.3)
        
        print("\n" + "="*70)
        print("✅ TEST RESTART COMPLETED SUCCESSFULLY")
        print("="*70)
        
        self.selenium.log_message("="*70, "info")
        self.selenium.log_message("✅ TEST RESTART COMPLETED SUCCESSFULLY", "info")
        self.selenium.log_message("="*70, "info")
        
        return True
    
    def _handle_need_healing(self, description: str) -> bool:
        """Handle need_healing decision"""
        
        print("\n" + "="*70)
        print("🔴 MAJOR UI CHANGES DETECTED - HEALING REQUIRED")
        print("="*70)
        print(f"💡 Changes: {description}")
        print("🛑 Exiting gracefully - Form needs to be re-analyzed")
        print("="*70)
        
        self.selenium.log_message("="*70, "error")
        self.selenium.log_message("🔴 MAJOR UI CHANGES DETECTED - HEALING REQUIRED", "error")
        self.selenium.log_message(f"💡 Changes: {description}", "error")
        self.selenium.log_message("🛑 Exiting gracefully - Form needs to be re-analyzed", "error")
        self.selenium.log_message("="*70, "error")
        
        logger.error(f"[FormPageRunner] need_healing - {description} - check_traffic")
        return False
    
    def _handle_correction_steps(self, ai_result: dict, failed_stage: dict, stages: list, json_file_path: str, stage_index: int) -> bool:
        """Handle correction_steps decision"""
        
        correction_type = ai_result.get("type")
        corrected_step = ai_result.get("corrected_step")
        
        if correction_type == "present_only":
            return self._handle_correction_present_only(corrected_step, stages, json_file_path, stage_index)
        
        elif correction_type == "with_presteps":
            presteps = ai_result.get("presteps", [])
            return self._handle_correction_with_presteps(presteps, corrected_step, stages, json_file_path, stage_index)
        
        else:
            print(f"❌ Unknown correction type: {correction_type}")
            logger.error(f"[FormPageRunner] Unknown correction type: {correction_type}")
            return False
    
    def _handle_correction_present_only(self, corrected_step: dict, stages: list, json_file_path: str, stage_index: int) -> bool:
        """Handle correction with just present step"""
        
        print(f"🔄 Retrying with corrected step...")
        self.selenium.log_message(f"🔄 Retrying with corrected step...", "info")
        
        for attempt in range(self.max_retries_correction_steps):
            print(f"   Attempt {attempt + 1}/{self.max_retries_correction_steps}")
            self.selenium.log_message(f"   Attempt {attempt + 1}/{self.max_retries_correction_steps}", "info")
            
            result = self.selenium.execute_step(corrected_step)
            
            if result.get("success"):
                print("✅ Corrected step succeeded")
                self.selenium.log_message("✅ Corrected step succeeded", "info")
                
                # Update JSON
                stages[stage_index] = corrected_step
                self._save_stages_to_file(stages, json_file_path)
                print(f"💾 Updated JSON with corrected step")
                logger.info(f"[FormPageRunner] Updated stage {stage_index} with correction")
                
                return True
            
            print(f"❌ Retry failed: {result.get('error')}")
            
            # If not last attempt, call AI again
            if attempt < self.max_retries_correction_steps - 1:
                print("🤖 Calling AI again...")
                
                context = self.selenium.capture_error_context()
                if not context.get("success"):
                    continue
                
                ai_result = self.ai_error_handler.analyze_error(
                    failed_stage=corrected_step,
                    dom_html=context.get("dom_html", ""),
                    screenshot_base64=context.get("screenshot_base64", ""),
                    all_stages=stages,
                    error_message=result.get('error', '')
                )
                
                corrected_step = ai_result.get("corrected_step")
                if not corrected_step:
                    break
        
        logger.error(f"[FormPageRunner] correction_steps (present_only) failed after {self.max_retries_correction_steps} attempts")
        return False
    
    def _handle_correction_with_presteps(self, presteps: list, corrected_step: dict, stages: list, json_file_path: str, stage_index: int) -> bool:
        """Handle correction with pre-steps + present step"""
        
        print(f"🔄 Executing {len(presteps)} pre-steps + corrected step...")
        self.selenium.log_message(f"🔄 Executing {len(presteps)} pre-steps + corrected step...", "info")
        
        for attempt in range(self.max_retries_correction_steps):
            print(f"   Attempt {attempt + 1}/{self.max_retries_correction_steps}")
            self.selenium.log_message(f"   Attempt {attempt + 1}/{self.max_retries_correction_steps}", "info")
            
            # Execute pre-steps
            all_succeeded = True
            for i, prestep in enumerate(presteps, 1):
                print(f"   Pre-step {i}/{len(presteps)}: {prestep.get('action')} - {prestep.get('description')}")
                self.selenium.log_message(f"   Pre-step {i}/{len(presteps)}: {prestep.get('action')} - {prestep.get('description')}", "info")
                result = self.selenium.execute_step(prestep)
                
                if not result.get("success"):
                    print(f"   ❌ Pre-step failed: {result.get('error')}")
                    self.selenium.log_message(f"   ❌ Pre-step failed: {result.get('error')}", "error")
                    all_succeeded = False
                    break
                
                print(f"   ✅ Pre-step completed")
                self.selenium.log_message(f"   ✅ Pre-step completed", "info")
                time.sleep(0.3)
            
            if not all_succeeded:
                if attempt < self.max_retries_correction_steps - 1:
                    continue
                else:
                    break
            
            # Execute corrected step
            print(f"   Executing corrected step...")
            result = self.selenium.execute_step(corrected_step)
            
            if result.get("success"):
                print("✅ All steps succeeded")
                self.selenium.log_message("✅ All steps succeeded", "info")
                
                # Update JSON - ONLY save corrected_step (don't add presteps)
                stages[stage_index] = corrected_step
                self._save_stages_to_file(stages, json_file_path)
                print(f"💾 Updated JSON with corrected step (pre-steps executed but not saved)")
                logger.info(f"[FormPageRunner] Updated stage {stage_index} with corrected step ({len(presteps)} presteps executed)")
                
                return True
            
            print(f"❌ Corrected step failed: {result.get('error')}")
            
            # If not last attempt, call AI again
            if attempt < self.max_retries_correction_steps - 1:
                print("🤖 Calling AI again...")
                
                context = self.selenium.capture_error_context()
                if not context.get("success"):
                    continue
                
                ai_result = self.ai_error_handler.analyze_error(
                    failed_stage=corrected_step,
                    dom_html=context.get("dom_html", ""),
                    screenshot_base64=context.get("screenshot_base64", ""),
                    all_stages=stages,
                    error_message=result.get('error', '')
                )
                
                if ai_result.get("decision") != "correction_steps":
                    break
                
                presteps = ai_result.get("presteps", [])
                corrected_step = ai_result.get("corrected_step")
                if not corrected_step:
                    break
        
        logger.error(f"[FormPageRunner] correction_steps (with_presteps) failed after {self.max_retries_correction_steps} attempts")
        return False
    
    def _save_stages_to_file(self, stages: list, json_file_path: str):
        """Save updated stages back to JSON file"""
        with open(json_file_path, 'w') as f:
            json.dump(stages, f, indent=2)


def main():
    """Main entry point"""
    
    # Configuration
    config = {
        "browser": "chrome",  # chrome, firefox, edge
        "headless": False,
        "url": "http://localhost:8000/test-form.html",
        "json_file": "/home/ranlaser/automation_product_config/ai_projects/local_web_site/form_pages_discovery/person/create_view_stages/create_verify_person.json",
        "api_key": os.getenv("ANTHROPIC_API_KEY"),
        
        # Retry configurations
        "max_retries_locator_changed": 2,      # How many times to retry when locator changed
        "max_retries_general_error": 2,        # How many times to retry general errors (page load issues)
        "max_retries_correction_steps": 2,     # How many times to retry correction steps
        "general_error_wait_time": 60          # Seconds to wait before retrying general errors
    }
    
    print("="*70)
    print("🚀 FORM PAGE RUNNER")
    print("="*70)
    print(f"Browser: {config['browser']}")
    print(f"Headless: {config['headless']}")
    print(f"URL: {config['url']}")
    print(f"JSON: {config['json_file']}")
    print(f"\n⚙️  Retry Configuration:")
    print(f"   Locator Changed Retries: {config['max_retries_locator_changed']}")
    print(f"   General Error Retries: {config['max_retries_general_error']}")
    print(f"   Correction Steps Retries: {config['max_retries_correction_steps']}")
    print(f"   General Error Wait Time: {config['general_error_wait_time']}s")
    print("="*70)
    
    # Create runner
    runner = FormPageRunner(
        browser=config["browser"],
        headless=config["headless"],
        api_key=config["api_key"],
        max_retries_locator_changed=config["max_retries_locator_changed"],
        max_retries_general_error=config["max_retries_general_error"],
        max_retries_correction_steps=config["max_retries_correction_steps"],
        general_error_wait_time=config["general_error_wait_time"]
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
