# ai_form_explorer_main.py
# Version 3 - Complete with all features
# Runner that launches Selenium and calls the crawler
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
from form_pages_crawler import FormPagesCrawler


import logging
from inits.log import Logger
import inits.environment as environment
environment.test_mode = "single_test_first"  # or create a new "crawler" mode
my_log = Logger(is_full_test=True)
my_log.init_logger()

# Set up simple logging configuration
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(message)s',
    datefmt='%m/%d/%Y %H:%M:%S'
)


def save_and_exit(crawler, reason):
    """Save progress and cleanup"""
    print(f"\n{'=' * 70}")
    print(f"💾 SAVING PROGRESS (Reason: {reason})")
    print(f"{'=' * 70}")

    # Save forms discovered so far
    if hasattr(crawler, 'master') and crawler.master:
        try:
            crawler._save_forms_list(crawler.master)
            print(f"✅ Saved {len(crawler.master)} forms to form_pages.json")
        except Exception as e:
            print(f"❌ Could not save forms: {e}")
    else:
        print("⚠️ No forms to save (crawler.master is empty)")

    # Try to close browser
    if hasattr(crawler, 'driver'):
        try:
            crawler.driver.quit()
            print("✅ Browser closed cleanly")
        except:
            print("⚠️ Browser already closed or crashed")

    print(f"{'=' * 70}")
    print(f"🏁 Exiting gracefully with partial results")
    print(f"{'=' * 70}\n")


