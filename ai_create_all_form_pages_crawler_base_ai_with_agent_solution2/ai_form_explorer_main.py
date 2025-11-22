# ai_form_explorer_main.py
# Modified to use new Orchestrator-based form discovery
import os
import sys
import time

from typing import List, Optional
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    NoSuchWindowException,
    InvalidSessionIdException,
    SessionNotCreatedException
)
from selenium.webdriver.common.by import By
from agent_selenium import MultiFormsDiscoveryAgent

# Import new orchestrator and AI prompter
from orchestrator import FormDiscoveryOrchestrator
from ai_prompter import AIPrompter

import logging

# Set up simple logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S'
)


def save_and_exit(orchestrator, reason):
    """Save progress and cleanup"""
    print(f"\n{'=' * 70}")
    print(f"💾 SAVING PROGRESS (Reason: {reason})")
    print(f"{'=' * 70}")

    # Save forms discovered so far
    if orchestrator and orchestrator.discovered_forms:
        try:
            orchestrator.save_results("discovered_forms.json")
            print(f"✅ Saved {len(orchestrator.discovered_forms)} forms to discovered_forms.json")
        except Exception as e:
            print(f"❌ Could not save forms: {e}")
    else:
        print("⚠️ No forms to save")

    # Try to close browser
    if hasattr(orchestrator, 'agent'):
        try:
            orchestrator.agent.close_browser()
            print("✅ Browser closed cleanly")
        except:
            print("⚠️ Browser already closed or crashed")

    print(f"{'=' * 70}")
    print(f"🏁 Exiting gracefully with partial results")
    print(f"{'=' * 70}\n")


def run_discovery_with_protection(orchestrator):
    """Run discovery with complete crash protection"""
    try:
        orchestrator.discover_forms()

    # ===== TIMEOUT ISSUES =====
    except TimeoutException as e:
        print(f"\n⏰ TIMEOUT: Page load exceeded limit")
        print(f"   Error: {e}")
        save_and_exit(orchestrator, "timeout")

    # ===== BROWSER CRASHES =====
    except (InvalidSessionIdException, SessionNotCreatedException) as e:
        print(f"\n🔥 BROWSER CRASH: Browser session died")
        print(f"   Error: {e}")
        save_and_exit(orchestrator, "browser_crash")

    except NoSuchWindowException as e:
        print(f"\n🪟 WINDOW CLOSED: Browser window was closed")
        print(f"   Error: {e}")
        save_and_exit(orchestrator, "window_closed")

    except WebDriverException as e:
        # Catch all other WebDriver issues
        print(f"\n⚠️ WEBDRIVER ERROR: {e}")
        save_and_exit(orchestrator, "webdriver_error")

    # ===== USER INTERRUPT =====
    except KeyboardInterrupt:
        print(f"\n⌨️ USER STOPPED: Ctrl+C pressed")
        save_and_exit(orchestrator, "user_interrupt")

    # ===== ANY OTHER ERROR =====
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}")
        print(f"   Error: {e}")
        save_and_exit(orchestrator, "unexpected_error")
        raise  # Re-raise so you can see the full traceback


def attempt_login(agent, username: str, password: str) -> bool:
    """
    Attempt to find and fill login form fields using agent methods.
    Returns True if login was attempted, False if no login fields found.
    
    Args:
        agent: AgentSelenium instance
        username: Username/email to enter
        password: Password to enter
    """
    try:
        # Look for username/email field
        username_selector = None
        password_selector = None
        
        # Common selectors for username/email
        username_selectors = [
            'input[type="email"]',
            'input[type="text"][name*="user"]',
            'input[type="text"][name*="email"]',
            'input[name="username"]',
            'input[name="email"]',
            'input[id*="user"]',
            'input[id*="email"]',
            'input[placeholder*="user"]',
            'input[placeholder*="email"]'
        ]
        
        # Find visible username field
        for selector in username_selectors:
            result = agent.find_elements(selector)
            if result.get("success") and result.get("count") > 0:
                # Check if first element is displayed
                elements = result.get("elements", [])
                if elements and elements[0].get("displayed"):
                    username_selector = selector
                    break
        
        # Find password field
        password_selector_candidate = 'input[type="password"]'
        result = agent.find_elements(password_selector_candidate)
        if result.get("success") and result.get("count") > 0:
            elements = result.get("elements", [])
            if elements and elements[0].get("displayed"):
                password_selector = password_selector_candidate
        
        # If both fields found, fill them
        if username_selector and password_selector:
            print("[Login] Found login fields, attempting to log in...")
            
            # Fill username using execute_step
            fill_username_result = agent.execute_step({
                "action": "fill",
                "selector": username_selector,
                "value": username,
                "description": "Enter username",
                "step_number": "login_1"
            })
            
            if not fill_username_result.get("success"):
                print(f"[Login] Failed to fill username: {fill_username_result.get('error')}")
                return False
            time.sleep(0.5)
            
            # Fill password using execute_step
            fill_password_result = agent.execute_step({
                "action": "fill",
                "selector": password_selector,
                "value": password,
                "description": "Enter password",
                "step_number": "login_2"
            })
            
            if not fill_password_result.get("success"):
                print(f"[Login] Failed to fill password: {fill_password_result.get('error')}")
                return False
            time.sleep(0.5)
            
            # Find and click submit button
            submit_selector = None
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
            ]
            
            for selector in submit_selectors:
                result = agent.find_elements(selector)
                if result.get("success") and result.get("count") > 0:
                    elements = result.get("elements", [])
                    if elements and elements[0].get("displayed"):
                        submit_selector = selector
                        break
            
            if submit_selector:
                click_result = agent.execute_step({
                    "action": "click",
                    "selector": submit_selector,
                    "description": "Click login button",
                    "step_number": "login_3"
                })
                
                if click_result.get("success"):
                    time.sleep(2.0)
                    agent.wait_dom_ready()
                    print("[Login] Login submitted successfully")
                    return True
                else:
                    print(f"[Login] Failed to click submit: {click_result.get('error')}")
                    return False
            else:
                print("[Login] Could not find submit button")
                return False
        else:
            print("[Login] No login fields detected, assuming already logged in")
            return False
            
    except Exception as e:
        print(f"[Login] Error during login attempt: {e}")
        return False


