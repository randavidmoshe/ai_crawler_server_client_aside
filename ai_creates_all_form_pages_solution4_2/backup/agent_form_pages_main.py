# agent_form_pages_main.py
# AGENT SIDE - Main agent class with driver initialization
# Calls server for AI operations when needed

import os
import time
import logging
import platform
from typing import List, Optional
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
    
    def navigate_to(self, url: str):
        """Navigate to URL"""
        self.info_logger.info(f"[Agent] Navigating to: {url}")
        print(f"[Agent] Navigating to: {url}")
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
    
    def attempt_login(self, username: str, password: str) -> bool:
        """Attempt automatic login"""
        self.info_logger.info(f"[Agent] Attempting login as: {username}")
        print(f"[Agent] Attempting login as: {username}")
        
        try:
            # Find username field
            username_field = None
            username_selectors = [
                'input[type="email"]',
                'input[type="text"][name*="user"]',
                'input[type="text"][name*="email"]',
                'input[name="username"]',
                'input[name="email"]'
            ]
            
            for selector in username_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
                    for el in elements:
                        if el.is_displayed():
                            username_field = el
                            break
                    if username_field:
                        break
                except Exception:
                    continue
            
            # Find password field
            password_field = None
            try:
                elements = self.driver.find_elements(By.CSS_SELECTOR, 'input[type="password"]')
                for el in elements:
                    if el.is_displayed():
                        password_field = el
                        break
            except Exception:
                pass
            
            if username_field and password_field:
                username_field.clear()
                username_field.send_keys(username)
                time.sleep(0.5)
                
                password_field.clear()
                password_field.send_keys(password)
                time.sleep(0.5)
                
                # Find submit button
                submit_button = None
                submit_selectors = [
                    'button[type="submit"]',
                    'input[type="submit"]',
                    'button'
                ]
                
                for selector in submit_selectors:
                    try:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
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
                    wait_dom_ready(self.driver)
                    print("[Agent] ✅ Login submitted")
                    return True
                else:
                    print("[Agent] ⚠️ Could not find submit button")
                    return False
            else:
                print("[Agent] ⚠️ No login fields detected")
                return False
                
        except Exception as e:
            print(f"[Agent] ❌ Login error: {e}")
            return False
    
    def run_crawler(
        self,
        start_url: str,
        project_name: str,
        username: str = None,
        password: str = None,
        logged_in: bool = True,
        use_ai: bool = True,
        target_form_pages: Optional[List[str]] = None,
        api_key: str = None,
        server=None,  # Server reference for AI callbacks
        max_pages: int = 20,
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
        
        # Navigate to start URL
        self.navigate_to(start_url)
        
        # Handle login
        if username and password:
            login_attempted = self.attempt_login(username, password)
            if login_attempted:
                print("[Agent] Login completed, waiting for dashboard...")
                time.sleep(2.0)
                wait_dom_ready(self.driver)
        elif not logged_in:
            input("[Agent] Log in manually, then press Enter...")
        else:
            print("[Agent] Assuming already logged in")
        
        # Save base URL
        base_url = self.driver.current_url
        print(f"[Agent] Base URL: {base_url}")
        
        # Create crawler instance
        # NOTE: Crawler will need to be updated to use server for AI calls
        crawler = FormPagesCrawler(
            self.driver,
            start_url=self.driver.current_url,
            base_url=base_url,
            project_name=project_name,
            max_pages=max_pages,
            max_depth=max_depth,
            use_ai=use_ai,
            target_form_pages=target_form_pages or [],
            api_key=api_key,
            server=server,  # Pass server to crawler
            discovery_only=discovery_only,
            slow_mode=slow_mode
        )
        
        # Run the crawler
        print("[Agent] Running crawler...")
        crawler.crawl()
        
        print("[Agent] ✅ Crawler completed")
        
        # Cleanup logger
        try:
            crawler.close_logger()
        except:
            pass
    
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