def run_crawler_with_protection(crawler):
    """Run crawler with complete crash protection"""
    try:
        crawler.crawl()

    # ===== TIMEOUT ISSUES =====
    except TimeoutException as e:
        print(f"\n⏰ TIMEOUT: Page load exceeded limit")
        print(f"   Error: {e}")
        save_and_exit(crawler, "timeout")

    # ===== BROWSER CRASHES =====
    except (InvalidSessionIdException, SessionNotCreatedException) as e:
        print(f"\n🔥 BROWSER CRASH: Browser session died")
        print(f"   Error: {e}")
        save_and_exit(crawler, "browser_crash")

    except NoSuchWindowException as e:
        print(f"\n🪟 WINDOW CLOSED: Browser window was closed")
        print(f"   Error: {e}")
        save_and_exit(crawler, "window_closed")

    except WebDriverException as e:
        # Catch all other WebDriver issues
        print(f"\n⚠️ WEBDRIVER ERROR: {e}")
        save_and_exit(crawler, "webdriver_error")

    # ===== USER INTERRUPT =====
    except KeyboardInterrupt:
        print(f"\n⌨️ USER STOPPED: Ctrl+C pressed")
        save_and_exit(crawler, "user_interrupt")

    # ===== ANY OTHER ERROR =====
    except Exception as e:
        print(f"\n❌ UNEXPECTED ERROR: {type(e).__name__}")
        print(f"   Error: {e}")
        save_and_exit(crawler, "unexpected_error")
        raise  # Re-raise so you can see the full traceback

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
    use_ai: bool = True,
    target_form_pages: Optional[List[str]] = None,
    api_key: str = None,
    max_pages: int = 20,
    max_depth: int = 4,
    discovery_only: bool = False,
    slow_mode: bool = False

):
    # Set test mode for logging


    # Initialize logging system
    logger = logging.getLogger('init_logger.crawler_initiator')
    result_logger_gui = logging.getLogger('init_result_logger_gui.crawler_initiator')

    result_logger_gui.info("------------------------------------------------")
    result_logger_gui.info(f"Starting Crawling on project : '{project_name}'")
    result_logger_gui.info("------------------------------------------------\n")


    # ADD THESE LINES AT THE START
    # If no API key passed, try to get from environment
    if api_key is None and use_ai:
        api_key = os.environ.get("ANTHROPIC_API_KEY")
        if api_key:
            result_logger_gui.info("[Main] Using API key from environment")
            logger.info(f"[Main] API key length: {len(api_key)}")
        else:
            result_logger_gui.info("[Main] Warning: No API key found")

    """
    Main runner function with all Ver 3 features.
    
    Args:
        start_url: The URL to start crawling from (post-login URL or login page)
        project_name: Name of the project for organizing outputs
        username: Username for login (optional)
        password: Password for login (optional)
        logged_in: If True and no credentials provided, assumes already logged in
        headless: Run browser in headless mode
        use_ai: Use AI (Claude) for intelligent form discovery (requires ANTHROPIC_API_KEY)
        target_form_pages: List of specific form page names to crawl. 
                          If None or empty, crawls all forms.
                          Examples: ["Create User", "Edit Profile"] or ["user", "profile"]
    
    Features:
        ✅ Target form pages filtering
        ✅ Smart AND/OR hiding conditions detection
        ✅ Grid column verification (3-stage flow)
        ✅ Enhanced gui_pre_verification_actions with field values
        ✅ Edit & Verify capture after each route
        ✅ Base URL navigation between forms
        ✅ Extended actions as dicts
        ✅ All CSS fields left empty (only AI stages filled)
    """
    #opts = webdriver.ChromeOptions()
    #if headless:
    #    opts.add_argument("--headless=new")
    #opts.add_argument("--window-size=1400,900")
    #driver = webdriver.Chrome(options=opts)

    from webdriver_manager.chrome import ChromeDriverManager

    if headless:
        options = webdriver.ChromeOptions()

        # Add headless mode - ADD THIS
        options.add_argument('--headless=new')  # Use new headless mode (Chrome 109+)
        # OR for older Chrome versions:
        # options.add_argument('--headless')

        # Other common headless options (recommended)
        options.add_argument('--disable-gpu')  # Disable GPU acceleration
        options.add_argument('--no-sandbox')  # Bypass OS security model
        options.add_argument('--disable-dev-shm-usage')  # Overcome limited resource problems
        options.add_argument('--window-size=1920,1080')  # Set viewport size

        # Then create the driver as before
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
    else:
        chrome_web_driver: WebDriver
        options = webdriver.ChromeOptions()
        options.add_argument("--incognito")
        options.add_argument("--allow-running-insecure-content")

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
        time.sleep(15)


        # If credentials provided, attempt automatic login
        if username and password:
            login_attempted = attempt_login(driver, username, password)
            if login_attempted:
                print("[Main] Login completed, waiting for dashboard to load...")
                result_logger_gui.info("[Main] Login completed, waiting for dashboard to load...")
                time.sleep(2.0)
                wait_dom_ready(driver)
        elif not logged_in:
            # Manual login
            input("Log in manually, then press Enter...")
        else:
            print("[Main] Assuming already logged in, proceeding with crawl...")
        
        # Save base URL after login for navigation between forms
        base_url = driver.current_url
        print(f"[Main] Base URL saved: {base_url}")
        
        # Start crawling
        print(f"[Main] Starting crawl for project: {project_name}")
        result_logger_gui.info(f"[Main] Starting crawl for project: {project_name}")
        print(f"[Main] AI-powered discovery: {'ENABLED' if use_ai else 'DISABLED'}")
        result_logger_gui.info(f"[Main] AI-powered discovery: {'ENABLED' if use_ai else 'DISABLED'}")
        
        # Display target form pages info
        if target_form_pages:
            print(f"[Main] Target form pages: {target_form_pages}")
            print(f"[Main] Will crawl ONLY matching forms")
        else:
            print(f"[Main] Target form pages: ALL (no filter)")

        crawler = FormPagesCrawler(
            driver,
            start_url=driver.current_url,
            base_url=base_url,
            project_name=project_name,
            max_pages=max_pages,
            max_depth=max_depth,
            use_ai=use_ai,
            target_form_pages=target_form_pages or [],
            api_key=api_key,
            discovery_only=discovery_only,
            slow_mode=slow_mode
        )

        # Run crawler with crash protection
        run_crawler_with_protection(crawler)
        

    except Exception as e:
        print(f"[Main] Error during execution: {e}")
        result_logger_gui.info(f"[Main] Error during execution: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Clean up logger (always runs, even if error occurs)
        if 'crawler' in locals():
            try:
                crawler.close_logger()
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
    #PROJECT_NAME = "para_bank"
    START_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"
    #START_URL = "https://parabank.parasoft.com/parabank/overview.htm"

    #USERNAME = "ranchook"
    #PASSWORD = "abcdefgh1"
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
    MAX_PAGES = 50  # How many forms to find
    MAX_DEPTH = 20  # How deep to explore

    SLOW_MODE= True

    HEADLESS = False

    # ============================================================
    # RUN THE CRAWLER
    # ============================================================

    run(
        start_url=START_URL,
        project_name=PROJECT_NAME,
        username=USERNAME,
        password=PASSWORD,
        logged_in=LOGGED_IN,
        headless=HEADLESS,
        use_ai=USE_AI,
        target_form_pages=TARGET_FORMS,
        api_key=API_KEY,
        max_pages=MAX_PAGES,
        max_depth=MAX_DEPTH,
        discovery_only=DISCOVERY_ONLY,
        slow_mode=SLOW_MODE
    )
