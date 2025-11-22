# agent_selenium.py
# AGENT SIDE - All Selenium WebDriver Operations
# This file runs on the customer's network and has access to internal QA environments

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
            
            self.info_logger.info(f"Browser initialized: {browser_type}, headless={headless}")
            
            return {
                "success": True,
                "browser": browser_type,
                "headless": headless,
                "session_id": self.driver.session_id
            }
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            self.info_logger.error(f"Browser initialization failed: {clean_error}")
            return {"success": False, "error": clean_error}
    
    def navigate_to_url(self, url: str) -> Dict:
        """Navigate to URL"""
        try:
            self.info_logger.info(f"Navigating to URL: {url}")
            self.driver.get(url)
            self.info_logger.info(f"Navigation successful: {self.driver.current_url}")
            return {
                "success": True,
                "url": self.driver.current_url,
                "title": self.driver.title
            }
        except Exception as e:
            clean_error = self._clean_error_message(e)
            self.info_logger.error(f"Navigation failed: {clean_error}")
            return {"success": False, "error": clean_error}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def capture_error_context(self) -> Dict:
        """
        Capture DOM and screenshot together for error analysis
        
        Returns:
            Dict with dom_html and screenshot_base64
        """
        try:
            # Capture DOM
            dom_result = self.extract_form_dom_with_js()
            dom_html = dom_result.get("dom_html", "") if dom_result.get("success") else ""
            
            # Capture screenshot (base64 encoded, save to folder)
            screenshot_result = self.capture_screenshot(
                scenario_description="error_context",
                encode_base64=True,
                save_to_folder=True
            )
            screenshot_base64 = screenshot_result.get("screenshot", "") if screenshot_result.get("success") else ""
            screenshot_path = screenshot_result.get("filepath", "") if screenshot_result.get("success") else ""
            
            return {
                "success": True,
                "dom_html": dom_html,
                "screenshot_base64": screenshot_base64,
                "screenshot_path": screenshot_path
            }
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def _compare_dom_fields(self, dom_before: Dict, dom_after: Dict) -> bool:
        """
        Compare fields between old DOM and new DOM to detect changes
        
        Checks for:
        1. New fields added
        2. Visible fields became hidden
        3. Hidden fields became visible
        
        Args:
            dom_before: DOM before action (from extract_form_dom_with_js)
            dom_after: DOM after action (from extract_form_dom_with_js)
            
        Returns:
            True if fields changed, False if no changes
        """
        from bs4 import BeautifulSoup
        
        def extract_fields(dom_html):
            """Extract all form fields with their visibility status"""
            soup = BeautifulSoup(dom_html, 'html.parser')
            fields = {}
            
            # Find all input, select, textarea elements
            for tag_name in ['input', 'select', 'textarea']:
                elements = soup.find_all(tag_name)
                for elem in elements:
                    # Get unique identifier
                    field_id = elem.get('id') or elem.get('name') or str(elem)
                    
                    # Check if field is hidden
                    is_hidden = False
                    
                    # Check type="hidden"
                    if tag_name == 'input' and elem.get('type') == 'hidden':
                        is_hidden = True
                    
                    # Check style="display: none" or "visibility: hidden"
                    style = elem.get('style', '')
                    if 'display:none' in style.replace(' ', '') or 'display: none' in style:
                        is_hidden = True
                    if 'visibility:hidden' in style.replace(' ', '') or 'visibility: hidden' in style:
                        is_hidden = True
                    
                    # Check class contains 'hidden'
                    classes = elem.get('class', [])
                    if isinstance(classes, list) and any('hidden' in c.lower() for c in classes):
                        is_hidden = True
                    elif isinstance(classes, str) and 'hidden' in classes.lower():
                        is_hidden = True
                    
                    # Check hidden attribute
                    if elem.has_attr('hidden'):
                        is_hidden = True
                    
                    # Check aria-hidden="true"
                    if elem.get('aria-hidden') == 'true':
                        is_hidden = True
                    
                    # Check parent elements for hidden status
                    if not is_hidden:
                        parent = elem.parent
                        while parent and parent.name != 'body':
                            # Check parent style
                            parent_style = parent.get('style', '')
                            if 'display:none' in parent_style.replace(' ', '') or 'display: none' in parent_style:
                                is_hidden = True
                                break
                            if 'visibility:hidden' in parent_style.replace(' ', '') or 'visibility: hidden' in parent_style:
                                is_hidden = True
                                break
                            
                            # Check parent class
                            parent_classes = parent.get('class', [])
                            if isinstance(parent_classes, list) and any('hidden' in c.lower() for c in parent_classes):
                                is_hidden = True
                                break
                            elif isinstance(parent_classes, str) and 'hidden' in parent_classes.lower():
                                is_hidden = True
                                break
                            
                            # Check parent hidden attribute
                            if parent.has_attr('hidden'):
                                is_hidden = True
                                break
                            
                            # Check parent aria-hidden
                            if parent.get('aria-hidden') == 'true':
                                is_hidden = True
                                break
                            
                            parent = parent.parent
                    
                    fields[field_id] = {
                        'tag': tag_name,
                        'type': elem.get('type', 'text') if tag_name == 'input' else tag_name,
                        'is_hidden': is_hidden
                    }
            
            return fields
        
        # Extract fields from both DOMs
        if not dom_before.get("success") or not dom_after.get("success"):
            print("[Agent] ⚠️  Field comparison: DOM extraction failed")
            return True  # Default to True if we can't compare
        
        old_fields = extract_fields(dom_before.get("dom_html", ""))
        new_fields = extract_fields(dom_after.get("dom_html", ""))
        
        # Track changes
        new_fields_added = []
        visible_to_hidden = []
        hidden_to_visible = []
        
        # Check for new fields
        for field_id in new_fields:
            if field_id not in old_fields:
                new_fields_added.append(field_id)
        
        # Check for visibility changes
        for field_id in old_fields:
            if field_id in new_fields:
                old_hidden = old_fields[field_id]['is_hidden']
                new_hidden = new_fields[field_id]['is_hidden']
                
                if not old_hidden and new_hidden:
                    # Was visible, now hidden
                    visible_to_hidden.append(field_id)
                elif old_hidden and not new_hidden:
                    # Was hidden, now visible
                    hidden_to_visible.append(field_id)
        
        # Print findings
        has_changes = bool(new_fields_added or visible_to_hidden or hidden_to_visible)
        
        if has_changes:
            print("\n[Agent] 🔍 Field Changes Detected:")
            if new_fields_added:
                print(f"   ➕ New fields added: {len(new_fields_added)}")
                for field in new_fields_added[:5]:  # Show first 5
                    field_info = new_fields[field]
                    print(f"      - {field_info['type']}: {field[:80]}")
                if len(new_fields_added) > 5:
                    print(f"      ... and {len(new_fields_added) - 5} more")
            
            if visible_to_hidden:
                print(f"   🙈 Visible → Hidden: {len(visible_to_hidden)}")
                for field in visible_to_hidden[:5]:
                    field_info = old_fields[field]
                    print(f"      - {field_info['type']}: {field[:80]}")
                if len(visible_to_hidden) > 5:
                    print(f"      ... and {len(visible_to_hidden) - 5} more")
            
            if hidden_to_visible:
                print(f"   👁️  Hidden → Visible: {len(hidden_to_visible)}")
                for field in hidden_to_visible[:5]:
                    field_info = new_fields[field]
                    print(f"      - {field_info['type']}: {field[:80]}")
                if len(hidden_to_visible) > 5:
                    print(f"      ... and {len(hidden_to_visible) - 5} more")
        
        # Check 2: DOM structure change (element count)
        if not has_changes:
            from bs4 import BeautifulSoup
            old_soup = BeautifulSoup(dom_before.get("dom_html", ""), 'html.parser')
            new_soup = BeautifulSoup(dom_after.get("dom_html", ""), 'html.parser')
            
            old_element_count = len(old_soup.find_all())
            new_element_count = len(new_soup.find_all())
            
            if old_element_count > 0:
                change_percent = abs(new_element_count - old_element_count) / old_element_count * 100
                
                if change_percent > 30:  # 30% threshold
                    print(f"\n[Agent] 🔍 DOM Structure Change Detected:")
                    print(f"   📊 Element count: {old_element_count} → {new_element_count} ({change_percent:.1f}% change)")
                    has_changes = True
        
        if not has_changes:
            print("[Agent] ℹ️  No field changes detected")
        
        return has_changes
    
    def execute_step(self, step: Dict) -> Dict:
        """
        Execute a single test step
        
        Args:
            step: Dict with action, selector, value, description
            
        Returns:
            Dict with success status and any relevant data
        """
        action = step.get('action', 'unknown')
        description = step.get('description', 'No description')
        step_number = step.get('step_number', '?')
        value = step.get('value', '')
        
        # Build log message with value if present
        if value:
            log_msg = f"Step {step_number}: {action.upper()} - {description} with value: {value}"
        else:
            log_msg = f"Step {step_number}: {action.upper()} - {description}"
        
        self.results_logger.info(log_msg)
        self.info_logger.info(f"Executing step {step_number}: {action} | Selector: {step.get('selector', 'N/A')} | Value: {step.get('value', 'N/A')}")
        
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
                # Wait briefly for JavaScript to finish
                time.sleep(0.5)
                dom_after = self.extract_form_dom_with_js()
                new_dom_hash = dom_after.get("dom_hash", "") if dom_after.get("success") else ""
                
                # Check if fields changed
                fields_changed = self._compare_dom_fields(dom_before, dom_after)
                
                # Return with alert info
                return {
                    **base_result,
                    "old_dom_hash": old_dom_hash,
                    "alert_present": True,
                    "alert_type": alert_info.get("alert_type"),
                    "alert_text": alert_info.get("alert_text"),
                    "new_dom_hash": new_dom_hash,
                    "fields_changed": fields_changed
                }
            
            # No alert - get new DOM hash
            # Wait briefly for JavaScript to finish (especially for conditional field visibility changes)
            time.sleep(0.5)
            dom_after = self.extract_form_dom_with_js()
            new_dom_hash = dom_after.get("dom_hash", "") if dom_after.get("success") else ""
            
            # Check if fields changed
            fields_changed = self._compare_dom_fields(dom_before, dom_after)
            
            self.results_logger.info(f"  ✅ Success")
            self.results_logger.info("-" * 70)
            self.info_logger.info(f"Step completed successfully: {action}")
            
            return {
                **base_result,
                "old_dom_hash": old_dom_hash,
                "alert_present": False,
                "new_dom_hash": new_dom_hash,
                "fields_changed": fields_changed
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
            
            # SLIDER ACTION
            elif action == "slider":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Slider not found: {selector}"}
                
                # Value should be percentage (0-100)
                try:
                    percentage = float(value)
                    if percentage < 0 or percentage > 100:
                        return {"success": False, "error": f"Slider percentage must be 0-100, got: {percentage}"}
                    
                    # Get slider dimensions
                    slider_width = element.size['width']
                    
                    # Calculate offset from left (percentage of width)
                    # Subtract half width to start from center of slider
                    offset_x = int((slider_width * percentage / 100) - (slider_width / 2))
                    
                    # Use ActionChains to drag slider to position
                    actions = ActionChains(self.driver)
                    actions.click_and_hold(element).move_by_offset(offset_x, 0).release().perform()
                    
                    return _finalize_success_result({
                        "success": True,
                        "action": "slider",
                        "selector": selector,
                        "value": value
                    })
                except ValueError:
                    return {"success": False, "error": f"Invalid slider value (must be 0-100): {value}"}
            
            # DRAG AND DROP ACTION
            elif action == "drag_and_drop":
                # Selector is the source element to drag
                # Value is the target selector to drop onto
                source_element = self._find_element(selector)
                if not source_element:
                    return {"success": False, "error": f"Source element not found: {selector}"}
                
                target_element = self._find_element(value)
                if not target_element:
                    return {"success": False, "error": f"Target element not found: {value}"}
                
                # Perform drag and drop
                actions = ActionChains(self.driver)
                actions.drag_and_drop(source_element, target_element).perform()
                
                return _finalize_success_result({
                    "success": True,
                    "action": "drag_and_drop",
                    "selector": selector,
                    "value": value
                })
            
            # PRESS KEY ACTION
            elif action == "press_key":
                # Value should be key name: "ENTER", "TAB", "ESCAPE", "ARROW_DOWN", etc.
                from selenium.webdriver.common.keys import Keys
                
                key_mapping = {
                    "ENTER": Keys.ENTER,
                    "TAB": Keys.TAB,
                    "ESCAPE": Keys.ESCAPE,
                    "ESC": Keys.ESCAPE,
                    "SPACE": Keys.SPACE,
                    "BACKSPACE": Keys.BACKSPACE,
                    "DELETE": Keys.DELETE,
                    "ARROW_UP": Keys.ARROW_UP,
                    "ARROW_DOWN": Keys.ARROW_DOWN,
                    "ARROW_LEFT": Keys.ARROW_LEFT,
                    "ARROW_RIGHT": Keys.ARROW_RIGHT,
                    "HOME": Keys.HOME,
                    "END": Keys.END,
                    "PAGE_UP": Keys.PAGE_UP,
                    "PAGE_DOWN": Keys.PAGE_DOWN,
                }
                
                key_value = value.upper() if value else "ENTER"
                key = key_mapping.get(key_value)
                
                if not key:
                    return {"success": False, "error": f"Unknown key: {value}"}
                
                # If selector provided, send key to specific element
                if selector:
                    element = self._find_element(selector)
                    if not element:
                        return {"success": False, "error": f"Element not found: {selector}"}
                    element.send_keys(key)
                else:
                    # Send key to active element
                    ActionChains(self.driver).send_keys(key).perform()
                
                return _finalize_success_result({
                    "success": True,
                    "action": "press_key",
                    "value": value
                })
            
            # CLEAR ACTION
            elif action == "clear":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                element.clear()
                
                return _finalize_success_result({
                    "success": True,
                    "action": "clear",
                    "selector": selector
                })
            
            # WAIT FOR VISIBLE ACTION
            elif action == "wait_for_visible":
                if not selector:
                    return {"success": False, "error": "wait_for_visible requires a selector"}
                
                try:
                    # Determine selector type
                    if selector.startswith('/') or selector.startswith('//'):
                        by_type = By.XPATH
                    else:
                        by_type = By.CSS_SELECTOR
                    
                    # Wait for element to be visible (max 10 seconds)
                    element = WebDriverWait(self.driver, 10).until(
                        EC.visibility_of_element_located((by_type, selector))
                    )
                    
                    return _finalize_success_result({
                        "success": True,
                        "action": "wait_for_visible",
                        "selector": selector
                    })
                except TimeoutException:
                    return {"success": False, "error": f"Element not visible after 10s: {selector}"}
            
            # DOUBLE CLICK ACTION
            elif action == "double_click":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                actions = ActionChains(self.driver)
                actions.double_click(element).perform()
                
                return _finalize_success_result({
                    "success": True,
                    "action": "double_click",
                    "selector": selector
                })
            
            # WAIT FOR HIDDEN ACTION
            elif action == "wait_for_hidden":
                if not selector:
                    return {"success": False, "error": "wait_for_hidden requires a selector"}
                
                try:
                    # Determine selector type
                    if selector.startswith('/') or selector.startswith('//'):
                        by_type = By.XPATH
                    else:
                        by_type = By.CSS_SELECTOR
                    
                    # Wait for element to be invisible (max 10 seconds)
                    WebDriverWait(self.driver, 10).until(
                        EC.invisibility_of_element_located((by_type, selector))
                    )
                    
                    return _finalize_success_result({
                        "success": True,
                        "action": "wait_for_hidden",
                        "selector": selector
                    })
                except TimeoutException:
                    return {"success": False, "error": f"Element still visible after 10s: {selector}"}
            
            # SWITCH TO WINDOW ACTION
            elif action == "switch_to_window":
                # Value should be window index (0, 1, 2, etc.)
                try:
                    window_index = int(value) if value else 1
                    window_handles = self.driver.window_handles
                    
                    if window_index >= len(window_handles):
                        return {"success": False, "error": f"Window index {window_index} out of range (only {len(window_handles)} windows)"}
                    
                    self.driver.switch_to.window(window_handles[window_index])
                    
                    return _finalize_success_result({
                        "success": True,
                        "action": "switch_to_window",
                        "value": value
                    })
                except ValueError:
                    return {"success": False, "error": f"Invalid window index: {value}"}
            
            # SWITCH TO PARENT WINDOW ACTION
            elif action == "switch_to_parent_window":
                # Switch back to first window (index 0)
                window_handles = self.driver.window_handles
                if len(window_handles) > 0:
                    self.driver.switch_to.window(window_handles[0])
                
                return _finalize_success_result({
                    "success": True,
                    "action": "switch_to_parent_window"
                })
            
            # REFRESH ACTION
            elif action == "refresh":
                self.driver.refresh()
                time.sleep(1)  # Wait for page to start reloading
                
                return _finalize_success_result({
                    "success": True,
                    "action": "refresh"
                })
            
            # CHECK ACTION (checkbox - ensure checked)
            elif action == "check":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                # Only click if not already checked
                if not element.is_selected():
                    element.click()
                
                return _finalize_success_result({
                    "success": True,
                    "action": "check",
                    "selector": selector
                })
            
            # UNCHECK ACTION (checkbox - ensure unchecked)
            elif action == "uncheck":
                element = self._find_element(selector)
                if not element:
                    return {"success": False, "error": f"Element not found: {selector}"}
                
                # Only click if currently checked
                if element.is_selected():
                    element.click()
                
                return _finalize_success_result({
                    "success": True,
                    "action": "uncheck",
                    "selector": selector
                })
            
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
                    
                    self.results_logger.error(f"  Selector: {selector}")
                    self.results_logger.error(f"  -------------------")
                    self.results_logger.error(f"  VERIFICATION FAILED")
                    self.info_logger.error(f"Verification failed: Element not found - {selector}")
                    
                    self.capture_screenshot(
                        scenario_description=f"{description}_{time.strftime('%Y%m%d_%H%M%S')}",
                        encode_base64=False,
                        save_to_folder=True
                    )
                    
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
                    
                    self.results_logger.error(f"  Selector: {selector}")
                    self.results_logger.error(f"  -------------------")
                    self.results_logger.error(f"  VERIFICATION FAILED")
                    self.info_logger.error(f"Verification failed: Element not visible - {selector}")
                    
                    self.capture_screenshot(
                        scenario_description=f"{description}_{time.strftime('%Y%m%d_%H%M%S')}",
                        encode_base64=False,
                        save_to_folder=True
                    )
                    
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

                        self.results_logger.error(f"❌ VERIFICATION FAILED - content mismatch")
                        self.results_logger.error(f"Expected: '{expected_value}'")
                        self.results_logger.error(f"Actual: '{actual_value}'")
                        self.results_logger.error(f"  Selector: {selector}")
                        self.results_logger.error(f"----------------------------------------------------------------------")
                        self.info_logger.error(f"Verification failed: Content mismatch - Expected '{expected_value}', Got '{actual_value}'")
                        
                        self.capture_screenshot(
                            scenario_description=f"{description}_{time.strftime('%Y%m%d_%H%M%S')}",
                            encode_base64=False,
                            save_to_folder=True
                        )
                        
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
                self.info_logger.error(f"Unknown action: {action}")
                return {"success": False, "error": f"Unknown action: {action}"}
                
        except NoAlertPresentException as e:
            # Alert was already handled (auto-accepted/dismissed) - this is fine
            if action in ["accept_alert", "dismiss_alert", "fill_alert"]:
                self.info_logger.info(f"Alert already handled for: {description}")
                self.results_logger.info(f"⏭️  Alert already handled - continuing")
                return {"success": True, "action": action, "message": "Alert already handled"}
            else:
                # Not an alert action but got NoAlertPresentException - this is an actual error
                clean_error = self._clean_error_message(e)
                error_msg = f"Step execution failed: {clean_error}"
                self.info_logger.error(error_msg)
                self.results_logger.error(f"ERROR - {description}: {clean_error}")
                
                self.capture_screenshot(
                    scenario_description=f"{description}_ERROR_{time.strftime('%Y%m%d_%H%M%S')}",
                    encode_base64=False,
                    save_to_folder=True
                )
                
                self.results_logger.info("-" * 70)
                return {"success": False, "error": clean_error, "action": action}
                
        except Exception as e:
            clean_error = self._clean_error_message(e)
            error_msg = f"Step execution failed: {clean_error}"
            self.info_logger.error(error_msg)
            self.results_logger.error(f"ERROR - {description}: {clean_error}")
            
            self.capture_screenshot(
                scenario_description=f"{description}_ERROR_{time.strftime('%Y%m%d_%H%M%S')}",
                encode_base64=False,
                save_to_folder=True
            )
            
            self.results_logger.info("-" * 70)
            return {"success": False, "error": clean_error, "action": action}
    
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
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def get_current_url(self) -> Dict:
        """Get current URL"""
        try:
            return {
                "success": True,
                "url": self.driver.current_url
            }
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def get_page_title(self) -> Dict:
        """Get page title"""
        try:
            return {
                "success": True,
                "title": self.driver.title
            }
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}


