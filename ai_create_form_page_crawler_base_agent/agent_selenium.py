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
        
        print(f"[Agent] Screenshots: {self.screenshots_path}")
        print(f"[Agent] Logs: {self.logs_path}")
        print(f"[Agent] Files: {self.files_path}")
    
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
                    downloaded_binary_path = ChromeDriverManager().install()
                    service = Service(executable_path=downloaded_binary_path)
                    self.driver = webdriver.Chrome(service=service, options=options)
                    self.driver.set_page_load_timeout(40)
                    print("[WebDriver] ✅ Initialized successfully")
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
    
    def capture_screenshot(self, scenario_description: str = "screenshot", encode_base64: bool = True, save_to_folder: bool = True) -> Dict:
        """
        Capture screenshot and optionally save to configured folder with timestamp
        
        Args:
            scenario_description: Description of what was happening (e.g., "filling first name field")
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
                
                print(f"[Agent] Screenshot saved: {filepath}")
                
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
    
    def create_file(
        self,
        file_type: str,
        filename: str,
        content: str = ""
    ) -> Dict:
        try:
            filepath = os.path.join(self.files_path, filename)
            
            if file_type.lower() == "txt":
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            elif file_type.lower() == "csv":
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            elif file_type.lower() == "json":
                with open(filepath, 'w', encoding='utf-8') as f:
                    f.write(content)
            
            elif file_type.lower() == "pdf":
                if canvas is None:
                    return {"success": False, "error": "reportlab not installed"}
                
                c = canvas.Canvas(filepath, pagesize=letter)
                width, height = letter
                
                lines = content.split('\n')
                y_position = height - 50
                
                for line in lines:
                    if y_position < 50:
                        c.showPage()
                        y_position = height - 50
                    c.drawString(50, y_position, line)
                    y_position -= 15
                
                c.save()
            
            elif file_type.lower() in ["xlsx", "excel"]:
                if Workbook is None:
                    return {"success": False, "error": "openpyxl not installed"}
                
                wb = Workbook()
                ws = wb.active
                
                lines = content.split('\n')
                for i, line in enumerate(lines, 1):
                    cells = line.split(',')
                    for j, cell in enumerate(cells, 1):
                        ws.cell(row=i, column=j, value=cell.strip())
                
                wb.save(filepath)
            
            elif file_type.lower() in ["docx", "word"]:
                if Document is None:
                    return {"success": False, "error": "python-docx not installed"}
                
                doc = Document()
                for line in content.split('\n'):
                    doc.add_paragraph(line)
                doc.save(filepath)
            
            elif file_type.lower() in ["png", "jpg", "jpeg"]:
                if Image is None:
                    return {"success": False, "error": "Pillow not installed"}
                
                img = Image.new('RGB', (800, 600), color='white')
                draw = ImageDraw.Draw(img)
                
                try:
                    font = ImageFont.truetype("arial.ttf", 20)
                except:
                    font = ImageFont.load_default()
                
                y = 50
                for line in content.split('\n')[:20]:
                    draw.text((50, y), line, fill='black', font=font)
                    y += 30
                
                img.save(filepath)
            
            else:
                return {"success": False, "error": f"Unsupported file type: {file_type}"}
            
            print(f"[FileCreation] ✅ Created: {filename}")
            return {
                "success": True,
                "filepath": filepath,
                "filename": filename,
                "file_type": file_type
            }
            
        except Exception as e:
            return {"success": False, "error": str(e)}
    
    def upload_file(self, selector: str, filename: str) -> Dict:
        try:
            filepath = os.path.join(self.files_path, filename)
            
            if not os.path.exists(filepath):
                return {"success": False, "error": f"File not found: {filepath}"}
            
            element = self._find_element(selector, timeout=10)
            if not element:
                return {"success": False, "error": f"File input not found: {selector}"}
            
            element.send_keys(filepath)
            time.sleep(1)
            
            print(f"[FileUpload] ✅ Uploaded: {filename}")
            return {
                "success": True,
                "filename": filename,
                "filepath": filepath
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
        # STEP 1: Capture old DOM hash BEFORE action
        dom_before = self.extract_form_dom_with_js()
        old_dom_hash = dom_before.get("dom_hash", "") if dom_before.get("success") else ""
        
        def _finalize_success_result(base_result: Dict) -> Dict:
            """
            Helper to add alert check and DOM hash to successful action results
            
            Flow:
            1. Check for alert
            2. If alert present: accept it, get new DOM hash, return alert info
            3. If no alert: get new DOM hash, return it
            
            Args:
                base_result: The base success result from the action
                
            Returns:
                Enhanced result with alert info or new DOM hash
            """
            # Check for alert
            alert_info = self.check_for_alert()
            
            if alert_info.get("success") and alert_info.get("alert_present"):
                # Alert detected - accept it immediately
                try:
                    alert = self.driver.switch_to.alert
                    alert.accept()
                except Exception as e:
                    # If we can't accept, still continue
                    print(f"[Agent] Warning: Could not accept alert: {e}")
                
                # Get new DOM hash after alert is accepted
                dom_after = self.extract_form_dom_with_js()
                new_dom_hash = dom_after.get("dom_hash", "") if dom_after.get("success") else ""
                
                # Return with alert info
                return {
                    **base_result,
                    "old_dom_hash": old_dom_hash,
                    "alert_present": True,
                    "alert_type": alert_info.get("alert_type"),
                    "alert_text": alert_info.get("alert_text"),
                    "new_dom_hash": new_dom_hash
                }
            
            # No alert - get new DOM hash
            dom_after = self.extract_form_dom_with_js()
            new_dom_hash = dom_after.get("dom_hash", "") if dom_after.get("success") else ""
            
            return {
                **base_result,
                "old_dom_hash": old_dom_hash,
                "alert_present": False,
                "new_dom_hash": new_dom_hash
            }
        
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
                return _finalize_success_result({
                    "success": True,
                    "action": "fill",
                    "selector": selector,
                    "value": value
                })
            
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
                
                return _finalize_success_result({
                    "success": True,
                    "action": "click",
                    "selector": selector
                })
            
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
                
                return _finalize_success_result({
                    "success": True,
                    "action": "select",
                    "selector": selector,
                    "value": value
                })
            
            # HOVER ACTION
            elif action == "hover":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                actions = ActionChains(self.driver)
                actions.move_to_element(element).perform()
                time.sleep(1)  # Wait for hover effects
                
                return _finalize_success_result({
                    "success": True,
                    "action": "hover",
                    "selector": selector
                })
            
            # SCROLL ACTION
            elif action == "scroll":
                if selector:
                    element = self._find_element(selector)
                    if element:
                        self.driver.execute_script("arguments[0].scrollIntoView(true);", element)
                else:
                    self.driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                
                return _finalize_success_result({"success": True, "action": "scroll"})
            
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
                        return _finalize_success_result({
                            "success": True,
                            "action": "wait",
                            "selector": selector,
                            "message": "Element is ready"
                        })
                    except TimeoutException:
                        # Log and continue (Option B - don't stop test)
                        error_msg = f"Element not ready after {timeout}s: {selector}"
                        print(f"[Agent] ⚠️  Wait timeout: {error_msg}")
                        return _finalize_success_result({
                            "success": True,  # ← Changed to True to continue
                            "action": "wait",
                            "selector": selector,
                            "message": f"Timeout but continuing: {error_msg}",
                            "warning": error_msg
                        })
                else:
                    # Simple time-based wait (max 10 seconds)
                    wait_time = min(float(value) if value else 2.0, 10.0)
                    time.sleep(wait_time)
                    return _finalize_success_result({"success": True, "action": "wait", "duration": wait_time})
            
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
                    
                    return _finalize_success_result({
                        "success": True,
                        "action": "wait_for_ready",
                        "selector": selector,
                        "message": "Element is ready for interaction"
                    })
                    
                except TimeoutException:
                    # Log and continue (Option B - don't stop test)
                    error_msg = f"Element not ready after timeout: {selector}"
                    print(f"[Agent] ⚠️  wait_for_ready timeout: {error_msg}")
                    return _finalize_success_result({
                        "success": True,  # ← Changed to True to continue
                        "action": "wait_for_ready",
                        "selector": selector,
                        "message": f"Timeout but continuing: {error_msg}",
                        "warning": error_msg
                    })
            
            # SWITCH TO IFRAME
            elif action == "switch_to_frame":
                iframe = self._find_element(selector)
                if not iframe:
                    return {"success": False, "error": f"Iframe not found: {selector}"}
                
                self.driver.switch_to.frame(iframe)
                return _finalize_success_result({"success": True, "action": "switch_to_frame", "selector": selector})
            
            # SWITCH TO DEFAULT (exit iframe)
            elif action == "switch_to_default":
                self.driver.switch_to.default_content()
                self.shadow_root_context = None  # Clear shadow root context too
                return _finalize_success_result({"success": True, "action": "switch_to_default"})
            
            # SWITCH TO SHADOW ROOT
            elif action == "switch_to_shadow_root":
                shadow_host = self._find_element(selector)
                if not shadow_host:
                    return {"success": False, "error": f"Shadow host not found: {selector}"}
                
                self.shadow_root_context = shadow_host.shadow_root
                return _finalize_success_result({"success": True, "action": "switch_to_shadow_root", "selector": selector})
            
            # ALERT ACTIONS
            elif action == "accept_alert":
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                alert.accept()
                return _finalize_success_result({"success": True, "action": "accept_alert", "alert_text": alert_text})
            
            elif action == "dismiss_alert":
                alert = self.driver.switch_to.alert
                alert_text = alert.text
                alert.dismiss()
                return _finalize_success_result({"success": True, "action": "dismiss_alert", "alert_text": alert_text})
            
            elif action == "fill_alert":
                alert = self.driver.switch_to.alert
                alert.send_keys(value)
                return _finalize_success_result({"success": True, "action": "fill_alert", "value": value})
            
            # NAVIGATE ACTION
            elif action == "navigate":
                self.driver.get(value)
                return _finalize_success_result({"success": True, "action": "navigate", "url": value})
            
            # REFRESH ACTION
            elif action == "refresh":
                self.driver.refresh()
                return _finalize_success_result({"success": True, "action": "refresh"})
            
            # VERIFY ACTION
            elif action == "verify":
                # Enhanced verify: checks element existence, visibility, AND content (text or value)
                expected_value = value  # The expected text or value from the step
                description = step.get('description', 'Verify element')
                
                print(f"   🔍 Verifying: {description}")
                if expected_value:
                    print(f"      Expected value: '{expected_value}'")
                
                # Find the element
                element = self._find_element(selector, timeout=5)
                
                if not element:
                    print(f"   ❌ VERIFICATION FAILED: Element not found")
                    print(f"      Selector: {selector}")
                    return {
                        "success": False, 
                        "action": "verify", 
                        "verified": False,
                        "error": "Element not found",
                        "expected": expected_value,
                        "actual": "Element not found"
                    }
                
                if not element.is_displayed():
                    print(f"   ❌ VERIFICATION FAILED: Element exists but is not visible")
                    print(f"      Selector: {selector}")
                    return {
                        "success": False, 
                        "action": "verify", 
                        "verified": False,
                        "error": "Element not visible",
                        "expected": expected_value,
                        "actual": "Element hidden"
                    }
                
                # If expected_value is provided, verify the content
                if expected_value:
                    # Get actual value from element
                    tag_name = element.tag_name.lower()
                    
                    # For input/textarea, check the 'value' attribute
                    if tag_name in ['input', 'textarea']:
                        actual_value = element.get_attribute('value') or ''
                    # For select, get selected option text
                    elif tag_name == 'select':
                        select_element = Select(element)
                        actual_value = select_element.first_selected_option.text
                    # For other elements, get text content
                    else:
                        actual_value = element.text or element.get_attribute('textContent') or ''
                    
                    actual_value = actual_value.strip()
                    expected_value_normalized = expected_value.strip()
                    
                    # Check if actual contains expected (flexible matching)
                    if expected_value_normalized.lower() in actual_value.lower():
                        print(f"   ✅ VERIFICATION PASSED")
                        print(f"      Actual value: '{actual_value}'")
                        return _finalize_success_result({
                            "success": True, 
                            "action": "verify", 
                            "verified": True,
                            "expected": expected_value,
                            "actual": actual_value
                        })
                    else:
                        print(f"   ❌ VERIFICATION FAILED: Content mismatch")
                        print(f"      Expected: '{expected_value}'")
                        print(f"      Actual: '{actual_value}'")
                        return {
                            "success": False, 
                            "action": "verify", 
                            "verified": False,
                            "error": "Content mismatch",
                            "expected": expected_value,
                            "actual": actual_value
                        }
                else:
                    # No expected value provided - just verify existence and visibility
                    print(f"   ✅ VERIFICATION PASSED (element exists and is visible)")
                    return _finalize_success_result({
                        "success": True, 
                        "action": "verify", 
                        "verified": True
                    })
            
            # CREATE FILE ACTION
            elif action == "create_file":
                file_type = step.get('file_type', 'txt')
                filename = step.get('filename', 'test_file.txt')
                content = step.get('content', '')
                
                return self.create_file(file_type, filename, content)
            
            # UPLOAD FILE ACTION
            elif action == "upload_file":
                filename = value
                return self.upload_file(selector, filename)
            
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
