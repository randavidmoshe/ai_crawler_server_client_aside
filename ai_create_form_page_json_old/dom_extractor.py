"""
DOM Extractor
Extracts relevant DOM elements from Selenium WebDriver for AI analysis
"""

from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from typing import List, Dict
from lxml import html, etree


class DOMExtractor:
    """Extracts and filters DOM for form mapping"""
    
    def __init__(self, driver):
        """
        Args:
            driver: Selenium WebDriver instance
        """
        self.driver = driver
        self.current_iframe_path = []  # Track iframe nesting
        self.shadow_dom_paths = []  # Track shadow DOM hosts
        self.default_stability_timeout = 30  # Max wait for page stability
        self.ajax_check_interval = 0.5  # Check every 500ms
        
    def extract_interactive_elements(self) -> str:
        """
        Extract only interactive/relevant elements from the page
        Including iframes and shadow DOM
        
        Returns:
            HTML string with interactive elements and context markers
        """
        # Wait for page to be fully stable before extraction
        self._wait_for_page_stability()
        
        # Get full page source
        page_source = self.driver.page_source
        
        # Parse with lxml
        tree = html.fromstring(page_source)
        
        # NEW: Try to extract entire form container first
        form_html = self._extract_entire_form(tree)
        if form_html:
            return form_html
        
        # Fallback: Extract interactive elements from main document
        interactive_html = self._build_comprehensive_dom(tree)
        
        return interactive_html
    
    def _extract_entire_form(self, tree) -> str:
        """
        Extract the entire form element with all its structure preserved
        This includes parent divs with classes like 'hidden', labels, etc.
        
        Returns:
            HTML string of complete form, or None if no form found
        """
        from lxml import etree
        
        try:
            # Find the main form element
            forms = tree.xpath('//form')
            
            if not forms:
                return None
            
            # Use the first form (or largest if multiple)
            main_form = forms[0]
            if len(forms) > 1:
                # Find the form with most inputs
                main_form = max(forms, key=lambda f: len(f.xpath('.//input | .//select | .//textarea')))
            
            # Convert form to HTML string (preserves all structure)
            form_html = etree.tostring(main_form, encoding='unicode', method='html')
            
            # Wrap in minimal HTML structure
            output = ['<html>', '<body>']
            output.append(form_html)
            
            # Still extract iframes and shadow DOM separately
            iframe_elements = self._extract_from_iframes()
            if iframe_elements:
                output.extend(iframe_elements)
            
            shadow_elements = self._extract_from_shadow_dom()
            if shadow_elements:
                output.extend(shadow_elements)
            
            output.extend(['</body>', '</html>'])
            
            return '\n'.join(output)
            
        except Exception as e:
            print(f"  ⚠️ Could not extract entire form: {e}")
            return None
    
    def _wait_for_page_stability(self, max_wait: int = 30):
        """
        Wait for page to be fully stable before extracting DOM
        Comprehensive checks for:
        - Document ready state
        - Loading indicators to disappear
        - AJAX/fetch calls to complete  
        - Framework rendering (React/Angular/Vue)
        - DOM mutations to stop
        - Animations to finish
        
        Args:
            max_wait: Maximum seconds to wait
        """
        import time
        from selenium.webdriver.support.ui import WebDriverWait
        from selenium.webdriver.support import expected_conditions as EC
        from selenium.webdriver.common.by import By
        
        start_time = time.time()
        print(f"  ⏳ Waiting for page to stabilize (max {max_wait}s)...")
        
        # Step 1: Wait for document.readyState = 'complete'
        try:
            WebDriverWait(self.driver, max_wait).until(
                lambda d: d.execute_script("return document.readyState") == "complete"
            )
            print("    ✓ Document ready")
        except:
            print("    ⚠ Document ready timeout")
        
        # Step 2: Wait for common loading indicators to disappear
        self._wait_for_loading_indicators(timeout=min(10, max_wait))
        
        # Step 3: Wait for AJAX/fetch calls to complete
        self._wait_for_ajax_complete(timeout=min(5, max_wait))
        
        # Step 4: Wait for frameworks to stabilize (React/Angular/Vue)
        self._wait_for_framework_stability(timeout=min(5, max_wait))
        
        # Step 5: Wait for DOM to stop changing (no more mutations)
        self._wait_for_dom_stability(timeout=min(5, max_wait))
        
        # Step 6: Final buffer wait for animations/transitions
        time.sleep(1)
        
        elapsed = time.time() - start_time
        print(f"    ✓ Page stable after {elapsed:.1f}s")

        print(f"  ⏱ Page stabilized in {elapsed:.2f}s")
    
    def _wait_for_loading_indicators(self, timeout: int = 10):
        """
        Wait for common loading indicators to disappear
        Checks for spinners, progress bars, overlays, and framework-specific loaders
        
        Args:
            timeout: Maximum seconds to wait
        """
        import time
        from selenium.common.exceptions import TimeoutException
        from selenium.webdriver.common.by import By
        
        # Comprehensive list of loading indicator selectors
        loading_selectors = [
            # Generic spinners
            '//*[contains(@class, "spinner")]',
            '//*[contains(@class, "loading")]',
            '//*[contains(@class, "loader")]',
            # Progress bars
            '//*[contains(@class, "progress")]',
            '//*[@role="progressbar"]',
            # Loading text
            '//*[contains(text(), "Loading")]',
            '//*[contains(text(), "Please wait")]',
            '//*[contains(text(), "Processing")]',
            # Overlays
            '//*[contains(@class, "overlay")]',
            '//*[contains(@class, "backdrop")]',
            '//*[contains(@class, "modal-backdrop")]',
            # Skeleton loaders
            '//*[contains(@class, "skeleton")]',
            '//*[contains(@class, "placeholder")]',
            # Material UI
            '//*[contains(@class, "MuiCircularProgress")]',
            '//*[contains(@class, "MuiLinearProgress")]',
            '//*[contains(@class, "MuiBackdrop")]',
            # Ant Design
            '//*[contains(@class, "ant-spin")]',
            '//*[contains(@class, "ant-skeleton")]',
            # Bootstrap
            '//*[contains(@class, "spinner-border")]',
            '//*[contains(@class, "spinner-grow")]',
            # Aria attributes
            '//*[@aria-busy="true"]',
            '//*[@aria-live="polite"]',
            # IDs
            '//*[@id="loading"]',
            '//*[@id="spinner"]',
            '//*[@id="loader"]',
        ]
        
        start_time = time.time()
        found_any_loader = False
        
        for selector in loading_selectors:
            if time.time() - start_time > timeout:
                break
                
            try:
                # Check if loading indicator exists and is visible
                elements = self.driver.find_elements(By.XPATH, selector)
                visible_elements = [el for el in elements if el.is_displayed()]
                
                if visible_elements:
                    if not found_any_loader:
                        print(f"    ⏳ Loading indicator found: {selector[:50]}...")
                        found_any_loader = True
                    
                    # Wait for it to disappear
                    from selenium.webdriver.support.ui import WebDriverWait
                    from selenium.webdriver.support import expected_conditions as EC
                    
                    try:
                        WebDriverWait(self.driver, min(timeout - (time.time() - start_time), 1)).until(
                            EC.invisibility_of_element_located((By.XPATH, selector))
                        )
                    except TimeoutException:
                        # Timeout is OK - loader might be persistent, move on
                        pass
                        
            except Exception as e:
                # Element not found or error - that's OK
                pass
        
        if found_any_loader:
            print("    ✓ Loading indicators cleared")
    
    def _wait_for_ajax_complete(self, timeout: int = 5):
        """
        Wait for all AJAX/fetch calls to complete
        Checks: jQuery.active, fetch promises, XMLHttpRequest, and app-specific trackers
        
        Args:
            timeout: Maximum seconds to wait
        """
        import time
        
        start_time = time.time()
        ajax_detected = False
        
        # Enhanced script to check multiple AJAX/fetch indicators
        script = """
        return (function() {
            // Check jQuery AJAX
            if (typeof jQuery !== 'undefined' && jQuery.active > 0) {
                return {complete: false, reason: 'jQuery.active: ' + jQuery.active};
            }
            
            // Check if document is still loading
            if (document.readyState !== 'complete') {
                return {complete: false, reason: 'document.readyState: ' + document.readyState};
            }
            
            // Check for app-specific pending request trackers
            if (typeof window.__pendingRequests !== 'undefined' && window.__pendingRequests > 0) {
                return {complete: false, reason: '__pendingRequests: ' + window.__pendingRequests};
            }
            
            if (typeof window.pendingAjaxRequests !== 'undefined' && window.pendingAjaxRequests > 0) {
                return {complete: false, reason: 'pendingAjaxRequests: ' + window.pendingAjaxRequests};
            }
            
            // Check for active XMLHttpRequest (if tracked)
            if (typeof window.activeAjaxConnections !== 'undefined' && window.activeAjaxConnections > 0) {
                return {complete: false, reason: 'activeAjaxConnections: ' + window.activeAjaxConnections};
            }
            
            return {complete: true};
        })();
        """
        
        while time.time() - start_time < timeout:
            try:
                result = self.driver.execute_script(script)
                
                # Handle both old boolean return and new object return
                if isinstance(result, dict):
                    if not result.get('complete', True):
                        if not ajax_detected:
                            print(f"    ⏳ AJAX detected: {result.get('reason', 'unknown')}")
                            ajax_detected = True
                        time.sleep(0.2)
                        continue
                    else:
                        if ajax_detected:
                            print("    ✓ AJAX calls complete")
                        return
                elif result == True or result is None:
                    # Old boolean format or complete
                    return
                else:
                    # False - still pending
                    if not ajax_detected:
                        ajax_detected = True
                    time.sleep(0.2)
                    continue
                    
            except Exception as e:
                # Script error - assume complete
                return
            
            time.sleep(0.2)
    
    def _wait_for_framework_stability(self, timeout: int = 5):
        """
        Wait for modern JavaScript frameworks to finish rendering
        Supports: React, Angular, Vue, and checks for general rendering completion
        
        Args:
            timeout: Maximum seconds to wait
        """
        import time
        
        start_time = time.time()
        
        # Check for React
        try:
            has_react = self.driver.execute_script("""
                return typeof React !== 'undefined' || 
                       document.querySelector('[data-reactroot]') !== null ||
                       document.querySelector('[data-reactid]') !== null ||
                       document.querySelector('[data-react]') !== null ||
                       document.querySelector('#root') !== null;
            """)
            
            if has_react:
                print("    ⏳ React detected, waiting for render...")
                # React doesn't expose a stable API, wait for requestAnimationFrame
                time.sleep(0.5)
                # Check if still rendering by looking for React devtools markers
                self.driver.execute_script("""
                    return new Promise(resolve => {
                        requestAnimationFrame(() => {
                            requestAnimationFrame(() => resolve());
                        });
                    });
                """)
        except Exception as e:
            pass
        
        # Check for Angular
        try:
            angular_stable = self.driver.execute_script("""
                // Angular 2+
                if (typeof getAllAngularTestabilities === 'function') {
                    var testabilities = getAllAngularTestabilities();
                    if (testabilities && testabilities.length > 0) {
                        return testabilities.every(function(t) { 
                            return t.isStable && t.isStable(); 
                        });
                    }
                }
                
                // AngularJS (1.x)
                if (typeof angular !== 'undefined') {
                    var injector = angular.element(document).injector();
                    if (injector) {
                        var $http = injector.get('$http');
                        var $timeout = injector.get('$timeout');
                        return $http.pendingRequests.length === 0;
                    }
                }
                
                return true; // No Angular found
            """)
            
            if not angular_stable:
                print("    ⏳ Angular detected, waiting for stability...")
                wait_count = 0
                while time.time() - start_time < timeout and wait_count < 20:
                    time.sleep(0.3)
                    angular_stable = self.driver.execute_script("""
                        if (typeof getAllAngularTestabilities === 'function') {
                            var testabilities = getAllAngularTestabilities();
                            if (testabilities && testabilities.length > 0) {
                                return testabilities.every(function(t) { 
                                    return t.isStable && t.isStable(); 
                                });
                            }
                        }
                        return true;
                    """)
                    
                    if angular_stable:
                        print("    ✓ Angular stable")
                        break
                    wait_count += 1
                    
        except Exception as e:
            pass
        
        # Check for Vue.js
        try:
            has_vue = self.driver.execute_script("""
                return typeof Vue !== 'undefined' || 
                       document.querySelector('[data-v-]') !== null ||
                       document.querySelector('#app') !== null;
            """)
            
            if has_vue:
                print("    ⏳ Vue detected, waiting for render...")
                # Vue doesn't have a built-in stability API
                # Wait for nextTick cycles to complete
                time.sleep(0.5)
                self.driver.execute_script("""
                    if (typeof Vue !== 'undefined' && Vue.nextTick) {
                        return new Promise(function(resolve) {
                            Vue.nextTick(function() {
                                Vue.nextTick(function() {
                                    resolve();
                                });
                            });
                        });
                    }
                """)
        except Exception as e:
            pass
        
        # General check: Wait for requestAnimationFrame cycles
        try:
            self.driver.execute_script("""
                return new Promise(function(resolve) {
                    requestAnimationFrame(function() {
                        requestAnimationFrame(function() {
                            requestAnimationFrame(function() {
                                resolve();
                            });
                        });
                    });
                });
            """)
        except:
            pass
    
    def _wait_for_dom_stability(self, timeout: int = 3, check_interval: float = 0.3):
        """
        Wait for DOM to stop changing
        Compares DOM snapshots to detect when mutations stop
        
        Args:
            timeout: Maximum seconds to wait
            check_interval: Seconds between stability checks
        """
        import time
        
        script = """
        return document.body ? document.body.innerHTML.length : 0;
        """
        
        start_time = time.time()
        previous_length = 0
        stable_count = 0
        
        while time.time() - start_time < timeout:
            try:
                current_length = self.driver.execute_script(script)
                
                # Check if DOM size is stable
                if current_length == previous_length:
                    stable_count += 1
                    # If stable for 2 consecutive checks, consider it done
                    if stable_count >= 2:
                        return
                else:
                    stable_count = 0
                
                previous_length = current_length
                
            except:
                # Error getting DOM - assume stable
                return
            
            time.sleep(check_interval)
    
    def _build_comprehensive_dom(self, tree) -> str:
        """
        Build comprehensive DOM including iframes and shadow DOM
        
        Args:
            tree: lxml HTML tree
            
        Returns:
            HTML string with all interactive elements and context markers
        """
        output_lines = ['<html>', '<body>']
        
        # Extract main document elements
        main_elements = self._extract_elements_from_tree(tree, context="main")
        output_lines.extend(main_elements)
        
        # Extract from iframes
        iframe_elements = self._extract_from_iframes()
        output_lines.extend(iframe_elements)
        
        # Extract from shadow DOM
        shadow_elements = self._extract_from_shadow_dom()
        output_lines.extend(shadow_elements)
        
        # Extract JavaScript for dynamic behavior analysis
        js_info = self._extract_javascript_info()
        if js_info:
            output_lines.append("\n<!-- JAVASCRIPT BEHAVIOR ANALYSIS -->")
            output_lines.extend(js_info)
        
        # Extract external scripts
        external_scripts = self._extract_external_scripts()
        if external_scripts:
            output_lines.append("\n<!-- EXTERNAL SCRIPTS CONTENT -->")
            output_lines.extend(external_scripts)
        
        output_lines.extend(['</body>', '</html>'])
        
        return '\n'.join(output_lines)
    
    def _extract_from_iframes(self) -> List[str]:
        """
        Extract elements from all iframes in the page
        
        Returns:
            List of HTML strings with iframe context markers
        """
        output = []
        
        try:
            # Find all iframes
            iframes = self.driver.find_elements(By.TAG_NAME, "iframe")
            
            for i, iframe in enumerate(iframes):
                try:
                    # Get iframe identifier
                    iframe_id = iframe.get_attribute('id') or iframe.get_attribute('name') or f"iframe_{i}"
                    iframe_xpath = self._get_element_xpath(iframe)
                    
                    output.append(f"\n<!-- IFRAME START: {iframe_id} -->")
                    output.append(f"<!-- IFRAME_XPATH: {iframe_xpath} -->")
                    output.append(f"<!-- SELENIUM_ACTION: switch_to_frame, locator={iframe_xpath} -->")
                    
                    # Switch to iframe
                    self.driver.switch_to.frame(iframe)
                    self.current_iframe_path.append(iframe_id)
                    
                    # Extract elements from iframe
                    iframe_source = self.driver.page_source
                    iframe_tree = html.fromstring(iframe_source)
                    iframe_elements = self._extract_elements_from_tree(
                        iframe_tree, 
                        context=f"iframe:{iframe_id}"
                    )
                    output.extend(iframe_elements)
                    
                    # Check for nested iframes
                    nested_iframes = self._extract_from_iframes()
                    if nested_iframes:
                        output.extend(nested_iframes)
                    
                    # Switch back
                    self.driver.switch_to.parent_frame()
                    self.current_iframe_path.pop()
                    
                    output.append(f"<!-- SELENIUM_ACTION: switch_to_parent_frame -->")
                    output.append(f"<!-- IFRAME END: {iframe_id} -->")
                    
                except Exception as e:
                    output.append(f"<!-- ERROR accessing iframe {i}: {str(e)} -->")
                    # Try to switch back in case of error
                    try:
                        self.driver.switch_to.default_content()
                        self.current_iframe_path = []
                    except:
                        pass
        
        except Exception as e:
            output.append(f"<!-- ERROR finding iframes: {str(e)} -->")
        
        return output
    
    def _extract_from_shadow_dom(self) -> List[str]:
        """
        Extract elements from shadow DOM
        
        Returns:
            List of HTML strings with shadow DOM context markers
        """
        output = []
        
        try:
            # JavaScript to find all shadow roots and extract their content
            script = """
            function extractShadowDOM() {
                const results = [];
                
                function traverse(node, path = []) {
                    if (node.shadowRoot) {
                        const shadowHost = {
                            xpath: getXPath(node),
                            tagName: node.tagName,
                            id: node.id,
                            classes: node.className,
                            path: path.join(' > '),
                            content: node.shadowRoot.innerHTML
                        };
                        results.push(shadowHost);
                        
                        // Traverse shadow DOM children
                        node.shadowRoot.querySelectorAll('*').forEach(child => {
                            traverse(child, [...path, 'shadow-root']);
                        });
                    }
                    
                    // Traverse regular DOM children
                    node.querySelectorAll(':scope > *').forEach(child => {
                        traverse(child, [...path, child.tagName.toLowerCase()]);
                    });
                }
                
                function getXPath(element) {
                    if (element.id) return `//*[@id="${element.id}"]`;
                    
                    const parts = [];
                    while (element && element.nodeType === Node.ELEMENT_NODE) {
                        let index = 0;
                        let sibling = element.previousSibling;
                        while (sibling) {
                            if (sibling.nodeType === Node.ELEMENT_NODE && 
                                sibling.nodeName === element.nodeName) {
                                index++;
                            }
                            sibling = sibling.previousSibling;
                        }
                        
                        const tagName = element.nodeName.toLowerCase();
                        const part = index > 0 ? `${tagName}[${index + 1}]` : tagName;
                        parts.unshift(part);
                        element = element.parentNode;
                    }
                    
                    return parts.length ? '/' + parts.join('/') : '';
                }
                
                traverse(document.body);
                return results;
            }
            
            return extractShadowDOM();
            """
            
            shadow_roots = self.driver.execute_script(script)
            
            for shadow_info in shadow_roots:
                shadow_host_xpath = shadow_info['xpath']
                
                output.append(f"\n<!-- SHADOW DOM START: {shadow_info['tagName']} -->")
                output.append(f"<!-- SHADOW_HOST_XPATH: {shadow_host_xpath} -->")
                output.append(f"<!-- SELENIUM_ACTION: access_shadow_root, host_xpath={shadow_host_xpath} -->")
                
                # Parse shadow DOM content
                try:
                    shadow_tree = html.fromstring(shadow_info['content'])
                    shadow_elements = self._extract_elements_from_tree(
                        shadow_tree,
                        context=f"shadow:{shadow_info['tagName']}"
                    )
                    output.extend(shadow_elements)
                except Exception as e:
                    output.append(f"<!-- ERROR parsing shadow DOM: {str(e)} -->")
                
                output.append(f"<!-- SHADOW DOM END -->")
        
        except Exception as e:
            output.append(f"<!-- ERROR extracting shadow DOM: {str(e)} -->")
        
        return output
    
    def _extract_javascript_info(self) -> List[str]:
        """
        Extract JavaScript event handlers and dynamic behavior
        
        Returns:
            List of strings describing JS behavior
        """
        output = []
        
        try:
            script = """
            function analyzeJavaScript() {
                const info = [];
                
                // Find elements with event listeners
                document.querySelectorAll('*').forEach(el => {
                    const listeners = [];
                    
                    // Check common events
                    ['onclick', 'onchange', 'onmouseover', 'onfocus', 'onblur'].forEach(event => {
                        if (el[event]) {
                            listeners.push({
                                event: event,
                                handler: el[event].toString().substring(0, 200)
                            });
                        }
                    });
                    
                    if (listeners.length > 0) {
                        info.push({
                            xpath: getXPath(el),
                            tag: el.tagName,
                            id: el.id,
                            listeners: listeners
                        });
                    }
                });
                
                function getXPath(element) {
                    if (element.id) return `//*[@id="${element.id}"]`;
                    
                    const parts = [];
                    while (element && element.nodeType === Node.ELEMENT_NODE) {
                        let index = 0;
                        let sibling = element.previousSibling;
                        while (sibling) {
                            if (sibling.nodeType === Node.ELEMENT_NODE && 
                                sibling.nodeName === element.nodeName) {
                                index++;
                            }
                            sibling = sibling.previousSibling;
                        }
                        
                        const tagName = element.nodeName.toLowerCase();
                        const part = index > 0 ? `${tagName}[${index + 1}]` : tagName;
                        parts.unshift(part);
                        element = element.parentNode;
                    }
                    
                    return parts.length ? '/' + parts.join('/') : '';
                }
                
                return info;
            }
            
            return analyzeJavaScript();
            """
            
            js_info = self.driver.execute_script(script)
            
            for item in js_info[:20]:  # Limit to first 20 to avoid huge output
                output.append(f"<!-- JS_BEHAVIOR xpath={item['xpath']} -->")
                for listener in item['listeners']:
                    output.append(f"<!--   Event: {listener['event']} -->")
                    if 'mouseover' in listener['event'].lower():
                        output.append(f"<!--   REQUIRES_HOVER: true -->")
                    # Truncated handler
                    handler_preview = listener['handler'][:100].replace('\n', ' ')
                    output.append(f"<!--   Handler: {handler_preview}... -->")
        
        except Exception as e:
            output.append(f"<!-- ERROR analyzing JavaScript: {str(e)} -->")
        
        return output
    
    def _extract_external_scripts(self) -> List[str]:
        """
        Extract content from external JavaScript files (script tags with src attribute)
        
        Returns:
            List of strings with script content
        """
        output = []
        
        try:
            from selenium.webdriver.common.by import By
            
            # Find all script tags with src attribute
            script_tags = self.driver.find_elements(By.TAG_NAME, 'script')
            
            for script in script_tags:
                src = script.get_attribute('src')
                if src:
                    try:
                        # Fetch the external script content using JavaScript fetch
                        js_content = self.driver.execute_script(f"""
                            return fetch('{src}')
                                .then(response => response.text())
                                .catch(err => 'ERROR: ' + err.message);
                        """)
                        
                        if js_content and not js_content.startswith('ERROR:'):
                            output.append(f"\n<!-- ========================================= -->")
                            output.append(f"<!-- EXTERNAL JAVASCRIPT FILE: {src} -->")
                            output.append(f"<!-- THIS IS EXECUTABLE JAVASCRIPT CODE - ANALYZE IT! -->")
                            output.append(f"<!-- ========================================= -->")
                            output.append("<script type=\"text/javascript\">")
                            output.append("// JAVASCRIPT CODE STARTS HERE")
                            # Add the actual content
                            output.append(js_content)
                            output.append("// JAVASCRIPT CODE ENDS HERE")
                            output.append("</script>")
                            output.append(f"<!-- ========================================= -->")
                        else:
                            output.append(f"<!-- FAILED TO LOAD SCRIPT: {src} - {js_content} -->")
                    
                    except Exception as e:
                        output.append(f"<!-- ERROR loading script {src}: {str(e)} -->")
        
        except Exception as e:
            output.append(f"<!-- ERROR extracting external scripts: {str(e)} -->")
        
        return output
    
    def _extract_elements_from_tree(self, tree, context: str = "main") -> List[str]:
        """
        Extract interactive elements from an HTML tree
        
        Args:
            tree: lxml HTML tree
            context: Context string (main, iframe:name, shadow:host)
            
        Returns:
            List of HTML element strings
        """
    def _extract_elements_from_tree(self, tree, context: str = "main") -> List[str]:
        """
        Extract interactive elements from an HTML tree
        
        Args:
            tree: lxml HTML tree
            context: Context string (main, iframe:name, shadow:host)
            
        Returns:
            List of HTML element strings
        """
        # Define selectors for interactive elements
        interactive_selectors = [
            '//input',
            '//select',
            '//textarea',
            '//button',
            '//a[@href]',
            '//*[@onclick]',
            '//*[@role="button"]',
            '//*[@role="tab"]',
            '//*[@role="checkbox"]',
            '//*[@role="radio"]',
            '//*[contains(@class, "button")]',
            '//*[contains(@class, "btn")]',
            '//*[contains(@class, "tab")]',
            '//*[contains(@class, "checkbox")]',
            '//*[contains(@class, "radio")]',
            '//*[@type="submit"]',
            '//*[@type="button"]',
            '//*[contains(@id, "button")]',
            '//*[contains(@id, "btn")]',
            '//*[contains(@id, "tab")]',
        ]
        
        # Collect all interactive elements
        interactive_elements = []
        seen_elements = set()
        
        for selector in interactive_selectors:
            elements = tree.xpath(selector)
            for elem in elements:
                # Use element's memory address as unique identifier
                elem_id = id(elem)
                if elem_id not in seen_elements:
                    seen_elements.add(elem_id)
                    interactive_elements.append(elem)
        
        # Build element representations with context
        output = []
        for elem in interactive_elements:
            elem_info = self._get_element_info(elem)
            parent_info = self._get_parent_context(elem)
            
            # Add context marker
            if context != "main":
                output.append(f"<!-- CONTEXT: {context} -->")
            
            elem_str = self._element_to_string(elem, elem_info, parent_info, context)
            output.append(elem_str)
        
        return output
        
        # Collect all interactive elements
        interactive_elements = []
        seen_elements = set()
        
        for selector in interactive_selectors:
            elements = tree.xpath(selector)
            for elem in elements:
                # Use element's memory address as unique identifier
                elem_id = id(elem)
                if elem_id not in seen_elements:
                    seen_elements.add(elem_id)
                    interactive_elements.append(elem)
        
        # Build simplified tree
        simplified = self._create_simplified_tree(interactive_elements)
        
        return simplified
    
    def _create_simplified_tree(self, elements: List) -> str:
        """
        Create a simplified HTML tree with interactive elements and their context
        
        Args:
            elements: List of lxml elements
            
        Returns:
            HTML string
        """
        output_lines = ['<html>', '<body>']
        
        for elem in elements:
            # Get element info
            elem_info = self._get_element_info(elem)
            
            # Get parent context (for grouping)
            parent_info = self._get_parent_context(elem)
            
            # Build element representation
            elem_str = self._element_to_string(elem, elem_info, parent_info)
            output_lines.append(elem_str)
        
        output_lines.extend(['</body>', '</html>'])
        
        return '\n'.join(output_lines)
    
    def _get_element_info(self, elem) -> Dict:
        """
        Extract relevant information from an element
        
        Args:
            elem: lxml element
            
        Returns:
            Dictionary with element info
        """
        elem_id = elem.get('id', '')
        elem_class = elem.get('class', '')
        elem_name = elem.get('name', '')
        
        # Analyze stability of attributes
        id_stable = self._is_stable_value(elem_id)
        class_stable = self._is_stable_value(elem_class)
        
        info = {
            'tag': elem.tag,
            'id': elem_id,
            'id_stable': id_stable,
            'name': elem_name,
            'class': elem_class,
            'class_stable': class_stable,
            'type': elem.get('type', ''),
            'placeholder': elem.get('placeholder', ''),
            'value': elem.get('value', ''),
            'role': elem.get('role', ''),
            'aria_label': elem.get('aria-label', ''),
            'title': elem.get('title', ''),
            'data_testid': elem.get('data-testid', ''),
            'data_id': elem.get('data-id', ''),
            'onclick': elem.get('onclick', ''),
            'xpath': self._get_full_xpath(elem),
            'text': self._get_element_text(elem),
            'stable_locators': self._generate_stable_locators(elem)
        }
        
        # For select elements, get options
        if elem.tag == 'select':
            options = elem.xpath('.//option')
            info['options'] = [
                {
                    'value': opt.get('value', ''),
                    'text': opt.text or ''
                }
                for opt in options
            ]
        
        return info
    
    def _get_parent_context(self, elem) -> Dict:
        """
        Get context from parent elements (labels, fieldsets, etc.)
        
        Args:
            elem: lxml element
            
        Returns:
            Dictionary with parent context
        """
        context = {
            'label': '',
            'fieldset': '',
            'section': ''
        }
        
        # Look for associated label
        elem_id = elem.get('id', '')
        if elem_id:
            # Find label with for attribute
            parent = elem.getparent()
            while parent is not None:
                labels = parent.xpath(f'.//label[@for="{elem_id}"]')
                if labels:
                    context['label'] = labels[0].text_content().strip()
                    break
                parent = parent.getparent()
        
        # Look for parent label (wrapping)
        parent = elem.getparent()
        if parent is not None and parent.tag == 'label':
            context['label'] = parent.text_content().strip()
        
        # Look for parent fieldset
        parent = elem.getparent()
        while parent is not None:
            if parent.tag == 'fieldset':
                legend = parent.find('.//legend')
                if legend is not None:
                    context['fieldset'] = legend.text_content().strip()
                break
            parent = parent.getparent()
        
        return context
    
    def _is_stable_value(self, value: str) -> bool:
        """
        Determine if an attribute value is stable (not dynamically generated)
        
        Args:
            value: Attribute value to check
            
        Returns:
            True if likely stable, False if likely dynamic
        """
        if not value:
            return False
        
        # Patterns that indicate dynamic/generated values
        dynamic_patterns = [
            r'[a-f0-9]{8,}',  # Long hex strings
            r'.*-[a-z0-9]{6,}$',  # Suffix with random chars (component-a3f8b2)
            r'^[a-z]{3,}-[0-9]{3,}',  # Prefix pattern (cls-123)
            r'.*_[0-9]{10,}',  # Timestamp suffix
            r'.*[A-Z]{2,}[a-z]{2,}[0-9]{4,}',  # CamelCase with numbers
            r'^css-[a-z0-9]+',  # CSS-in-JS patterns
            r'^sc-[a-z0-9]+',  # Styled-components patterns
            r'^jss[0-9]+',  # JSS patterns
            r'.*__[a-z0-9]{5,}',  # BEM with hash
        ]
        
        import re
        for pattern in dynamic_patterns:
            if re.search(pattern, value):
                return False
        
        return True
    
    def _generate_stable_locators(self, elem) -> List[Dict]:
        """
        Generate multiple stable locator strategies for an element
        Priority: name > data-testid > stable id > aria-label > placeholder > stable class
        
        Args:
            elem: lxml element
            
        Returns:
            List of locator dictionaries with priority
        """
        locators = []
        
        # Priority 1: name attribute (most stable)
        name = elem.get('name', '')
        if name:
            locators.append({
                'priority': 1,
                'type': 'name',
                'value': name,
                'css': f"[name='{name}']",
                'xpath': f"//*[@name='{name}']"
            })
        
        # Priority 2: data-testid (explicitly for testing)
        test_id = elem.get('data-testid', '') or elem.get('data-test-id', '') or elem.get('data-test', '')
        if test_id:
            locators.append({
                'priority': 2,
                'type': 'data-testid',
                'value': test_id,
                'css': f"[data-testid='{test_id}']",
                'xpath': f"//*[@data-testid='{test_id}']"
            })
        
        # Priority 3: data-id or data-cy (Cypress)
        data_id = elem.get('data-id', '') or elem.get('data-cy', '')
        if data_id:
            locators.append({
                'priority': 3,
                'type': 'data-id',
                'value': data_id,
                'css': f"[data-id='{data_id}']",
                'xpath': f"//*[@data-id='{data_id}']"
            })
        
        # Priority 4: Stable ID
        elem_id = elem.get('id', '')
        if elem_id and self._is_stable_value(elem_id):
            locators.append({
                'priority': 4,
                'type': 'id',
                'value': elem_id,
                'css': f"#{elem_id}",
                'xpath': f"//*[@id='{elem_id}']"
            })
        
        # Priority 5: aria-label
        aria_label = elem.get('aria-label', '')
        if aria_label:
            locators.append({
                'priority': 5,
                'type': 'aria-label',
                'value': aria_label,
                'css': f"[aria-label='{aria_label}']",
                'xpath': f"//*[@aria-label='{aria_label}']"
            })
        
        # Priority 6: placeholder
        placeholder = elem.get('placeholder', '')
        if placeholder:
            locators.append({
                'priority': 6,
                'type': 'placeholder',
                'value': placeholder,
                'css': f"[placeholder='{placeholder}']",
                'xpath': f"//*[@placeholder='{placeholder}']"
            })
        
        # Priority 7: type + stable class combination
        elem_type = elem.get('type', '')
        elem_class = elem.get('class', '')
        if elem_type and elem_class and self._is_stable_value(elem_class):
            # Use first stable class
            classes = elem_class.split()
            stable_classes = [c for c in classes if self._is_stable_value(c)]
            if stable_classes:
                first_stable = stable_classes[0]
                locators.append({
                    'priority': 7,
                    'type': 'type-class',
                    'value': f"{elem_type}.{first_stable}",
                    'css': f"{elem.tag}[type='{elem_type}'].{first_stable}",
                    'xpath': f"//{elem.tag}[@type='{elem_type}' and contains(@class, '{first_stable}')]"
                })
        
        # Priority 8: role attribute
        role = elem.get('role', '')
        if role:
            # Combine with additional attributes for uniqueness
            if name:
                locators.append({
                    'priority': 8,
                    'type': 'role-name',
                    'value': f"{role}+{name}",
                    'css': f"[role='{role}'][name='{name}']",
                    'xpath': f"//*[@role='{role}' and @name='{name}']"
                })
            elif aria_label:
                locators.append({
                    'priority': 8,
                    'type': 'role-aria',
                    'value': f"{role}+{aria_label}",
                    'css': f"[role='{role}'][aria-label='{aria_label}']",
                    'xpath': f"//*[@role='{role}' and @aria-label='{aria_label}']"
                })
        
        # Priority 9: Structural XPath (based on parent/sibling context)
        # Only use if no other stable locators found
        if len(locators) == 0:
            structural_xpath = self._generate_structural_xpath(elem)
            if structural_xpath:
                locators.append({
                    'priority': 9,
                    'type': 'structural-xpath',
                    'value': structural_xpath,
                    'xpath': structural_xpath
                })
        
        # Sort by priority
        locators.sort(key=lambda x: x['priority'])
        
        return locators
    
    def _generate_structural_xpath(self, elem) -> str:
        """
        Generate XPath based on element structure (parent context, label, fieldset)
        More stable than absolute position
        
        Args:
            elem: lxml element
            
        Returns:
            Structural XPath string
        """
        parts = []
        
        # Check for label
        elem_id = elem.get('id', '')
        if elem_id:
            # Try to find label with for attribute
            parent = elem.getparent()
            if parent is not None:
                root = elem.getroottree().getroot()
                labels = root.xpath(f'.//label[@for="{elem_id}"]')
                if labels:
                    label_text = labels[0].text_content().strip()[:30]
                    return f"//label[contains(text(), '{label_text}')]/following::input[1]"
        
        # Check for parent label (wrapping)
        parent = elem.getparent()
        if parent is not None and parent.tag == 'label':
            label_text = parent.text_content().strip()[:30]
            return f"//label[contains(text(), '{label_text}')]//{elem.tag}"
        
        # Check for fieldset context
        current = elem
        while current is not None:
            if current.tag == 'fieldset':
                legend = current.find('.//legend')
                if legend is not None:
                    legend_text = legend.text_content().strip()[:30]
                    # Find position within fieldset
                    return f"//fieldset[.//legend[contains(text(), '{legend_text}')]]//{elem.tag}[@{self._get_unique_attr(elem)}]"
            current = current.getparent()
        
        return ""
    
    def _get_unique_attr(self, elem) -> str:
        """Get most unique attribute for XPath predicate"""
        if elem.get('name'):
            return f"name='{elem.get('name')}'"
        elif elem.get('type'):
            return f"type='{elem.get('type')}'"
        elif elem.get('placeholder'):
            return f"placeholder='{elem.get('placeholder')}'"
        return "1"
    
    def _get_full_xpath(self, elem) -> str:
        """
        Generate full XPath for an element
        
        Args:
            elem: lxml element
            
        Returns:
            Full XPath string
        """
        try:
            tree = elem.getroottree()
            return tree.getpath(elem)
        except:
            return ''
    
    def _get_element_text(self, elem) -> str:
        """
        Get visible text content of element
        
        Args:
            elem: lxml element
            
        Returns:
            Text content
        """
        text = elem.text_content().strip()
        # Limit text length
        if len(text) > 100:
            text = text[:100] + '...'
        return text
    
    def _get_element_xpath(self, element) -> str:
        """
        Get XPath for a Selenium WebElement
        
        Args:
            element: Selenium WebElement
            
        Returns:
            XPath string
        """
        try:
            script = """
            function getXPath(element) {
                if (element.id) return `//*[@id="${element.id}"]`;
                
                const parts = [];
                while (element && element.nodeType === Node.ELEMENT_NODE) {
                    let index = 0;
                    let sibling = element.previousSibling;
                    while (sibling) {
                        if (sibling.nodeType === Node.ELEMENT_NODE && 
                            sibling.nodeName === element.nodeName) {
                            index++;
                        }
                        sibling = sibling.previousSibling;
                    }
                    
                    const tagName = element.nodeName.toLowerCase();
                    const part = index > 0 ? `${tagName}[${index + 1}]` : tagName;
                    parts.unshift(part);
                    element = element.parentNode;
                }
                
                return parts.length ? '/' + parts.join('/') : '';
            }
            return getXPath(arguments[0]);
            """
            return self.driver.execute_script(script, element)
        except:
            return ""
    
    def _element_to_string(self, elem, elem_info: Dict, parent_info: Dict, context: str = "main") -> str:
        """
        Convert element to readable string representation with context
        
        Args:
            elem: lxml element
            elem_info: Element information dictionary
            parent_info: Parent context dictionary
            context: Context string
            
        Returns:
            String representation
        """
        lines = []
        
        # Add context if not main
        if context != "main":
            lines.append(f"<!-- ELEMENT_CONTEXT: {context} -->")
        
        # Add comment with context
        if parent_info['label']:
            lines.append(f"<!-- Label: {parent_info['label']} -->")
        if parent_info['fieldset']:
            lines.append(f"<!-- Fieldset: {parent_info['fieldset']} -->")
        
        # Check for visibility attributes
        style = elem.get('style', '')
        css_class = elem.get('class', '')
        if 'display:none' in style or 'display: none' in style:
            lines.append(f"<!-- VISIBILITY: hidden (CSS display:none) -->")
        if 'hidden' in css_class.lower():
            lines.append(f"<!-- VISIBILITY: possibly hidden (class contains 'hidden') -->")
        
        # Check for role-based visibility
        aria_hidden = elem.get('aria-hidden', '')
        if aria_hidden == 'true':
            lines.append(f"<!-- VISIBILITY: hidden (aria-hidden=true) -->")
        
        # Build element tag
        tag = elem_info['tag']
        attrs = []
        
        if elem_info['id']:
            attrs.append(f'id="{elem_info["id"]}"')
        if elem_info['name']:
            attrs.append(f'name="{elem_info["name"]}"')
        if elem_info['class']:
            attrs.append(f'class="{elem_info["class"]}"')
        if elem_info['type']:
            attrs.append(f'type="{elem_info["type"]}"')
        if elem_info['placeholder']:
            attrs.append(f'placeholder="{elem_info["placeholder"]}"')
        if elem_info['role']:
            attrs.append(f'role="{elem_info["role"]}"')
        if elem_info['aria_label']:
            attrs.append(f'aria-label="{elem_info["aria_label"]}"')
        
        # Add data-xpath attribute for reference
        attrs.append(f'data-xpath="{elem_info["xpath"]}"')
        
        # Add context marker
        if context != "main":
            attrs.append(f'data-context="{context}"')
        
        attr_str = ' '.join(attrs)
        
        # Build element string
        if tag in ['input', 'img', 'br', 'hr']:
            elem_str = f"<{tag} {attr_str} />"
        else:
            content = elem_info['text'][:50] if elem_info['text'] else ''
            
            # For select, add options
            if tag == 'select' and 'options' in elem_info:
                option_strs = [
                    f'<option value="{opt["value"]}">{opt["text"]}</option>'
                    for opt in elem_info['options'][:10]  # Limit to first 10
                ]
                content = '\n  '.join(option_strs)
                elem_str = f"<{tag} {attr_str}>\n  {content}\n</{tag}>"
            else:
                elem_str = f"<{tag} {attr_str}>{content}</{tag}>"
        
        lines.append(elem_str)
        
        return '\n'.join(lines)
    
    def get_element_by_xpath(self, xpath: str):
        """
        Get Selenium WebElement by XPath
        
        Args:
            xpath: XPath string
            
        Returns:
            WebElement or None
        """
        try:
            element = WebDriverWait(self.driver, 10).until(
                EC.presence_of_element_located((By.XPATH, xpath))
            )
            return element
        except:
            return None
    
    def extract_full_dom(self) -> str:
        """
        Extract the complete DOM (for debugging purposes)
        
        Returns:
            Full HTML source
        """
        return self.driver.page_source
    
    def highlight_element(self, xpath: str):
        """
        Highlight an element on the page (useful for debugging)
        
        Args:
            xpath: XPath of element to highlight
        """
        try:
            element = self.get_element_by_xpath(xpath)
            if element:
                self.driver.execute_script(
                    "arguments[0].style.border='3px solid red'",
                    element
                )
        except:
            pass


def test_extractor():
    """Test the DOM extractor with a sample page"""
    from selenium import webdriver
    
    driver = webdriver.Chrome()
    driver.get("https://www.example.com")
    
    extractor = DOMExtractor(driver)
    
    # Extract interactive elements
    interactive_dom = extractor.extract_interactive_elements()
    
    print("=== INTERACTIVE DOM ===")
    print(interactive_dom)
    
    # Save to file
    with open('extracted_dom.html', 'w', encoding='utf-8') as f:
        f.write(interactive_dom)
    
    print("\nExtracted DOM saved to: extracted_dom.html")
    
    driver.quit()


if __name__ == "__main__":
    test_extractor()