# ============================================================================
# MULTI-FORMS DISCOVERY AGENT
# ============================================================================

class MultiFormsDiscoveryAgent(AgentSelenium):
    """
    Extended agent for multi-form discovery and crawling operations
    Inherits all functionality from AgentSelenium
    Adds methods needed for recursive form page discovery across web applications
    
    This agent is designed for server-client architecture where:
    - Server: Runs form discovery logic with AI
    - Client: Executes Selenium operations and returns results
    """
    
    def __init__(self, screenshot_folder: Optional[str] = None):
        super().__init__(screenshot_folder)
    
    # ========================================================================
    # ELEMENT FINDING & INTERACTION
    # ========================================================================
    
    def find_elements(self, selector: str, by_type: str = "css") -> Dict:
        """
        Find multiple elements by selector
        
        Args:
            selector: CSS selector or XPath
            by_type: "css" or "xpath"
            
        Returns:
            Dict with success, count, and element info list
        """
        try:
            if by_type == "xpath":
                elements = self.driver.find_elements(By.XPATH, selector)
            else:
                elements = self.driver.find_elements(By.CSS_SELECTOR, selector)
            
            elements_info = []
            for idx, el in enumerate(elements):
                try:
                    elements_info.append({
                        "index": idx,
                        "tag": el.tag_name,
                        "text": (el.text or "").strip(),
                        "displayed": el.is_displayed(),
                        "enabled": el.is_enabled(),
                        "location": el.location
                    })
                except StaleElementReferenceException:
                    continue
            
            return {
                "success": True,
                "count": len(elements_info),
                "elements": elements_info
            }
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "count": 0, "elements": []}
    
    def wait_dom_ready(self, timeout: int = 8) -> Dict:
        """Wait for DOM to be ready"""
        try:
            WebDriverWait(self.driver, timeout).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def scroll_into_view(self, selector: str) -> Dict:
        """Scroll element into view"""
        try:
            element = self._find_element(selector)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            self.driver.execute_script("arguments[0].scrollIntoView({block:'center'})", element)
            return {"success": True}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def safe_click(self, selector: str) -> Dict:
        """Safe click with multiple fallback strategies"""
        try:
            element = self._find_element(selector)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            # Try scroll + ActionChains click
            try:
                self.driver.execute_script("arguments[0].scrollIntoView({block:'center'})", element)
                ActionChains(self.driver).move_to_element(element).pause(0.05).click().perform()
                return {"success": True, "method": "action_chains"}
            except:
                pass
            
            # Try direct click
            try:
                element.click()
                return {"success": True, "method": "direct"}
            except:
                pass
            
            # Try JavaScript click
            try:
                self.driver.execute_script("arguments[0].click();", element)
                return {"success": True, "method": "javascript"}
            except:
                pass
            
            return {"success": False, "error": "All click methods failed"}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error}
    
    def visible_text(self, selector: str) -> Dict:
        """Get visible text from element"""
        try:
            element = self._find_element(selector)
            if not element:
                return {"success": False, "error": f"Element not found: {selector}"}
            
            text = (element.text or "").strip()
            return {"success": True, "text": text}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "text": ""}
    
    # ========================================================================
    # FORM DETECTION
    # ========================================================================
    
    def page_has_form_fields(self, ai_classifier_results: Optional[Dict] = None) -> Dict:
        """
        Check if page has form fields AND submission button in the same container
        
        Args:
            ai_classifier_results: Dict with button text -> is_submission mapping
                                  Example: {"Save": True, "Cancel": False}
        
        Returns:
            Dict with success, has_form, and details
        """
        try:
            input_fields = self.driver.find_elements(By.CSS_SELECTOR,
                                                "input:not([type='hidden']), textarea, select")
            visible_inputs = [f for f in input_fields if f.is_displayed()]
            
            if len(visible_inputs) < 1:
                return {"success": True, "has_form": False, "reason": "No input fields"}
            
            button_blacklist = ['search', 'filter', 'find', 'reset', 'clear', 'back', 'cancel', 'close']
            buttons = self.driver.find_elements(By.CSS_SELECTOR,
                                           "button, input[type='submit'], input[type='button']")
            
            for button in buttons:
                if not button.is_displayed():
                    continue
                
                text = (button.text or button.get_attribute('value') or '').strip()
                if not text:
                    continue
                
                if any(blacklisted in text.lower() for blacklisted in button_blacklist):
                    continue
                
                # Check AI classifier results if provided
                if ai_classifier_results and text in ai_classifier_results:
                    if ai_classifier_results[text]:
                        # Check if button shares container with inputs
                        shares_container = self._check_button_container(button, visible_inputs)
                        if shares_container:
                            return {
                                "success": True,
                                "has_form": True,
                                "submission_button": text,
                                "input_count": len(visible_inputs)
                            }
            
            return {"success": True, "has_form": False, "reason": "No submission button found"}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "has_form": False}
    
    def _check_button_container(self, button, visible_inputs) -> bool:
        """Check if button is in the same parent container as input fields"""
        try:
            result = self.driver.execute_script("""
                var button = arguments[0];
                var inputs = arguments[1];
                
                function getAncestors(el, maxDepth) {
                    var ancestors = [];
                    var current = el;
                    var depth = 0;
                    while (current && current.tagName !== 'BODY' && depth < maxDepth) {
                        ancestors.push(current);
                        current = current.parentElement;
                        depth++;
                    }
                    return ancestors;
                }
                
                var buttonAncestors = getAncestors(button, 10);
                
                for (var i = 0; i < inputs.length; i++) {
                    var inputAncestors = getAncestors(inputs[i], 10);
                    
                    for (var j = 0; j < buttonAncestors.length; j++) {
                        for (var k = 0; k < inputAncestors.length; k++) {
                            if (buttonAncestors[j] === inputAncestors[k]) {
                                return true;
                            }
                        }
                    }
                }
                
                return false;
            """, button, visible_inputs)
            
            return result
            
        except Exception:
            return True
    
    # ========================================================================
    # ELEMENT SEARCHING
    # ========================================================================
    
    def find_clickables_by_keywords(self, keywords: List[str]) -> Dict:
        """Find clickable elements by keyword matching"""
        try:
            els = self.driver.find_elements(By.XPATH, "//*")
            matches = []
            seen = set()
            
            for el in els:
                try:
                    if not el.is_displayed():
                        continue
                    tag = el.tag_name.lower()
                    if tag in ("script", "style", "meta", "link"):
                        continue
                    txt = (el.text or "").strip().lower()
                    if not txt or len(txt) > 100:
                        continue
                    if any(k in txt for k in keywords):
                        key = (tag, txt, el.location.get("y", 0), el.location.get("x", 0))
                        if key not in seen:
                            matches.append({
                                "tag": tag,
                                "text": txt,
                                "location": el.location
                            })
                            seen.add(key)
                except StaleElementReferenceException:
                    continue
            
            matches.sort(key=lambda e: e['location'].get("y", 0))
            return {"success": True, "count": len(matches), "elements": matches}
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "count": 0, "elements": []}
    
    def all_inputs_on_page(self) -> Dict:
        """Get all input elements on page"""
        try:
            inputs = []
            for css in ("input", "select", "textarea"):
                elements = self.driver.find_elements(By.CSS_SELECTOR, css)
                for el in elements:
                    try:
                        inputs.append({
                            "tag": el.tag_name,
                            "type": el.get_attribute("type"),
                            "name": el.get_attribute("name"),
                            "id": el.get_attribute("id"),
                            "displayed": el.is_displayed()
                        })
                    except StaleElementReferenceException:
                        continue
            
            return {"success": True, "count": len(inputs), "inputs": inputs}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "count": 0, "inputs": []}
    
    # ========================================================================
    # ERROR & POPUP HANDLING
    # ========================================================================
    
    def collect_error_messages(self) -> Dict:
        """Collect error messages from page"""
        ERROR_SELECTORS = [
            ".error", ".error-message", ".invalid-feedback",
            ".validation-error", ".help-block.error", ".text-danger",
            ".is-invalid + .invalid-feedback", "[role='alert']", "[aria-invalid='true']"
        ]
        
        try:
            msgs = []
            for sel in ERROR_SELECTORS:
                try:
                    for el in self.driver.find_elements(By.CSS_SELECTOR, sel):
                        if el.is_displayed():
                            t = (el.text or "").strip()
                            if t:
                                msgs.append(t)
                except:
                    continue
            
            unique_msgs = list(dict.fromkeys(msgs))
            return {"success": True, "count": len(unique_msgs), "messages": unique_msgs}
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {"success": False, "error": clean_error, "count": 0, "messages": []}
    
    def dismiss_all_popups_and_overlays(self) -> Dict:
        """Dismiss ALL popups: cookies, modals, overlays, chat widgets"""
        try:
            dismissed_count = 0
            
            cookie_selectors = [
                "//button[contains(translate(., 'ACCEPT', 'accept'), 'accept')]",
                "//button[contains(translate(., 'OK', 'ok'), 'ok')]",
                "//a[contains(translate(., 'ACCEPT', 'accept'), 'accept')]",
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
    
    def get_stable_dom(self, timeout: int = 10) -> Dict:
        """
        Wait for page content to stabilize, then return DOM
        All waiting happens locally on agent side to minimize network calls
        
        This ensures dynamic content (AJAX, React, Vue) has finished loading
        before returning the DOM to the orchestrator
        
        Args:
            timeout: Maximum seconds to wait for stability (default 10)
            
        Returns:
            Dict with success and html content:
            {
                "success": True,
                "html": "...",
                "stable": True,  # Whether DOM stabilized or timed out
                "wait_time": 3.5  # How long it waited
            }
        """
        try:
            import time
            start_time = time.time()
            
            # First wait for basic DOM ready
            self.wait_dom_ready()
            time.sleep(0.5)  # Small delay for initial rendering
            
            # Now wait for DOM to stop changing (AJAX/dynamic content)
            previous_dom = None
            stable_count = 0
            attempts = 0
            max_attempts = int(timeout / 0.5)  # Check every 0.5 seconds
            
            while attempts < max_attempts:
                current_dom = self.driver.page_source
                
                # Check if DOM is unchanged
                if current_dom == previous_dom:
                    stable_count += 1
                    # If stable for 3 consecutive checks (1.5 seconds), we're done
                    if stable_count >= 3:
                        wait_time = time.time() - start_time
                        return {
                            "success": True,
                            "html": current_dom,
                            "stable": True,
                            "wait_time": round(wait_time, 2)
                        }
                else:
                    # DOM changed, reset counter
                    stable_count = 0
                
                previous_dom = current_dom
                time.sleep(0.5)
                attempts += 1
            
            # Timeout reached - return whatever we have
            wait_time = time.time() - start_time
            return {
                "success": True,
                "html": self.driver.page_source,
                "stable": False,  # Timed out, might not be fully stable
                "wait_time": round(wait_time, 2)
            }
            
        except Exception as e:
            clean_error = self._clean_error_message(e)
            return {
                "success": False,
                "error": clean_error,
                "html": "",
                "stable": False,
                "wait_time": 0
            }
