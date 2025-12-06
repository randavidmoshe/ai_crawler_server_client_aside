# agent_form_pages_main.py
# AGENT SIDE - Main agent class with driver initialization
# Calls server for AI operations when needed

import os
import time
import logging
import platform
import base64
from typing import List, Optional, Dict
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

from agent_form_pages_utils import wait_dom_ready
from agent_form_pages_crawler import FormPagesCrawler


class Agent:
    """
    Agent running on customer machine.
    Manages WebDriver and executes crawling operations.
    Calls server for AI assistance when needed.
    """
    
    def __init__(self, screenshot_folder: Optional[str] = None):
        self.driver = None
        self.server = None  # Will be set when run_crawler is called
        
        # Screenshot folder configuration
        if screenshot_folder:
            # User provided a path (absolute or relative)
            if os.path.isabs(screenshot_folder):
                base_path = screenshot_folder
            else:
                # Relative path - make it relative to current working directory
                base_path = os.path.abspath(screenshot_folder)
        else:
            # Default to Desktop
            base_path = self._get_desktop_path()
        
        # Create automation_files folder structure
        automation_files_path = os.path.join(base_path, "automation_files")
        self.screenshots_path = os.path.join(automation_files_path, "screenshots")
        self.logs_path = os.path.join(automation_files_path, "logs")
        self.files_path = os.path.join(automation_files_path, "files")
        
        # Create folders if they don't exist
        os.makedirs(self.screenshots_path, exist_ok=True)
        os.makedirs(self.logs_path, exist_ok=True)
        os.makedirs(self.files_path, exist_ok=True)
        
        # Setup logging
        self._setup_logging()
        
        # Track if header has been printed
        self._header_printed = False
        
        print(f"[Agent] Screenshots: {self.screenshots_path}")
        print(f"[Agent] Logs: {self.logs_path}")
        print(f"[Agent] Files: {self.files_path}")
        
        self.info_logger.info("[Agent] Initialized")
    
    def _get_desktop_path(self) -> str:
        """
        Get Desktop path for Windows, Linux, and Mac
        
        Returns:
            Desktop path as string
        """
        system = platform.system()
        
        if system == "Windows":
            # Windows: C:\Users\{username}\Desktop
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        elif system == "Darwin":
            # macOS: /Users/{username}/Desktop
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        else:
            # Linux: /home/{username}/Desktop
            desktop = os.path.join(os.path.expanduser("~"), "Desktop")
        
        return desktop
    
    def _setup_logging(self):
        """Setup info and results logging"""
        timestamp = time.strftime("%Y%m%d_%H%M%S")
        
        info_log_path = os.path.join(self.logs_path, f"info_log_{timestamp}.log")
        results_log_path = os.path.join(self.logs_path, f"results_log_{timestamp}.log")
        
        self.info_logger = logging.getLogger('agent_info')
        self.info_logger.setLevel(logging.DEBUG)
        self.info_logger.handlers.clear()
        
        info_handler = logging.FileHandler(info_log_path)
        info_handler.setLevel(logging.DEBUG)
        info_formatter = logging.Formatter('%(asctime)s - %(levelname)s - %(message)s')
        info_handler.setFormatter(info_formatter)
        self.info_logger.addHandler(info_handler)
        
        self.results_logger = logging.getLogger('agent_results')
        self.results_logger.setLevel(logging.INFO)
        self.results_logger.handlers.clear()
        
        results_handler = logging.FileHandler(results_log_path)
        results_handler.setLevel(logging.INFO)
        results_formatter = logging.Formatter('%(asctime)s - %(message)s')
        results_handler.setFormatter(results_formatter)
        self.results_logger.addHandler(results_handler)
        
        self.info_logger.info("Agent logging initialized")
        self.results_logger.info("Agent results logging initialized")
    
    def start_driver(
        self, 
        browser_type: str = "chrome",
        headless: bool = False, 
        hidden: bool = False,
        electron_binary: Optional[str] = None,
        electron_debug_port: Optional[int] = None
    ):
        """
        Initialize WebDriver on agent machine.
        
        Args:
            browser_type: 'chrome', 'firefox', 'edge', or 'electron'
            headless: Run in headless mode
            hidden: Use undetected-chromedriver (Chrome only)
            electron_binary: Path to Electron binary
            electron_debug_port: Debug port for Electron app
        """
        self.info_logger.info(f"[Agent] Starting WebDriver (browser={browser_type}, headless={headless})")
        print(f"[Agent] Starting WebDriver (browser={browser_type}, headless={headless}, hidden={hidden})")
        
        # Store browser info for logging
        self.browser_type = browser_type
        self.headless = headless
        
        from webdriver_manager.chrome import ChromeDriverManager


        
        try:
            if browser_type.lower() == "chrome":
                if hidden:
                    # Use undetected-chromedriver
                    import undetected_chromedriver as uc
                    options = webdriver.ChromeOptions()
                    options.add_argument("--incognito")
                    options.add_argument("--allow-running-insecure-content")
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    self.driver = uc.Chrome(options=options, version_main=140, headless=False)
                    self.driver.set_page_load_timeout(40)
                else:
                    options = Options()
                    options.binary_location = '/opt/google/chrome/google-chrome'
                    
                    if headless:
                        options.add_argument('--headless=new')
                        options.add_argument('--disable-gpu')
                    
                    options.add_argument('--no-sandbox')
                    options.add_argument('--disable-dev-shm-usage')
                    options.add_argument('--window-size=1920,1080')
                    options.add_argument('--incognito')
                    options.add_argument('--allow-running-insecure-content')
                    options.add_argument('--disable-blink-features=AutomationControlled')
                    options.add_experimental_option("excludeSwitches", ["enable-automation"])
                    options.add_experimental_option('useAutomationExtension', False)

                    try:
                        service = Service()
                        self.driver = webdriver.Chrome(service=service, options=options)
                        self.driver.set_page_load_timeout(40)
                    except Exception:
                        downloaded_binary_path = ChromeDriverManager().install()
                        if downloaded_binary_path.endswith('THIRD_PARTY_NOTICES.chromedriver'):
                            import os
                            downloaded_binary_path = os.path.join(os.path.dirname(downloaded_binary_path),
                                                                  'chromedriver')
                            os.chmod(downloaded_binary_path, 0o755)
                        service = Service(executable_path=downloaded_binary_path)
                        self.driver = webdriver.Chrome(service=service, options=options)
                        self.driver.set_page_load_timeout(40)
            
            elif browser_type.lower() == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                
                self.driver = webdriver.Firefox(options=options)
                self.driver.set_page_load_timeout(40)
            
            elif browser_type.lower() == "edge":
                options = webdriver.EdgeOptions()
                if headless:
                    options.add_argument('--headless')
                
                self.driver = webdriver.Edge(options=options)
                self.driver.set_page_load_timeout(40)
            
            elif browser_type.lower() == "electron":
                # Electron support - uses ChromeDriver since Electron is Chromium-based
                options = webdriver.ChromeOptions()
                
                # Connect to already-running Electron app via debug port
                if electron_debug_port:
                    options.add_experimental_option("debuggerAddress", f"localhost:{electron_debug_port}")
                    self.driver = webdriver.Chrome(options=options)
                    self.info_logger.info(f"[Agent] Connected to Electron app on port {electron_debug_port}")
                
                # Launch Electron binary directly
                elif electron_binary and os.path.exists(electron_binary):
                    options.binary_location = electron_binary
                    self.driver = webdriver.Chrome(options=options)
                    self.info_logger.info(f"[Agent] Launched Electron from: {electron_binary}")
                
                else:
                    raise ValueError(
                        "Electron mode requires either electron_debug_port "
                        "(to connect to running app) or electron_binary "
                        "(to launch app)"
                    )
                
                self.driver.set_page_load_timeout(40)
            
            else:
                raise ValueError(f"Unsupported browser type: {browser_type}")
            
            self.info_logger.info("[Agent] ✅ WebDriver started successfully")
            print("[Agent] ✅ WebDriver started")
            return self.driver
            
        except Exception as e:
            error_msg = f"[Agent] ❌ Failed to start WebDriver: {e}"
            self.info_logger.error(error_msg)
            print(error_msg)
            raise
    
    def navigate_to(self, url: str, max_retries: int = 3):
        """Navigate to URL with retry logic"""
        self.info_logger.info(f"[Agent] Navigating to: {url}")
        print(f"[Agent] Navigating to: {url}")
        
        for attempt in range(1, max_retries + 1):
            try:
                self.driver.get(url)
                wait_dom_ready(self.driver)
                
                # Wait for JavaScript to render
                self.info_logger.info("[Agent] Waiting for JavaScript to render...")
                print("[Agent] Waiting for JavaScript to render...")
                try:
                    WebDriverWait(self.driver, 30).until(
                        EC.presence_of_element_located((By.CSS_SELECTOR, "input"))
                    )
                    self.info_logger.info("[Agent] ✅ Content rendered")
                    print("[Agent] ✅ Content rendered")
                except:
                    self.info_logger.warning("[Agent] ⚠️ Timeout - continuing anyway")
                    print("[Agent] ⚠️ Timeout - continuing anyway")
                
                time.sleep(2)
                return True
                
            except Exception as e:
                short_error = str(e).split('\n')[0]  # First line only, no stacktrace
                error_msg = f"Navigation failed (attempt {attempt}/{max_retries}): {short_error}"
                print(f"[Agent] ❌ {error_msg}")
                
                # Capture screenshot and log
                self.capture_screenshot(f"navigation_error_attempt_{attempt}")
                self.log_message(f"Navigation Error: {error_msg}", "error")
                
                if attempt < max_retries:
                    wait_time = 40
                    print(f"[Agent] Retrying in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # All retries failed - log and stop driver
                    self.log_message(f"Navigation failed after {max_retries} attempts. Stopping.", "error")
                    print(f"[Agent] ❌ Navigation failed after {max_retries} attempts")
                    self.stop_driver()
                    return False
        
        return False
    
    def attempt_login(self, username: str, password: str, project_name: str, server=None, max_retries: int = 3) -> bool:
        """
        Attempt automatic login using AI-generated steps from Server.
        
        Args:
            username: Username to login with
            password: Password to login with
            project_name: Project name for storing login stages
            server: Server instance for AI operations
            max_retries: Number of retry attempts
        """
        self.info_logger.info(f"[Agent] Attempting login as: {username}")
        print(f"[Agent] 🔐 Attempting login as: {username}")
        
        # Save login URL before any attempts
        login_url = self.driver.current_url
        print(f"[Agent] 🔐 Login URL: {login_url}")
        
        for attempt in range(1, max_retries + 1):
            try:
                # On retry, navigate back to login page
                if attempt > 1:
                    print(f"[Agent] 🔐 Navigating back to login page...")
                    self.driver.get(login_url)
                    time.sleep(2.0)
                    wait_dom_ready(self.driver)
                
                # Capture DOM and screenshot for Server
                page_html = self.driver.execute_script("return document.documentElement.outerHTML")
                
                screenshot_base64 = None
                try:
                    screenshot_base64 = self.driver.get_screenshot_as_base64()
                    print(f"[Agent] 📸 Captured login page screenshot")
                except Exception as e:
                    print(f"[Agent] ⚠️ Could not capture screenshot: {e}")
                
                # Call Server to get/create login steps
                if not server:
                    print("[Agent] ⚠️ No server - cannot generate login steps")
                    return False
                
                login_steps = server.create_login_stages(
                    project_name=project_name,
                    login_url=login_url,
                    page_html=page_html,
                    screenshot_base64=screenshot_base64,
                    username=username,
                    password=password
                )
                
                if not login_steps:
                    print("[Agent] ⚠️ No login steps received from Server")
                    return False
                
                print(f"[Agent] 🔐 Received {len(login_steps)} login steps from Server")
                
                # Execute login steps
                for i, step in enumerate(login_steps, 1):
                    action = step.get("action", "")
                    selector = step.get("selector", "")
                    value = step.get("value", "")
                    
                    print(f"[Agent] 🔐 Step {i}: {action}" + (f" on {selector}" if selector else ""))
                    
                    # Handle verification actions (no element needed)
                    if action == "wait_dom_ready":
                        time.sleep(1.0)
                        wait_dom_ready(self.driver)
                        print(f"[Agent] ✅ DOM is stable")
                        continue
                        
                    elif action == "verify_clickables":
                        min_count = int(value) if value else 3
                        clickable_count = self._count_clickables()
                        print(f"[Agent] 🔍 Found {clickable_count} clickable elements (minimum required: {min_count})")
                        if clickable_count < min_count:
                            raise Exception(f"Login verification failed: only {clickable_count} clickables found (need {min_count}+)")
                        print(f"[Agent] ✅ Login verified: {clickable_count} clickables found")
                        continue
                    
                    # For fill/click actions, find the element
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                    except Exception as e:
                        print(f"[Agent] ❌ Could not find element: {selector} - {e}")
                        raise  # Re-raise to trigger retry
                    
                    if action == "fill":
                        # Replace placeholders with actual values
                        actual_value = value.replace("{{username}}", username).replace("{{password}}", password)
                        element.clear()
                        element.send_keys(actual_value)
                        time.sleep(0.3)
                        print(f"[Agent] ✅ Filled: {selector}")
                        
                    elif action == "click":
                        element.click()
                        time.sleep(0.5)
                        print(f"[Agent] ✅ Clicked: {selector}")
                        
                    else:
                        print(f"[Agent] ⚠️ Unknown action: {action}")
                
                # Final wait for page to stabilize
                time.sleep(1.0)
                wait_dom_ready(self.driver)
                
                print("[Agent] ✅ Login steps completed")
                return True
                    
            except Exception as e:
                short_error = str(e).split('\n')[0]  # First line only, no stacktrace
                error_msg = f"Login failed (attempt {attempt}/{max_retries}): {short_error}"
                print(f"[Agent] ❌ {error_msg}")
                
                # Capture screenshot and log
                self.capture_screenshot(f"login_error_attempt_{attempt}")
                self.log_message(f"Login Error: {error_msg}", "error")
                
                if attempt < max_retries:
                    wait_time = 40
                    print(f"[Agent] Retrying login in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # All retries failed - log and stop driver
                    self.log_message(f"Login failed after {max_retries} attempts. Stopping.", "error")
                    print(f"[Agent] ❌ Login failed after {max_retries} attempts")
                    self.stop_driver()
                    return False
        
        return False
    
    def attempt_logout(self, username: str, login_url: str, project_name: str, server, max_retries: int = 3) -> bool:
        """
        Attempt automatic logout using AI-generated steps.
        
        Args:
            username: Username that was logged in
            login_url: URL of the login page (for reference)
            project_name: Project name
            server: Server instance for AI operations
            max_retries: Number of retry attempts
            
        Returns:
            True if logout steps executed, False otherwise
        """
        print(f"[Agent] 🚪 Attempting logout...")
        
        for attempt in range(1, max_retries + 1):
            try:
                # Get current page info
                logout_url = self.driver.current_url
                print(f"[Agent] 🚪 Logout URL: {logout_url}")
                
                # Capture page HTML
                page_html = self.driver.execute_script("return document.documentElement.outerHTML")
                
                # Capture screenshot
                screenshot_base64 = None
                try:
                    screenshot_base64 = self.driver.get_screenshot_as_base64()
                    print(f"[Agent] 📸 Captured page screenshot for logout")
                except Exception as e:
                    print(f"[Agent] ⚠️ Could not capture screenshot: {e}")
                
                # Ask server for logout steps
                if not server:
                    print("[Agent] ⚠️ No server connection - cannot get logout steps")
                    return False
                
                logout_steps = server.create_logout_stages(
                    project_name=project_name,
                    logout_url=logout_url,
                    page_html=page_html,
                    screenshot_base64=screenshot_base64,
                    username=username,
                    login_url=login_url
                )
                
                if not logout_steps:
                    print("[Agent] ⚠️ No logout steps received from Server")
                    return False
                
                print(f"[Agent] 🚪 Received {len(logout_steps)} logout steps from Server")
                
                # Execute logout steps
                for i, step in enumerate(logout_steps):
                    action = step.get("action", "")
                    selector = step.get("selector", "")
                    
                    print(f"[Agent] 🚪 Step {i+1}: {action}" + (f" on {selector}" if selector else ""))
                    
                    # Handle verification actions (no element needed)
                    if action == "wait_dom_ready":
                        time.sleep(1.0)
                        wait_dom_ready(self.driver)
                        print(f"[Agent] ✅ DOM is stable")
                        continue
                        
                    elif action == "verify_login_page":
                        if self._is_login_page():
                            print(f"[Agent] ✅ Logout verified: back at login page")
                        else:
                            raise Exception("Logout verification failed: not at login page (no username/password fields found)")
                        continue
                    
                    # For click actions, find the element
                    try:
                        element = self.driver.find_element(By.CSS_SELECTOR, selector)
                        
                        if action == "click":
                            element.click()
                            print(f"[Agent] ✅ Clicked: {selector}")
                            time.sleep(1.0)
                            wait_dom_ready(self.driver)
                        
                    except Exception as e:
                        print(f"[Agent] ⚠️ Failed step {i+1}: {e}")
                        raise  # Re-raise to trigger retry
                
                print("[Agent] ✅ Logout steps completed")
                
                # Log logout to results logger
                self.results_logger.info(f"Logout: User '{username}' completed")
                self.results_logger.info("---------------------------------------------------")
                
                return True
                
            except Exception as e:
                short_error = str(e).split('\n')[0]  # First line only, no stacktrace
                error_msg = f"Logout failed (attempt {attempt}/{max_retries}): {short_error}"
                print(f"[Agent] ❌ {error_msg}")
                
                # Capture screenshot and log
                self.capture_screenshot(f"logout_error_attempt_{attempt}")
                self.log_message(f"Logout Error: {error_msg}", "error")
                
                if attempt < max_retries:
                    wait_time = 40
                    print(f"[Agent] Retrying logout in {wait_time} seconds...")
                    time.sleep(wait_time)
                else:
                    # All retries failed - log but continue (logout is at the end)
                    self.log_message(f"Logout failed after {max_retries} attempts. Continuing shutdown.", "error")
                    print(f"[Agent] ⚠️ Logout failed after {max_retries} attempts, continuing...")
                    return False
        
        return False
    
    def run_crawler(
        self,
        start_url: str,
        project_name: str,
        username: str = None,
        password: str = None,
        logged_in: bool = True,
        target_form_pages: Optional[List[str]] = None,
        server=None,  # Server reference for AI callbacks
        max_depth: int = 4,
        discovery_only: bool = False,
        slow_mode: bool = False
    ):
        """
        Run the crawler using existing FormPagesCrawler.
        
        Args:
            server: Server instance to call for AI operations
        """
        if not self.driver:
            raise Exception("Driver not started. Call start_driver() first.")
        
        # Store server reference
        self.server = server
        
        print(f"[Agent] Starting crawler for project: {project_name}")
        print(f"[Agent] Server connection: {'✅ Connected' if server else '❌ No server'}")
        
        # Log startup info to results logger (only on first cycle)
        if not self._header_printed:
            self.results_logger.info("="*70)
            self.results_logger.info(f"STARTED LOCATING FORM PAGES - Project: {project_name}")
            self.results_logger.info(f"Start URL: {start_url}")
            self.results_logger.info(f"Browser: {self.browser_type.upper()} (Headless: {self.headless})")
            self.results_logger.info("="*70)
            self._header_printed = True
        
        # Navigate to start URL
        if not self.navigate_to(start_url):
            print("[Agent] ❌ Navigation failed - stopping crawler")
            return
        
        # Handle login
        if username and password:
            # Log login to results logger
            self.results_logger.info(f"Login: User '{username}' at {start_url}")
            self.results_logger.info("---------------------------------------------------")
            
            login_attempted = self.attempt_login(username, password, project_name, server)
            if not login_attempted:
                print("[Agent] ❌ Login failed - stopping crawler")
                return
            
            print("[Agent] Login completed, waiting for dashboard...")
            time.sleep(2.0)
            wait_dom_ready(self.driver)
        elif not logged_in:
            input("[Agent] Log in manually, then press Enter...")
        else:
            print("[Agent] Assuming already logged in")
        
        # Save base URL
        try:
            base_url = self.driver.current_url
            print(f"[Agent] Base URL: {base_url}")
        except Exception as e:
            short_error = str(e).split('\n')[0]
            print(f"[Agent] ❌ Browser session lost: {short_error}")
            self.log_message(f"Browser session lost before crawler start: {short_error}", "error")
            return
        
        # Create crawler instance
        crawler = FormPagesCrawler(
            self.driver,
            start_url=base_url,
            base_url=base_url,
            project_name=project_name,
            max_depth=max_depth,
            target_form_pages=target_form_pages or [],
            server=server,  # Pass server to crawler for AI operations
            discovery_only=discovery_only,
            slow_mode=slow_mode,
            username=username,  # Pass username for tagging forms
            login_url=start_url,  # Pass login URL for tagging forms
            agent=self  # Pass agent for logging
        )
        
        # Run the crawler
        print("[Agent] Running crawler...")
        crawler.crawl()
        
        print("[Agent] ✅ Crawler completed")
        
        # Attempt logout after crawling
        if username and server:
            self.attempt_logout(
                username=username,
                login_url=start_url,
                project_name=project_name,
                server=server
            )
        
        # Cleanup logger
        try:
            crawler.close_logger()
        except:
            pass
    
    def run_crawler_with_multiple_logins(
        self,
        login_configs: list,
        project_name: str,
        logged_in: bool = True,
        target_form_pages: Optional[List[str]] = None,
        server=None,
        max_depth: int = 4,
        discovery_only: bool = False,
        slow_mode: bool = False
    ):
        """
        Run crawler with multiple login configurations.
        
        Args:
            login_configs: List of dicts with 'url', 'username' (optional), 'password' (optional)
            project_name: Project name
            logged_in: Whether already logged in
            target_form_pages: Target form pages
            server: Server instance
            max_depth: Max crawl depth
            discovery_only: Discovery mode
            slow_mode: Slow mode
        """
        if not self.driver:
            raise Exception("Driver not started. Call start_driver() first.")
        
        print(f"\n[Agent] Running crawler with {len(login_configs)} login configuration(s)")
        
        for idx, config in enumerate(login_configs, 1):
            url = config.get("url")
            username = config.get("username")
            password = config.get("password")
            
            print(f"\n{'='*70}")
            print(f"[Agent] Configuration {idx}/{len(login_configs)}")
            if username:
                print(f"[Agent] URL: {url}")
                print(f"[Agent] Username: {username}")
            else:
                print(f"[Agent] URL: {url} (No login)")
            print(f"{'='*70}\n")
            
            # Run crawler for this configuration
            self.run_crawler(
                start_url=url,
                project_name=project_name,
                username=username,
                password=password,
                logged_in=logged_in,
                target_form_pages=target_form_pages,
                server=server,
                max_depth=max_depth,
                discovery_only=discovery_only,
                slow_mode=slow_mode
            )
            
            print(f"\n[Agent] ✅ Completed configuration {idx}/{len(login_configs)}")
        
        print(f"\n{'='*70}")
        print(f"[Agent] ✅ All {len(login_configs)} configuration(s) completed")
        print(f"{'='*70}\n")
    
    def stop_driver(self):
        """Stop WebDriver"""
        if self.driver:
            print("[Agent] Stopping WebDriver")
            try:
                self.driver.quit()
                print("[Agent] ✅ WebDriver stopped")
            except:
                print("[Agent] ⚠️ WebDriver already stopped")
            self.driver = None
    
    def health_check(self) -> dict:
        """
        Check agent health status (useful for future network communication)
        
        Returns:
            Health status dictionary
        """
        return {
            "status": "ok",
            "driver_active": self.driver is not None,
            "server_connected": self.server is not None
        }
    
    def log_message(self, message: str, level: str = "info"):
        """
        Log a message to both agent loggers
        
        Args:
            message: The message to log
            level: Log level - "info", "warning", "error", "debug"
        """
        # Log to info logger
        if level == "warning":
            self.info_logger.warning(message)
        elif level == "error":
            self.info_logger.error(message)
        elif level == "debug":
            self.info_logger.debug(message)
        else:
            self.info_logger.info(message)
        
        # Log to results logger
        if level == "warning":
            self.results_logger.warning(message)
        elif level == "error":
            self.results_logger.error(message)
        elif level == "debug":
            self.results_logger.debug(message)
        else:
            self.results_logger.info(message)
        
        # Add separator after every message in results logger
        self.results_logger.info("---------------------------------------------------")
    
    def log_error(self, message: str, screenshot_description: str = None):
        """
        Log error message and optionally take screenshot
        
        Args:
            message: The error message to log
            screenshot_description: If provided, take screenshot with this description
        """
        self.log_message(message, "error")
        if screenshot_description and self.driver:
            self.capture_screenshot(screenshot_description)
    
    def _count_clickables(self) -> int:
        """
        Count visible clickable elements on the page (links, buttons).
        Used for login verification - a logged-in page typically has 3+ clickables.
        """
        try:
            clickables = self.driver.find_elements(
                By.CSS_SELECTOR, 
                "a[href], button, [role='button'], [onclick]"
            )
            visible_count = 0
            for el in clickables:
                try:
                    if el.is_displayed():
                        visible_count += 1
                except:
                    pass
            return visible_count
        except Exception as e:
            print(f"[Agent] ⚠️ Error counting clickables: {e}")
            return 0
    
    def _is_login_page(self) -> bool:
        """
        Check if current page is a login page by looking for username/password fields.
        Used for logout verification.
        """
        try:
            # Must have visible password field
            password_fields = self.driver.find_elements(By.CSS_SELECTOR, "input[type='password']")
            has_password = any(el.is_displayed() for el in password_fields)
            
            if not has_password:
                return False
            
            # Check for username/email field
            login_selectors = [
                "input[name*='user']", "input[name*='login']", "input[name*='email']",
                "input[id*='user']", "input[id*='login']", "input[id*='email']",
            ]
            for selector in login_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            return True
                except:
                    pass
            return False
        except Exception as e:
            print(f"[Agent] ⚠️ Error checking login page: {e}")
            return False
    
    def capture_screenshot(self, scenario_description: str = "screenshot", encode_base64: bool = True, save_to_folder: bool = True) -> Dict:
        """
        Capture screenshot and optionally save to configured folder with timestamp
        
        Args:
            scenario_description: Description of what was happening (e.g., "ui_defect_claim")
            encode_base64: If True, also return base64 encoded string (for backward compatibility)
            save_to_folder: If True, save to disk folder. If False, only return base64 (for AI analysis)
            
        Returns:
            Dict with screenshot data and file path (if saved)
        """
        try:
            from datetime import datetime
            import re
            
            # Get screenshot as PNG bytes
            screenshot_png = self.driver.get_screenshot_as_png()
            
            # Prepare response
            result = {
                "success": True
            }
            
            # Save to folder if requested
            if save_to_folder:
                # Sanitize scenario description for filename
                # Remove special chars, replace spaces with underscores, limit length
                sanitized = re.sub(r'[^\w\s-]', '', scenario_description)
                sanitized = re.sub(r'[-\s]+', '_', sanitized)
                sanitized = sanitized.strip('_').lower()[:50]  # Limit to 50 chars
                
                # Generate timestamp: YYYY-MM-DD_HH-MM-SS
                timestamp = datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
                
                # Build filename
                filename = f"{sanitized}_{timestamp}.png"
                filepath = os.path.join(self.screenshots_path, filename)
                
                # Save screenshot to file
                with open(filepath, 'wb') as f:
                    f.write(screenshot_png)
                
                print(f"[Agent] 📸 Screenshot saved: {filepath}")
                
                result["filepath"] = filepath
                result["filename"] = filename
                result["format"] = "file"
            else:
                # Not saving to folder - just for AI analysis
                result["format"] = "memory"
            
            # Include base64 or binary
            if encode_base64:
                screenshot_b64 = base64.b64encode(screenshot_png).decode('utf-8')
                result["screenshot"] = screenshot_b64
                if save_to_folder:
                    result["format"] = "file+base64"
                else:
                    result["format"] = "base64"
            else:
                result["screenshot"] = screenshot_png
                if save_to_folder:
                    result["format"] = "file+binary"
                else:
                    result["format"] = "binary"
            
            return result
            
        except Exception as e:
            return {"success": False, "error": str(e)}
