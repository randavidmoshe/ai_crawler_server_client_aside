# agent_form_pages.py
# AGENT SIDE - All Selenium WebDriver Operations
# This file runs on the customer's network and has access to internal QA environments
# Specialized version for Form Pages Discovery Project

import os
import time
import hashlib
import base64
import logging
from typing import Dict, Optional, Any, List
from bs4 import BeautifulSoup

from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service as ChromeService, Service
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.common.exceptions import (
    NoSuchElementException,
    TimeoutException,
    ElementClickInterceptedException,
    StaleElementReferenceException,
    NoAlertPresentException
)
from webdriver_manager.chrome import ChromeDriverManager

try:
    from reportlab.pdfgen import canvas
    from reportlab.lib.pagesizes import letter
except ImportError:
    canvas = None

try:
    from PIL import Image, ImageDraw, ImageFont
except ImportError:
    Image = None

try:
    from openpyxl import Workbook
except ImportError:
    Workbook = None

try:
    from docx import Document
except ImportError:
    Document = None


class AgentSelenium:
    """
    Agent-side Selenium operations
    Handles all browser automation, DOM extraction, and step execution
    """
    
    def __init__(self, screenshot_folder: Optional[str] = None):
        self.driver = None
        self.shadow_root_context = None
        
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
    
    def _clean_error_message(self, error: Exception) -> str:
        """
        Extract clean error message without stacktrace
        
        Args:
            error: Exception object
            
        Returns:
            Clean error message (first line only, no stacktrace)
        """
        error_str = str(error)
        
        # Split by common stacktrace indicators
        if 'Stacktrace:' in error_str:
            error_str = error_str.split('Stacktrace:')[0].strip()
        
        if '\n' in error_str:
            # Take only first line
            error_str = error_str.split('\n')[0].strip()
        
        return error_str
    
    def _get_desktop_path(self) -> str:
        """
        Get Desktop path for Windows, Linux, and Mac
        
        Returns:
            Desktop path as string
        """
        import platform
        
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
    
    def log_test_start(self, config: Dict):
        """Log test start configuration to both logs"""
        self.info_logger.info("="*70)
        self.info_logger.info("TEST STARTED")
        self.info_logger.info(f"Test URL: {config.get('test_url', 'N/A')}")
        self.info_logger.info(f"Form Page Name: {config.get('form_page_name', 'N/A')}")
        self.info_logger.info(f"Browser: {config.get('browser', 'N/A')}")
        self.info_logger.info(f"Headless: {config.get('headless', 'N/A')}")
        self.info_logger.info(f"UI Verification: {config.get('enable_ui_verification', 'N/A')}")
        self.info_logger.info(f"Screenshot Folder: {config.get('screenshot_folder', 'N/A')}")
        self.info_logger.info(f"Test Cases File: {config.get('test_cases_file', 'N/A')}")
        self.info_logger.info(f"Max Retries: {config.get('max_retries', 'N/A')}")
        self.info_logger.info("="*70)
        
        self.results_logger.info("="*70)
        self.results_logger.info("TEST STARTED")
        self.results_logger.info(f"Test URL: {config.get('test_url', 'N/A')}")
        self.results_logger.info(f"Form Page Name: {config.get('form_page_name', 'N/A')}")
        self.results_logger.info(f"Browser: {config.get('browser', 'N/A')}")
        self.results_logger.info(f"Headless: {config.get('headless', 'N/A')}")
        self.results_logger.info(f"UI Verification: {config.get('enable_ui_verification', 'N/A')}")
        self.results_logger.info(f"Screenshot Folder: {config.get('screenshot_folder', 'N/A')}")
        self.results_logger.info(f"Test Cases File: {config.get('test_cases_file', 'N/A')}")
        self.results_logger.info(f"Max Retries: {config.get('max_retries', 'N/A')}")
        self.results_logger.info("="*70)
        
    def log_message(self, message: str, level: str = "info"):
        """
        Log a message to both agent loggers
        
        Args:
            message: The message to log
            level: Log level - "info", "warning", "error", "debug"
        """
        log_methods = {
            "debug": (self.info_logger.debug, None),
            "info": (self.info_logger.info, self.results_logger.info),
            "warning": (self.info_logger.warning, self.results_logger.warning),
            "error": (self.info_logger.error, self.results_logger.error)
        }
        
        info_method, results_method = log_methods.get(level.lower(), (self.info_logger.info, self.results_logger.info))
        info_method(message)
        if results_method:
            results_method(message)
    
    # ========================================================================
    # BROWSER INITIALIZATION
    # ========================================================================
    
    def initialize_browser(
        self,
        browser_type: str = "chrome",
        headless: bool = False,
        hidden: bool = False
    ) -> Dict:
        """
        Initialize browser driver
        
        Args:
            browser_type: "chrome", "firefox", or "edge"
            headless: Run browser without UI
            hidden: Hide browser window (Windows only)
            
        Returns:
            Dict with success and message
        """
        try:
            if browser_type == "chrome":
                options = Options()
                if headless:
                    options.add_argument("--headless")
                    options.add_argument("--disable-gpu")
                options.add_argument("--no-sandbox")
                options.add_argument("--disable-dev-shm-usage")
                options.add_argument("--start-maximized")
                options.add_argument("--disable-blink-features=AutomationControlled")
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                service = ChromeService(ChromeDriverManager().install())
                self.driver = webdriver.Chrome(service=service, options=options)
                
            elif browser_type == "firefox":
                from selenium.webdriver.firefox.options import Options as FirefoxOptions
                options = FirefoxOptions()
                if headless:
                    options.add_argument("--headless")
                service = FirefoxService()
                self.driver = webdriver.Firefox(service=service, options=options)
                
            elif browser_type == "edge":
                from selenium.webdriver.edge.options import Options as EdgeOptions
                options = EdgeOptions()
                if headless:
                    options.add_argument("--headless")
                service = EdgeService()
                self.driver = webdriver.Edge(service=service, options=options)
                
            else:
                return {"success": False, "error": f"Unsupported browser: {browser_type}"}
            
            self.driver.maximize_window()
            self.info_logger.info(f"Browser initialized: {browser_type}, headless={headless}")
            
            return {"success": True, "message": f"{browser_type} initialized"}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            self.info_logger.error(f"Browser initialization failed: {clean_error}")
            return {"success": False, "error": clean_error}
    
    def close_browser(self) -> Dict:
        """Close browser"""
        try:
            if self.driver:
                self.driver.quit()
                self.info_logger.info("Browser closed successfully")
                return {"success": True}
            return {"success": False, "error": "No browser to close"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # NAVIGATION
    # ========================================================================
    
    def navigate_to_url(self, url: str, timeout: int = 30) -> Dict:
        """
        Navigate to URL
        
        Args:
            url: Target URL
            timeout: Page load timeout in seconds
            
        Returns:
            Dict with success and current URL
        """
        try:
            self.driver.set_page_load_timeout(timeout)
            self.driver.get(url)
            time.sleep(1)
            self.info_logger.info(f"Navigated to: {url}")
            return {"success": True, "url": self.driver.current_url}
        except TimeoutException:
            self.info_logger.warning(f"Navigation timeout for: {url}")
            return {"success": False, "error": "Page load timeout"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            self.info_logger.error(f"Navigation failed: {clean_error}")
            return {"success": False, "error": clean_error}
    
    def get_current_url(self) -> Dict:
        """Get current URL"""
        try:
            url = self.driver.current_url
            return {"success": True, "url": url}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "url": ""}
    
    def get_page_title(self) -> Dict:
        """Get page title"""
        try:
            title = self.driver.title
            return {"success": True, "title": title}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "title": ""}
    
    # ========================================================================
    # DOM EXTRACTION
    # ========================================================================
    
    def get_dom(self, filter_out_hidden: bool = True) -> Dict:
        """
        Get full DOM HTML
        
        Args:
            filter_out_hidden: Remove hidden elements
            
        Returns:
            Dict with success and DOM HTML
        """
        try:
            html = self.driver.page_source
            
            if filter_out_hidden:
                soup = BeautifulSoup(html, 'html.parser')
                
                # Remove hidden elements
                for element in soup.find_all(style=lambda value: value and 'display:none' in value.replace(' ', '')):
                    element.decompose()
                
                for element in soup.find_all(style=lambda value: value and 'visibility:hidden' in value.replace(' ', '')):
                    element.decompose()
                
                html = str(soup)
            
            return {"success": True, "dom": html, "length": len(html)}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "dom": "", "length": 0}
    
    def get_dom_hash(self) -> Dict:
        """Get hash of current DOM for change detection"""
        try:
            html = self.driver.page_source
            dom_hash = hashlib.md5(html.encode()).hexdigest()
            return {"success": True, "hash": dom_hash}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "hash": ""}
    
    # ========================================================================
    # SCREENSHOTS
    # ========================================================================
    
    def take_screenshot(self, filename: str = None) -> Dict:
        """
        Take full page screenshot
        
        Args:
            filename: Optional custom filename
            
        Returns:
            Dict with success, filepath, and base64 data
        """
        try:
            if filename is None:
                timestamp = time.strftime("%Y%m%d_%H%M%S")
                filename = f"screenshot_{timestamp}.png"
            
            if not filename.endswith('.png'):
                filename += '.png'
            
            filepath = os.path.join(self.screenshots_path, filename)
            
            self.driver.save_screenshot(filepath)
            
            # Also return as base64
            with open(filepath, "rb") as f:
                img_data = base64.b64encode(f.read()).decode()
            
            self.info_logger.info(f"Screenshot saved: {filepath}")
            
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "base64": img_data
            }
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "filepath": "", "base64": ""}
    
    # ========================================================================
    # ELEMENT FINDING
    # ========================================================================
    
    def _find_element(self, selector: str, timeout: int = 5):
        """
        Internal method to find element by CSS selector or XPath
        
        Args:
            selector: CSS selector or XPath
            timeout: Wait timeout in seconds
            
        Returns:
            WebElement or None
        """
        try:
            # Determine if it's XPath or CSS
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return element
        except:
            return None
    
    def find_elements(self, selector: str, timeout: int = 5) -> Dict:
        """
        Find all elements matching selector
        
        Args:
            selector: CSS selector or XPath
            timeout: Wait timeout in seconds
            
        Returns:
            Dict with success, count, and element details
        """
        try:
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            
            elements = self.driver.find_elements(by, selector)
            
            element_details = []
            for idx, elem in enumerate(elements):
                try:
                    detail = {
                        "index": idx,
                        "tag": elem.tag_name,
                        "text": elem.text[:100] if elem.text else "",
                        "displayed": elem.is_displayed(),
                        "enabled": elem.is_enabled()
                    }
                    element_details.append(detail)
                except StaleElementReferenceException:
                    pass
            
            return {
                "success": True,
                "count": len(elements),
                "elements": element_details
            }
        except TimeoutException:
            return {"success": False, "error": "Element not found", "count": 0, "elements": []}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "count": 0, "elements": []}
    
    def element_exists(self, selector: str, timeout: int = 2) -> Dict:
        """Check if element exists"""
        try:
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return {"success": True, "exists": True}
        except:
            return {"success": True, "exists": False}
    
    def element_visible(self, selector: str, timeout: int = 2) -> Dict:
        """Check if element is visible"""
        try:
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, selector))
            )
            return {"success": True, "visible": True}
        except:
            return {"success": True, "visible": False}
    
    # ========================================================================
    # ACTIONS
    # ========================================================================
    
    def click_element(self, selector: str, timeout: int = 5) -> Dict:
        """
        Click element
        
        Args:
            selector: CSS selector or XPath
            timeout: Wait timeout in seconds
            
        Returns:
            Dict with success status
        """
        try:
            element = self._find_element(selector, timeout)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            # Scroll into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            
            # Try regular click first
            try:
                element.click()
            except ElementClickInterceptedException:
                # If intercepted, try JavaScript click
                self.driver.execute_script("arguments[0].click();", element)
            
            time.sleep(0.5)
            self.info_logger.info(f"Clicked: {selector}")
            return {"success": True}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            self.info_logger.error(f"Click failed: {clean_error}")
            return {"success": False, "error": clean_error}
    
    def fill_element(self, selector: str, value: str, clear_first: bool = True, timeout: int = 5) -> Dict:
        """
        Fill element with text
        
        Args:
            selector: CSS selector or XPath
            value: Text to enter
            clear_first: Clear field before filling
            timeout: Wait timeout in seconds
            
        Returns:
            Dict with success status
        """
        try:
            element = self._find_element(selector, timeout)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            # Scroll into view
            self.driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.2)
            
            if clear_first:
                element.clear()
                time.sleep(0.1)
            
            element.send_keys(value)
            time.sleep(0.3)
            
            self.info_logger.info(f"Filled: {selector} = {value}")
            return {"success": True}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            self.info_logger.error(f"Fill failed: {clean_error}")
            return {"success": False, "error": clean_error}
    
    def select_dropdown(self, selector: str, value: str, by_value: bool = False, timeout: int = 5) -> Dict:
        """
        Select dropdown option
        
        Args:
            selector: CSS selector or XPath
            value: Text or value to select
            by_value: Select by value attribute instead of visible text
            timeout: Wait timeout in seconds
            
        Returns:
            Dict with success status
        """
        try:
            element = self._find_element(selector, timeout)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            select = Select(element)
            
            if by_value:
                select.select_by_value(value)
            else:
                select.select_by_visible_text(value)
            
            time.sleep(0.3)
            self.info_logger.info(f"Selected: {selector} = {value}")
            return {"success": True}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def check_checkbox(self, selector: str, check: bool = True, timeout: int = 5) -> Dict:
        """
        Check or uncheck checkbox
        
        Args:
            selector: CSS selector or XPath
            check: True to check, False to uncheck
            timeout: Wait timeout in seconds
            
        Returns:
            Dict with success status
        """
        try:
            element = self._find_element(selector, timeout)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            is_checked = element.is_selected()
            
            if (check and not is_checked) or (not check and is_checked):
                element.click()
                time.sleep(0.3)
            
            self.info_logger.info(f"Checkbox {'checked' if check else 'unchecked'}: {selector}")
            return {"success": True}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # STEP EXECUTION
    # ========================================================================
    
    def execute_step(self, step: Dict) -> Dict:
        """
        Execute a single test step
        
        Args:
            step: Dictionary containing step details:
                - action: "click", "fill", "select", "check", "navigate", etc.
                - selector: Element selector (for element actions)
                - value: Value to use (for fill/select actions)
                - description: Human-readable description
                - step_number: Unique step identifier
                
        Returns:
            Dict with execution result
        """
        action = step.get("action", "").lower()
        selector = step.get("selector", "")
        value = step.get("value", "")
        description = step.get("description", "")
        step_number = step.get("step_number", "")
        
        self.info_logger.info(f"Executing step {step_number}: {description} ({action})")
        
        result = {"step_number": step_number, "description": description, "action": action}
        
        try:
            if action == "navigate":
                url = step.get("url", value)
                nav_result = self.navigate_to_url(url)
                result.update(nav_result)
                
            elif action == "click":
                click_result = self.click_element(selector)
                result.update(click_result)
                
            elif action == "fill":
                fill_result = self.fill_element(selector, value)
                result.update(fill_result)
                
            elif action == "select":
                select_result = self.select_dropdown(selector, value)
                result.update(select_result)
                
            elif action == "check":
                check_value = value.lower() in ["true", "yes", "1", "checked"]
                check_result = self.check_checkbox(selector, check_value)
                result.update(check_result)
                
            elif action == "wait":
                wait_time = float(value) if value else 1.0
                time.sleep(wait_time)
                result.update({"success": True, "waited": wait_time})
                
            elif action == "screenshot":
                filename = value if value else f"step_{step_number}.png"
                screenshot_result = self.take_screenshot(filename)
                result.update(screenshot_result)
                
            else:
                result.update({"success": False, "error": f"Unknown action: {action}"})
            
            self.results_logger.info(f"Step {step_number} result: {result.get('success', False)}")
            return result
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            result.update({"success": False, "error": clean_error})
            self.results_logger.error(f"Step {step_number} failed: {clean_error}")
            return result
    
    # ========================================================================
    # WAITING & SYNCHRONIZATION
    # ========================================================================
    
    def wait_dom_ready(self, timeout: int = 10) -> Dict:
        """Wait for DOM to be ready"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def wait_for_element(self, selector: str, timeout: int = 10) -> Dict:
        """Wait for element to be present"""
        try:
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by, selector))
            )
            return {"success": True}
        except TimeoutException:
            return {"success": False, "error": "Element not found within timeout"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def wait_for_element_visible(self, selector: str, timeout: int = 10) -> Dict:
        """Wait for element to be visible"""
        try:
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by, selector))
            )
            return {"success": True}
        except TimeoutException:
            return {"success": False, "error": "Element not visible within timeout"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def wait_for_element_clickable(self, selector: str, timeout: int = 10) -> Dict:
        """Wait for element to be clickable"""
        try:
            by = By.XPATH if selector.startswith("//") or selector.startswith("(//") else By.CSS_SELECTOR
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by, selector))
            )
            return {"success": True}
        except TimeoutException:
            return {"success": False, "error": "Element not clickable within timeout"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # IFRAME HANDLING
    # ========================================================================
    
    def switch_to_iframe(self, selector: str = None, index: int = None) -> Dict:
        """
        Switch to iframe
        
        Args:
            selector: CSS selector or XPath for iframe
            index: Index of iframe (if selector not provided)
            
        Returns:
            Dict with success status
        """
        try:
            if selector:
                iframe = self._find_element(selector)
                if not iframe:
                    return {"success": False, "error": f"Iframe not found: {selector}"}
                self.driver.switch_to.frame(iframe)
            elif index is not None:
                self.driver.switch_to.frame(index)
            else:
                return {"success": False, "error": "Must provide selector or index"}
            
            time.sleep(0.5)
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def switch_to_default_content(self) -> Dict:
        """Switch back to main document"""
        try:
            self.driver.switch_to.default_content()
            time.sleep(0.3)
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # ALERT HANDLING
    # ========================================================================
    
    def handle_alert(self, accept: bool = True) -> Dict:
        """
        Handle JavaScript alert
        
        Args:
            accept: True to accept, False to dismiss
            
        Returns:
            Dict with success and alert text
        """
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            
            if accept:
                alert.accept()
            else:
                alert.dismiss()
            
            time.sleep(0.3)
            return {"success": True, "alert_text": alert_text}
        except NoAlertPresentException:
            return {"success": False, "error": "No alert present"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # POPUP & OVERLAY HANDLING
    # ========================================================================
    
    def dismiss_popups(self) -> Dict:
        """Try to dismiss common popups and overlays"""
        try:
            dismissed_count = 0
            
            # Cookie consent
            cookie_selectors = [
                "//button[contains(translate(text(), 'ACCEPT', 'accept'), 'accept')]",
                ".cookie-consent button", ".cookie-banner button",
                "#accept-cookies", ".oxd-toast-close"
            ]
            
            for sel in cookie_selectors:
                try:
                    if sel.startswith("//"):
                        elements = self.driver.find_elements(By.XPATH, sel)
                    else:
                        elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    
                    for el in elements:
                        if el.is_displayed():
                            try:
                                el.click()
                                time.sleep(0.3)
                                dismissed_count += 1
                                break
                            except:
                                pass
                except:
                    pass
            
            close_selectors = [
                ".modal.show .close", ".modal.show [data-dismiss='modal']",
                ".dialog[open] .close", "[role='dialog'] button[aria-label='Close']",
                ".ant-modal-close", ".MuiDialog-root button[aria-label='close']"
            ]
            
            for sel in close_selectors:
                try:
                    elements = self.driver.find_elements(By.CSS_SELECTOR, sel)
                    for el in elements:
                        if el.is_displayed():
                            try:
                                el.click()
                                time.sleep(0.3)
                                dismissed_count += 1
                                break
                            except:
                                pass
                except:
                    pass
            
            try:
                overlays = self.driver.find_elements(By.CSS_SELECTOR, ".modal-backdrop, .overlay, [class*='backdrop']")
                for overlay in overlays:
                    if overlay.is_displayed():
                        try:
                            overlay.click()
                            time.sleep(0.3)
                            dismissed_count += 1
                            break
                        except:
                            pass
            except:
                pass
            
            try:
                from selenium.webdriver.common.keys import Keys
                self.driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
                time.sleep(0.2)
            except:
                pass
            
            return {"success": True, "dismissed_count": dismissed_count}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "dismissed_count": 0}
    
    def handle_overlay_dismiss(self, overlay_selector: str) -> Dict:
        """Dismiss specific overlay/modal"""
        try:
            overlay = self.driver.find_element(By.CSS_SELECTOR, overlay_selector)
            if overlay.is_displayed():
                close_btn = overlay.find_element(By.CSS_SELECTOR, ".close, [aria-label='Close'], button")
                close_btn.click()
                time.sleep(0.3)
                return {"success": True}
            return {"success": False, "error": "Overlay not visible"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # ADVANCED INTERACTIONS
    # ========================================================================
    
    def handle_hover(self, selector: str) -> Dict:
        """Hover over element"""
        try:
            element = self._find_element(selector)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            ActionChains(self.driver).move_to_element(element).perform()
            time.sleep(0.3)
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def handle_scroll(self, direction: str = "down", amount: int = 500) -> Dict:
        """Scroll page"""
        try:
            if direction == "down":
                self.driver.execute_script(f"window.scrollBy(0, {amount})")
            elif direction == "up":
                self.driver.execute_script(f"window.scrollBy(0, -{amount})")
            time.sleep(0.5)
            return {"success": True, "direction": direction, "amount": amount}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def select_by_visible_text(self, selector: str, text: str) -> Dict:
        """Select dropdown option by visible text"""
        try:
            element = self._find_element(selector)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            Select(element).select_by_visible_text(text)
            return {"success": True, "selected": text}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    # ========================================================================
    # NAVIGATION & WINDOW MANAGEMENT
    # ========================================================================
    
    def go_back(self) -> Dict:
        """Navigate back"""
        try:
            self.driver.back()
            time.sleep(0.5)
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def get_window_handles(self) -> Dict:
        """Get all window handles"""
        try:
            handles = self.driver.window_handles
            return {"success": True, "handles": handles, "count": len(handles)}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "handles": [], "count": 0}
    
    def switch_window(self, handle: str) -> Dict:
        """Switch to specific window"""
        try:
            self.driver.switch_to.window(handle)
            time.sleep(0.5)
            return {"success": True, "current_url": self.driver.current_url}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def close_current_window(self) -> Dict:
        """Close current window"""
        try:
            self.driver.close()
            time.sleep(0.3)
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def get_main_window_handle(self) -> Dict:
        """Get the first (main) window handle"""
        try:
            handles = self.driver.window_handles
            if handles:
                return {"success": True, "handle": handles[0]}
            return {"success": False, "error": "No windows open"}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def execute_script(self, script: str, *args) -> Dict:
        """
        Execute JavaScript code
        
        Args:
            script: JavaScript code to execute
            *args: Arguments to pass to the script
            
        Returns:
            Dict with success and result
        """
        try:
            result = self.driver.execute_script(script, *args)
            return {"success": True, "result": result}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "result": None}


# ============================================================================
# MULTI-FORMS DISCOVERY AGENT
# Extends AgentSelenium with form discovery capabilities
# ============================================================================

class MultiFormsDiscoveryAgent(AgentSelenium):
    """
    Extended agent for multi-form discovery
    Inherits all base Selenium capabilities and adds form-specific methods
    """
    
    def __init__(self, screenshot_folder: Optional[str] = None):
        super().__init__(screenshot_folder)
        self.info_logger.info("MultiFormsDiscoveryAgent initialized")
    
    def get_all_clickable_elements(self) -> Dict:
        """
        Get all clickable elements (buttons, links, etc.) on the page
        
        Returns:
            Dict with success and list of clickable elements
        """
        try:
            script = """
            return Array.from(document.querySelectorAll('button, a, [role="button"], input[type="button"], input[type="submit"]'))
                .filter(el => {
                    const style = window.getComputedStyle(el);
                    return style.display !== 'none' && 
                           style.visibility !== 'hidden' && 
                           el.offsetParent !== null;
                })
                .map((el, idx) => ({
                    index: idx,
                    tag: el.tagName.toLowerCase(),
                    text: el.textContent.trim().substring(0, 100),
                    id: el.id,
                    classes: el.className,
                    type: el.type || '',
                    href: el.href || '',
                    selector: el.id ? `#${el.id}` : `.${el.className.split(' ').join('.')}`
                }));
            """
            
            result = self.execute_script(script)
            
            if result.get("success"):
                elements = result.get("result", [])
                return {
                    "success": True,
                    "elements": elements,
                    "count": len(elements)
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Script execution failed"),
                    "elements": [],
                    "count": 0
                }
                
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {
                "success": False,
                "error": clean_error,
                "elements": [],
                "count": 0
            }
    
    def check_for_form_fields(self) -> Dict:
        """
        Check if page contains form input fields
        
        Returns:
            Dict with success and form field details
        """
        try:
            script = """
            const formFields = document.querySelectorAll('input:not([type="hidden"]):not([type="submit"]):not([type="button"]), textarea, select');
            const visibleFields = Array.from(formFields).filter(field => {
                const style = window.getComputedStyle(field);
                return style.display !== 'none' && 
                       style.visibility !== 'hidden' && 
                       field.offsetParent !== null;
            });
            
            return {
                hasFormFields: visibleFields.length > 0,
                fieldCount: visibleFields.length,
                fields: visibleFields.slice(0, 20).map(field => ({
                    tag: field.tagName.toLowerCase(),
                    type: field.type || 'text',
                    name: field.name || '',
                    id: field.id || '',
                    placeholder: field.placeholder || '',
                    required: field.required || false
                }))
            };
            """
            
            result = self.execute_script(script)
            
            if result.get("success"):
                form_data = result.get("result", {})
                return {
                    "success": True,
                    "has_form_fields": form_data.get("hasFormFields", False),
                    "field_count": form_data.get("fieldCount", 0),
                    "fields": form_data.get("fields", [])
                }
            else:
                return {
                    "success": False,
                    "error": result.get("error", "Script execution failed"),
                    "has_form_fields": False,
                    "field_count": 0,
                    "fields": []
                }
                
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {
                "success": False,
                "error": clean_error,
                "has_form_fields": False,
                "field_count": 0,
                "fields": []
            }