def run(
    start_url: str,
    project_name: str = "default_project",
    username: Optional[str] = None,
    password: Optional[str] = None,
    logged_in: bool = False,
    headless: bool = False,
    hidden: bool = False,
    use_ai: bool = True,
    api_key: str = None,
    max_depth: int = 10,
    max_states: int = 100
):
    """
    Main runner function for form discovery
    
    Args:
        start_url: The URL to start crawling from (post-login URL or login page)
        project_name: Name of the project for organizing outputs
        username: Username for login (optional)
        password: Password for login (optional)
        logged_in: If True and no credentials provided, assumes already logged in
        headless: Run browser in headless mode
        use_ai: Use AI (Claude) for intelligent form discovery (requires ANTHROPIC_API_KEY)
        api_key: Anthropic API key (if not provided, tries environment variable)
        max_depth: Maximum depth for exploration (default 10)
        max_states: Maximum states to explore (default 100)
    """
    
    # Check API key
    if api_key is None and use_ai:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            print("[Main] Using API key from environment")
        else:
            print("[Main] ❌ No API key found - cannot use AI")
            return
    
    # Initialize Agent
    agent = MultiFormsDiscoveryAgent(screenshot_folder=None)
    
    # Initialize browser
    browser_result = agent.initialize_browser(
        browser_type="chrome",
        headless=headless
    )
    
    if not browser_result.get("success"):
        print(f"[Main] Failed to initialize browser: {browser_result.get('error')}")
        return
    
    print("[Main] ✅ Browser initialized successfully")

    try:
        # Navigate to start URL
        agent.navigate_to_url(start_url)
        agent.wait_dom_ready()

        # Wait for JavaScript to render
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By

        print("[Waiting] For JavaScript to render content...")
        try:
            WebDriverWait(agent.driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
            )
            print("[Waiting] ✅ Content rendered!")
        except:
            print("[Waiting] ⚠️ Timeout - continuing anyway")

        time.sleep(2)

        # If credentials provided, attempt automatic login
        if username and password:
            login_attempted = attempt_login(agent, username, password)
            if login_attempted:
                print("[Main] Login completed, waiting for dashboard to load...")
                time.sleep(2.0)
                agent.wait_dom_ready()
        elif not logged_in:
            # Manual login
            input("Log in manually, then press Enter...")
        else:
            print("[Main] Assuming already logged in, proceeding with discovery...")
        
        # Get current URL after login (this becomes our start URL)
        current_url_result = agent.get_current_url()
        dashboard_url = current_url_result.get('url', start_url)
        print(f"[Main] Dashboard URL: {dashboard_url}")
        
        # Initialize AI Prompter
        print(f"[Main] Initializing AI Prompter...")
        ai_prompter = AIPrompter(api_key=api_key)
        
        # Initialize Orchestrator
        print(f"[Main] Initializing Orchestrator...")
        orchestrator = FormDiscoveryOrchestrator(
            agent=agent,
            ai_prompter=ai_prompter,
            start_url=dashboard_url,
            project_name=project_name,  # ← ADD THIS LINE
            max_depth=max_depth,
            max_states=max_states
        )
        
        # Start discovery
        print(f"[Main] Starting form discovery for project: {project_name}")
        
        # Run discovery with crash protection
        run_discovery_with_protection(orchestrator)
        
        # Save results
        orchestrator.save_results("discovered_forms.json")
        
        # Print summary
        orchestrator.print_summary()

    except Exception as e:
        print(f"[Main] Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        agent.close_browser()
        print("[Main] Browser closed")


if __name__ == "__main__":
    import os

    # ============================================================
    # CONFIGURATION
    # ============================================================

    PROJECT_NAME = "orange_app_ai"
    START_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"

    USERNAME = "Admin"
    PASSWORD = "admin123"
    LOGGED_IN = False

    USE_AI = True
    API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    if API_KEY:
        print(f"[Config] ✅ API Key loaded")
    else:
        print("[Config] ❌ No API key - cannot proceed")
        sys.exit(1)

    # Discovery parameters
    MAX_DEPTH = 10  # How deep to explore (levels of clicks)
    MAX_STATES = 100  # Maximum states to explore

    HEADLESS = False

    # ============================================================
    # RUN THE DISCOVERY
    # ============================================================

    run(
        start_url=START_URL,
        project_name=PROJECT_NAME,
        username=USERNAME,
        password=PASSWORD,
        logged_in=LOGGED_IN,
        headless=HEADLESS,
        use_ai=USE_AI,
        api_key=API_KEY,
        max_depth=MAX_DEPTH,
        max_states=MAX_STATES
    )
