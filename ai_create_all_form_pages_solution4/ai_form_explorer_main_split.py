# ai_form_explorer_main_split.py
# Example of how to use the split architecture
# Agent (Selenium) + Server (AI/Files) working together in same process

import os
import sys
import time
from typing import List, Optional

from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.webdriver import WebDriver
from selenium.webdriver.common.by import By
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    WebDriverException,
    NoSuchWindowException,
    InvalidSessionIdException,
    SessionNotCreatedException
)
from form_utils import wait_dom_ready, all_inputs_on_page
from agent_form_pages import AgentFormPages
from form_pages_crawler_server import FormPagesCrawler

import logging
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


def save_and_exit(agent, reason):
    """Save progress and cleanup"""
    print(f"\n{'=' * 70}")
    print(f"💾 SAVING PROGRESS (Reason: {reason})")
    print(f"{'=' * 70}")

    # Save forms discovered so far
    if hasattr(agent, 'master') and agent.master:
        try:
            agent.server.save_forms_list(agent.master)
            print(f"✅ Saved {len(agent.master)} forms to form_pages.json")
        except Exception as e:
            print(f"❌ Could not save forms: {e}")
    else:
        print("⚠️ No forms to save (agent.master is empty)")

    # Try to close browser
    if hasattr(agent, 'driver'):
        try:
            agent.driver.quit()
            print("✅ Browser closed cleanly")
        except:
            print("⚠️ Browser already closed or crashed")

    print(f"{'=' * 70}")
    print(f"🏁 Exiting gracefully with partial results")
    print(f"{'=' * 70}\n")


def run_crawler_with_protection(agent):
    """Run crawler with complete crash protection"""
    try:
        agent.crawl()

    # ===== TIMEOUT ISSUES =====
    except TimeoutException as e:
        print(f"\n⏰ TIMEOUT: Page load exceeded limit")
        print(f"   Error: {e}")
        save_and_exit(agent, "timeout")

    # ===== BROWSER CRASHES =====
    except (InvalidSessionIdException, SessionNotCreatedException) as e:
        print(f"\n🔥 BROWSER CRASH: Browser session died")
        print(f"   Error: {e}")
        save_and_exit(agent, "browser_crash")

    except NoSuchWindowException as e:
        print(f"\n🪟 WINDOW CLOSED: Browser window was closed")
        print(f"   Error: {e}")
        save_and_exit(agent, "window_closed")

    except WebDriverException as e:
        print(f"\n⚠️ WEBDRIVER ERROR: {e}")
        save_and_exit(agent, "webdriver_error")

    # ===== USER INTERRUPT =====
    except KeyboardInterrupt:
        print(f"\n⌨️ USER STOPPED: Ctrl+C pressed")
        save_and_exit(agent, "user_interrupt")

    # ===== ANY OTHER ERROR =====
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}")
        print(f"   Error: {e}")
        save_and_exit(agent, "unexpected_error")
        raise


