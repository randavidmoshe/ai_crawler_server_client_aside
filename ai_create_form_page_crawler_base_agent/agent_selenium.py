# agent_selenium.py
# AGENT SIDE - All Selenium WebDriver Operations
# This file runs on the customer's network and has access to internal QA environments

import os
import time
import hashlib
import base64
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


class AgentSelenium:
    """
    Agent-side Selenium operations
    Handles all browser automation, DOM extraction, and step execution
    """
    
    def __init__(self):
        self.driver = None
        self.shadow_root_context = None
        
    def initialize_browser(
        self,
        browser_type: str = "chrome",
        headless: bool = False,
        download_dir: Optional[str] = None,
        electron_binary: Optional[str] = None,
        electron_debug_port: Optional[int] = None
    ) -> Dict:
        """
        Initialize browser on agent side
        
        Args:
            browser_type: 'chrome', 'firefox', 'edge', or 'electron'
            headless: Run in headless mode
            download_dir: Download directory path
            electron_binary: Path to Electron binary (for Electron apps)
            electron_debug_port: Debug port for connecting to running Electron app
            
        ELECTRON CONFIGURATION GUIDE:
        ==============================
        
        **Case 1: Packaged Electron App (Standalone .exe/.app)**
        Configure:
            browser_type="electron"
            electron_binary="/path/to/YourApp.exe"  # Windows
            electron_binary="/path/to/YourApp.app/Contents/MacOS/YourApp"  # macOS
            electron_binary="/path/to/yourapp"  # Linux
        
        Example:
            initialize_browser(
                browser_type="electron",
                electron_binary="C:/Program Files/MyApp/MyApp.exe"
            )
        
        **Case 2: Electron Development Mode (npm start / electron .)**
        Configure:
            browser_type="electron"
            electron_binary="electron"  # Uses system Electron from PATH
        
        Requirements:
            - Electron must be installed globally: npm install -g electron
            - OR available in project: npm install electron --save-dev
        
        Example:
            initialize_browser(
                browser_type="electron",
                electron_binary="electron"
            )
        
        **Case 3: Connect to Already-Running Electron App**
        Configure:
            browser_type="electron"
            electron_debug_port=9222  # Port your app is running on
        
        Requirements:
            - Start your Electron app with remote debugging enabled:
              electron . --remote-debugging-port=9222
            - OR add to your app's main.js:
              app.commandLine.appendSwitch('remote-debugging-port', '9222')
        
        Example:
            initialize_browser(
                browser_type="electron",
                electron_debug_port=9222
            )
        
        **Case 4: Default Electron (tries system installation)**
        Configure:
            browser_type="electron"
            # No electron_binary or electron_debug_port specified
        
        This will attempt to use 'electron' from system PATH.
        
        Returns:
            Dict with success status and message
        """
        try:
            if browser_type.lower() == "chrome":
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
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.set_page_load_timeout(40)
                    print("[WebDriver] ✅ Initialized successfully")
                    #return driver
                
            elif browser_type.lower() == "firefox":
                options = webdriver.FirefoxOptions()
                if headless:
                    options.add_argument('--headless')
                
                if download_dir:
                    options.set_preference("browser.download.folderList", 2)
                    options.set_preference("browser.download.dir", download_dir)
                
                self.driver = webdriver.Firefox(options=options)
                
            elif browser_type.lower() == "edge":
                options = webdriver.EdgeOptions()
                if headless:
                    options.add_argument('--headless')
                
                self.driver = webdriver.Edge(options=options)
            
            elif browser_type.lower() == "electron":
                # Electron support - uses ChromeDriver since Electron is Chromium-based
                options = webdriver.ChromeOptions()
                
                # Case 3: Connect to already-running Electron app via debug port
                if electron_debug_port:
                    print(f"[WebDriver] Connecting to running Electron app on port {electron_debug_port}...")
                    options.add_experimental_option("debuggerAddress", f"localhost:{electron_debug_port}")
                
                # Case 1 & 2: Launch Electron app with specific binary
                elif electron_binary:
                    print(f"[WebDriver] Launching Electron app: {electron_binary}")
                    options.binary_location = electron_binary
                
                # Case 4: Default - try system Electron
                else:
                    print("[WebDriver] Using default system Electron installation")
                    options.binary_location = "electron"
                
                # Electron-specific options
                options.add_argument("--enable-logging")
                options.add_argument("--v=1")
                options.add_argument('--no-sandbox')
                options.add_argument('--disable-dev-shm-usage')
                
                # Optional headless mode (if Electron supports it)
                if headless:
                    options.add_argument('--headless=new')
                    options.add_argument('--disable-gpu')
                
                # Disable automation detection
                options.add_argument('--disable-blink-features=AutomationControlled')
                options.add_experimental_option("excludeSwitches", ["enable-automation"])
                options.add_experimental_option('useAutomationExtension', False)
                
                try:
                    service = Service()
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.set_page_load_timeout(40)
                    print("[WebDriver] ✅ Electron initialized successfully")
                except Exception as e:
                    print(f"[WebDriver] Electron initialization failed: {e}")
                    print("[WebDriver] Downloading ChromeDriver for Electron...")
                    downloaded_binary_path = ChromeDriverManager().install()
                    service = Service(executable_path=downloaded_binary_path)
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.set_page_load_timeout(40)
                    print("[WebDriver] ✅ Electron initialized successfully")
                
            else:
                return {"success": False, "error": f"Unsupported browser: {browser_type}"}
            
            self.driver.maximize_window()
            self.driver.set_page_load_timeout(30)
            
            return {
                "success": True,
                "browser": browser_type,
                "headless": headless,
                "session_id": self.driver.session_id
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def navigate_to_url(self, url: str) -> Dict:
        """Navigate to URL"""
        try:
            self.driver.get(url)
            return {
                "success": True,
                "url": self.driver.current_url,
                "title": self.driver.title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def extract_dom(self) -> Dict:
        """
        Extract current DOM and compute hash
        
        Returns:
            Dict with dom_html, dom_hash, url
        """
        try:
            dom_html = self.driver.page_source
            dom_hash = hashlib.md5(dom_html.encode('utf-8')).hexdigest()
            
            return {
                "success": True,
                "dom_html": dom_html,
                "dom_hash": dom_hash,
                "url": self.driver.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def extract_form_dom_with_js(self) -> Dict:
        """
        Extract optimized DOM (forms + external JS inlined)
        Reduces DOM size by 70-80%
        """
        try:
            soup = BeautifulSoup(self.driver.page_source, 'html.parser')
            result = []
            
            # Extract forms
            forms = soup.find_all('form')
            
            if forms:
                for form in forms:
                    result.append(str(form))
            else:
                # No forms - get body
                body = soup.find('body')
                if body:
                    result.append(str(body))
            
            # Extract external JS
            scripts = soup.find_all('script', src=True)
            for script in scripts:
                src = script.get('src')
                if src and not src.startswith('http'):
                    # Relative path - fetch it
                    try:
                        base_url = self.driver.current_url.rsplit('/', 1)[0]
                        js_url = f"{base_url}/{src.lstrip('/')}"
                        js_content = self.driver.execute_script(
                            f"return fetch('{js_url}').then(r => r.text())"
                        )
                        if js_content:
                            result.append(f"<script>\n{js_content}\n</script>")
                    except:
                        pass
            
            # Extract inline scripts (without src attribute)
            # This captures calculation logic, event listeners, and initialization code
            inline_scripts = soup.find_all('script', src=False)
            for script in inline_scripts:
                if script.string and script.string.strip():
                    # Skip very large scripts (likely embedded libraries like jQuery)
                    if len(script.string) < 50000:  # 50KB limit
                        result.append(f"<script>\n{script.string}\n</script>")
            
            dom_html = '\n'.join(result)
            dom_hash = hashlib.md5(dom_html.encode('utf-8')).hexdigest()
            
            return {
                "success": True,
                "dom_html": dom_html,
                "dom_hash": dom_hash,
                "url": self.driver.current_url,
                "size_chars": len(dom_html)
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def capture_screenshot(self, encode_base64: bool = True) -> Dict:
        """
        Capture screenshot
        
        Args:
            encode_base64: If True, return base64 encoded string
            
        Returns:
            Dict with screenshot data
        """
        try:
            screenshot_png = self.driver.get_screenshot_as_png()
            
            if encode_base64:
                screenshot_b64 = base64.b64encode(screenshot_png).decode('utf-8')
                return {
                    "success": True,
                    "screenshot": screenshot_b64,
                    "format": "base64"
                }
            else:
                return {
                    "success": True,
                    "screenshot": screenshot_png,
                    "format": "binary"
                }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def check_for_alert(self) -> Dict:
        """
        Check if JavaScript alert/confirm/prompt is present
        
        Returns:
            Dict with alert info or None if no alert
        """
        try:
            alert = self.driver.switch_to.alert
            alert_text = alert.text
            
            # Determine alert type
            alert_type = "alert"
            try:
                alert.send_keys("")
                alert_type = "prompt"
            except:
                if any(word in alert_text.lower() for word in ['sure', 'confirm', 'continue', 'yes', 'no']):
                    alert_type = "confirm"
            
            return {
                "success": True,
                "alert_present": True,
                "alert_type": alert_type,
                "alert_text": alert_text
            }
        except NoAlertPresentException:
            return {
                "success": True,
                "alert_present": False
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def execute_step(self, step: Dict) -> Dict:
        """
        Execute a single test step
        
        Args:
            step: Dict with action, selector, value, description
            
        Returns:
            Dict with success status and any relevant data
        """
        try:
            action = step.get('action', '').lower()
            selector = step.get('selector', '')
            value = step.get('value', '')
            description = step.get('description', '')
            
            # FILL ACTION
            if action == "fill":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                element.clear()
                element.send_keys(value)
                return {
                    "success": True,
                    "action": "fill",
                    "selector": selector,
                    "value": value
                }
            
            # CLICK ACTION
            elif action == "click":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                try:
                    element.click()
                except ElementClickInterceptedException:
                    # Try JavaScript click
                    self.driver.execute_script("arguments[0].click();", element)
                
                return {
                    "success": True,
                    "action": "click",
                    "selector": selector
                }
            
            # SELECT ACTION
            elif action == "select":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                select = Select(element)
                try:
                    select.select_by_visible_text(value)
                except:
                    try:
                        select.select_by_value(value)
                    except:
                        select.select_by_index(int(value))
                
                return {
                    "success": True,
                    "action": "select",
                    "selector": selector,
                    "value": value
                }
            
            # HOVER ACTION
            elif action == "hover":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                actions = ActionChains(self.driver)
                actions.move_to_element(element).perform()
                time.sleep(1)  # Wait for hover effects
                
                return {
                    "success": True,
                    "action": "hover",
                    "selector": selector
                }
            
            # SCROLL ACTION
            elif action == "scroll":
                if selector:
                    element = self._find_element(selector)
                    if element:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                else:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                return {"success": True, "action": "scroll"}
            
            # WAIT ACTION
            elif action == "wait":
                if selector:
                    # Wait for element to be present and interactable (AJAX scenario)
                    # Use value as timeout (default 10s, max 10s)
                    timeout = min(float(value) if value else 10.0, 10.0)
                    
                    try:
                        element = WebDriverWait(self.driver, timeout).until(
                            EC.element_to_be_clickable((By.CSS_SELECTOR, selector))
                        )
                        return {
                            "success": True,
                            "action": "wait",
                            "selector": selector,
                            "message": "Element is ready"
                        }
                    except TimeoutException:
                        # Log and continue (Option B - don't stop test)
                        error_msg = f"Element not ready after {timeout}s: {selector}"
                        print(f"[Agent] ⚠️  Wait timeout: {error_msg}")
                        return {
                            "success": True,  # ← Changed to True to continue
                            "action": "wait",
                            "selector": selector,
                            "message": f"Timeout but continuing: {error_msg}",
                            "warning": error_msg
                        }
                else:
                    # Simple time-based wait (max 10 seconds)
                    wait_time = min(float(value) if value else 2.0, 10.0)
                    time.sleep(wait_time)
                    return {"success": True, "action": "wait", "duration": wait_time}
            
            # WAIT_FOR_READY ACTION (explicit AJAX waiting)
            elif action == "wait_for_ready":
                if not selector:
                    return {"success": False, "error": "wait_for_ready requires a selector"}
                
                try:
                    # Determine selector type
                    if selector.startswith('/') or selector.startswith('//'):
                        by_type = By.XPATH
                    else:
                        by_type = By.CSS_SELECTOR
                    
                    # Wait for element to be clickable/interactable (max 10 seconds)
                    element = WebDriverWait(self.driver, 10).until(
                        EC.element_to_be_clickable((by_type, selector))
                    )
                    
                    # Additional checks for AJAX-loaded fields
                    if element.tag_name in ['input', 'textarea', 'select']:
                        # For input fields, also wait for them to be enabled (max 5 seconds)
                        WebDriverWait(self.driver, 5).until(
                            lambda d: element.is_enabled()
                        )
                    
                    return {
                        "success": True,
                        "action": "wait_for_ready",
                        "selector": selector,
                        "message": "Element is ready for interaction"
                    }
                    
                except TimeoutException:
                    # Log and continue (Option B - don't stop test)
                    error_msg = f"Element not ready after timeout: {selector}"
                    print(f"[Agent] ⚠️  wait_for_ready timeout: {error_msg}")
                    return {
                        "success": True,  # ← Changed to True to continue
                        "action": "wait_for_ready",
                        "selector": selector,
                        "message": f"Timeout but continuing: {error_msg}",
                        "warning": error_msg
                    }
            
            # SWITCH TO IFRAME
            elif action == "switch_to_frame":
                iframe = self._find_element(selector)
                if not iframe:
                    return {"success": False, "error": f"Iframe not found: {selector}"}
                
                self.driver.switch_to.frame(iframe)
                return {"success": True, "action": "switch_to_frame", "selector": selector}
            
            # SWITCH TO DEFAULT (exit iframe)
            elif action == "switch_to_default":
                self.driver.switch_to.default_content()
                self.shadow_root_context = None  # Clear shadow root context too
                return {"success": True, "action": "switch_to_default"}
            
            # SWITCH TO SHADOW ROOT
            elif action == "switch_to_shadow_root":
                shadow_host = self._find_element(selector)
                if not shadow_host:
                    return {"success": False, "error": f"Shadow host not found: {selector}"}
                
                self.shadow_root_context = shadow_host.shadow_root
                return {"success": True, "action": "switch_to_shadow_root", "selector": selector}
            
            # ALERT ACTIONS
            elif action == "accept_alert":
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                alert.accept()
                return {"success": True, "action": "accept_alert", "alert_text": alert_text}
            
            elif action == "dismiss_alert":
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                alert.dismiss()
                return {"success": True, "action": "dismiss_alert", "alert_text": alert_text}
            
            elif action == "fill_alert":
                alert = self.driver.switch_to.alert
                alert.send_keys(value)
                return {"success": True, "action": "fill_alert", "value": value}
            
            # NAVIGATE ACTION
            elif action == "navigate":
                self.driver.get(value)
                return {"success": True, "action": "navigate", "url": value}
            
            # REFRESH ACTION
            elif action == "refresh":
                self.driver.refresh()
                return {"success": True, "action": "refresh"}
            
            # VERIFY ACTION
            elif action == "verify":
                element = self._find_element(selector, timeout=5)
                if element and element.is_displayed():
                    return {"success": True, "action": "verify", "verified": True}
                else:
                    return {"success": False, "action": "verify", "verified": False}
            
            else:
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except Exception as e:
            return {"success": False, "error": str(e), "action": action}
    
    def _find_element(self, selector: str, timeout: int = 10):
        """
        Find element - supports both CSS selectors and XPath
        Automatically detects selector type:
        - XPath: starts with '/' or '//'
        - CSS: everything else
        """
        try:
            # Determine selector type
            if selector.startswith('/') or selector.startswith('//'):
                by_type = By.XPATH
            else:
                by_type = By.CSS_SELECTOR
            
            if self.shadow_root_context:
                # Search in shadow root (only CSS supported in shadow DOM)
                try:
                    element = self.shadow_root_context.find_element(By.CSS_SELECTOR, selector)
                    return element
                except NoSuchElementException:
                    # Poll for element
                    end_time = time.time() + timeout
                    while time.time() < end_time:
                        try:
                            element = self.shadow_root_context.find_element(By.CSS_SELECTOR, selector)
                            return element
                        except NoSuchElementException:
                            time.sleep(0.5)
                    return None
            else:
                # Normal search in main document (supports both CSS and XPath)
                element = WebDriverWait(self.driver, timeout).until(
                    EC.presence_of_element_located((by_type, selector))
                )
                return element
        except TimeoutException:
            return None
        except Exception:
            return None
    
    def close_browser(self) -> Dict:
        """Close browser and cleanup"""
        try:
            if self.driver:
                self.driver.quit()
                self.driver = None
                self.shadow_root_context = None
            return {"success": True}
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_current_url(self) -> Dict:
        """Get current URL"""
        try:
            return {
                "success": True,
                "url": self.driver.current_url
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def get_page_title(self) -> Dict:
        """Get page title"""
        try:
            return {
                "success": True,
                "title": self.driver.title
            }
        except Exception as e:
            return {"success": False, "error": str(e)}