def attempt_login(driver, username: str, password: str) -> bool:
    """
    Attempt to find and fill login form fields.
    Returns True if login was attempted, False if no login fields found.
    """
    try:
        # Look for username/email field
        username_field = None
        password_field = None
        
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
        
        for selector in username_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        username_field = el
                        break
                if username_field:
                    break
            except Exception:
                continue
        
        # Common selectors for password
        password_selectors = [
            'input[type="password"]'
        ]
        
        for selector in password_selectors:
            try:
                elements = driver.find_elements(By.CSS_SELECTOR, selector)
                for el in elements:
                    if el.is_displayed():
                        password_field = el
                        break
                if password_field:
                    break
            except Exception:
                continue
        
        # If both fields found, fill them
        if username_field and password_field:
            print("[Login] Found login fields, attempting to log in...")
            username_field.clear()
            username_field.send_keys(username)
            time.sleep(0.5)
            
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(0.5)
            
            # Find and click submit button
            submit_button = None
            submit_selectors = [
                'button[type="submit"]',
                'input[type="submit"]',
                'button:contains("Log in")',
                'button:contains("Sign in")',
                'button:contains("Login")',
                'button',  # fallback to any button
            ]
            
            for selector in submit_selectors:
                try:
                    elements = driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            el_text = (el.text or "").lower()
                            if "log" in el_text or "sign" in el_text or not el_text:
                                submit_button = el
                                break
                    if submit_button:
                        break
                except Exception:
                    continue
            
            if submit_button:
                submit_button.click()
                time.sleep(2.0)
                wait_dom_ready(driver)
                print("[Login] Login submitted successfully")
                return True
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
    username: str = None,
    password: str = None,
    logged_in: bool = True,
    headless: bool = False,
    hidden: bool = False,
    use_ai: bool = True,
    target_form_pages: Optional[List[str]] = None,
    api_key: str = None,
    max_pages: int = 20,
    max_depth: int = 4,
    discovery_only: bool = False,
    slow_mode: bool = False
):
    """
    Run the split architecture crawler:
    - Agent handles Selenium
    - Server handles AI and files
    - Both run in same process for now (easy migration to network later)
    """
    
    from webdriver_manager.chrome import ChromeDriverManager

    # Setup Chrome driver
    if headless:
        options = webdriver.ChromeOptions()
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
            print("running webdriver")
        except Exception:
            downloaded_binary_path = ChromeDriverManager().install()
            service = Service(executable_path=downloaded_binary_path)
            driver = webdriver.Chrome(service=service, options=options)
            driver.set_page_load_timeout(40)
    
    elif hidden:
        import undetected_chromedriver as uc
        options = webdriver.ChromeOptions()
        options.add_argument("--incognito")
        options.add_argument("--allow-running-insecure-content")
        options.add_argument('--disable-blink-features=AutomationControlled')
        driver = uc.Chrome(options=options, version_main=140, headless=False)
        driver.set_page_load_timeout(40)
    
    else:
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

    try:
        driver.get(start_url)
        wait_dom_ready(driver)

        # Wait for JavaScript to render
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC

        print("[Waiting] For JavaScript to render content...")
        try:
            WebDriverWait(driver, 30).until(
                EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
            )
            print("[Waiting] ✅ Content rendered!")
        except:
            print("[Waiting] ⚠️ Timeout - continuing anyway")

        time.sleep(2)

        # If credentials provided, attempt automatic login
        if username and password:
            login_attempted = attempt_login(driver, username, password)
            if login_attempted:
                print("[Main] Login completed, waiting for dashboard to load...")
                time.sleep(2.0)
                wait_dom_ready(driver)
        elif not logged_in:
            # Manual login
            input("Log in manually, then press Enter...")
        else:
            print("[Main] Assuming already logged in, proceeding with crawl...")
        
        # Save base URL after login
        base_url = driver.current_url
        print(f"[Main] Base URL saved: {base_url}")
        
        # ============================================================
        # CREATE SPLIT ARCHITECTURE: Server + Agent
        # ============================================================
        
        print("\n" + "="*70)
        print("🏗️  INITIALIZING SPLIT ARCHITECTURE")
        print("="*70)
        
        # Step 1: Create Server (no agent reference yet)
        print("[Main] Creating server-side crawler (AI + Files)...")
        server = FormPagesCrawler(
            agent=None,  # Will be set after agent is created
            project_name=project_name,
            use_ai=use_ai,
            api_key=api_key
        )
        
        # Step 2: Create Agent with server reference
        print("[Main] Creating agent-side crawler (Selenium)...")
        agent = AgentFormPages(
            driver=driver,
            start_url=driver.current_url,
            base_url=base_url,
            server=server,  # Agent knows about server
            project_name=project_name,
            max_pages=max_pages,
            max_depth=max_depth,
            use_ai=use_ai,
            target_form_pages=target_form_pages or [],
            discovery_only=discovery_only,
            slow_mode=slow_mode
        )
        
        # Step 3: Link server back to agent
        server.agent = agent  # Now server knows about agent
        
        print("[Main] ✅ Split architecture initialized!")
        print("="*70 + "\n")
        
        # Display configuration
        print(f"[Main] Starting crawl for project: {project_name}")
        print(f"[Main] AI-powered discovery: {'ENABLED' if use_ai else 'DISABLED'}")
        
        if target_form_pages:
            print(f"[Main] Target form pages: {target_form_pages}")
            print(f"[Main] Will crawl ONLY matching forms")
        else:
            print(f"[Main] Target form pages: ALL (no filter)")

        # Run crawler with crash protection
        run_crawler_with_protection(agent)

    except Exception as e:
        print(f"[Main] Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up
        if 'agent' in locals():
            try:
                agent.close_logger()
            except:
                pass

        driver.quit()
        print("[Main] Browser closed")


if __name__ == "__main__":
    import os

    # ============================================================
    # CONFIGURATION
    # ============================================================

    PROJECT_NAME = "orange_app"
    START_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"

    USERNAME = "Admin"
    PASSWORD = "admin123"
    LOGGED_IN = False

    USE_AI = True
    API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    if API_KEY:
        print(f"[Config] ✅ API Key loaded")
    else:
        print("[Config] ❌ No API key - disabling AI")
        USE_AI = False

    # PHASE 1: DISCOVERY ONLY
    DISCOVERY_ONLY = True  # Set to False for Phase 2 (full exploration)

    TARGET_FORMS = []  # Empty = discover ALL forms
    MAX_PAGES = 50
    MAX_DEPTH = 20

    SLOW_MODE = True

    HEADLESS = False
    HIDDEN = False

    # ============================================================
    # RUN THE SPLIT ARCHITECTURE CRAWLER
    # ============================================================

    run(
        start_url=START_URL,
        project_name=PROJECT_NAME,
        username=USERNAME,
        password=PASSWORD,
        logged_in=LOGGED_IN,
        headless=HEADLESS,
        hidden=HIDDEN,
        use_ai=USE_AI,
        target_form_pages=TARGET_FORMS,
        api_key=API_KEY,
        max_pages=MAX_PAGES,
        max_depth=MAX_DEPTH,
        discovery_only=DISCOVERY_ONLY,
        slow_mode=SLOW_MODE
    )
