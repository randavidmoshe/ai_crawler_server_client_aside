"""
Selenium Executor
Executes Selenium actions based on AI-generated instructions
"""

import time
from typing import List, Dict, Optional
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.webdriver.common.action_chains import ActionChains


class SeleniumExecutor:
    """Executes Selenium actions from AI-generated action sequences"""
    
    def __init__(self, driver, default_timeout: int = 10):
        """
        Args:
            driver: Selenium WebDriver instance
            default_timeout: Default timeout for wait operations
        """
        self.driver = driver
        self.default_timeout = default_timeout
        self.action_handlers = {
            'click': self._handle_click,
            'enter_text': self._handle_enter_text,
            'clear_text': self._handle_clear_text,
            'select_dropdown': self._handle_select_dropdown,
            'select_dropdown_by_text': self._handle_select_dropdown_by_text,
            'click_checkbox': self._handle_click_checkbox,
            'click_radio': self._handle_click_radio,
            'hover': self._handle_hover,
            'scroll_to': self._handle_scroll_to,
            'wait_for_element': self._handle_wait_for_element,
            'wait_for_clickable': self._handle_wait_for_clickable,
            'wait_for_visible': self._handle_wait_for_visible,
            'sleep': self._handle_sleep,
            'press_key': self._handle_press_key,
            'upload_file': self._handle_upload_file,
            'switch_to_frame': self._handle_switch_to_frame,
            'switch_to_parent_frame': self._handle_switch_to_parent_frame,
            'switch_to_default': self._handle_switch_to_default,
            'access_shadow_root': self._handle_access_shadow_root,
            'execute_script': self._handle_execute_script
        }
    
    def execute_actions(self, actions: List[Dict]) -> bool:
        """
        Execute a sequence of Selenium actions
        
        Args:
            actions: List of action dictionaries
            
        Returns:
            True if all actions succeeded, False otherwise
        """
        for i, action in enumerate(actions):
            try:
                action_type = action.get('action', '')
                
                if action_type not in self.action_handlers:
                    print(f"Warning: Unknown action type: {action_type}")
                    continue
                
                print(f"  [{i+1}/{len(actions)}] Executing: {action_type}")
                
                # Execute action
                handler = self.action_handlers[action_type]
                success = handler(action)
                
                if not success:
                    print(f"  ✗ Failed to execute: {action_type}")
                    return False
                    
            except Exception as e:
                print(f"  ✗ Error executing {action_type}: {str(e)}")
                return False
        
        return True
    
    def _get_element(self, action: Dict):
        """
        Get element from action parameters
        
        Args:
            action: Action dictionary with locator info
            
        Returns:
            WebElement or None
        """
        locator = action.get('locator', '')
        locator_type = action.get('locator_type', 'xpath').lower()
        timeout = action.get('timeout', self.default_timeout)
        
        by_type = self._get_by_type(locator_type)
        
        try:
            element = WebDriverWait(self.driver, timeout).until(
                EC.presence_of_element_located((by_type, locator))
            )
            return element
        except Exception as e:
            print(f"    Element not found: {locator}")
            return None
    
    def _get_by_type(self, locator_type: str):
        """Convert locator type string to Selenium By type"""
        mapping = {
            'xpath': By.XPATH,
            'css': By.CSS_SELECTOR,
            'id': By.ID,
            'name': By.NAME,
            'class': By.CLASS_NAME,
            'tag': By.TAG_NAME,
            'link_text': By.LINK_TEXT,
            'partial_link_text': By.PARTIAL_LINK_TEXT
        }
        return mapping.get(locator_type, By.XPATH)
    
    # Action Handlers
    
    def _handle_click(self, action: Dict) -> bool:
        """Handle click action"""
        element = self._get_element(action)
        if not element:
            return False
        
        try:
            # Try regular click first
            element.click()
        except Exception as e:
            # If regular click fails, try JavaScript click
            try:
                self.driver.execute_script("arguments[0].click();", element)
            except:
                return False
        
        return True
    
    def _handle_enter_text(self, action: Dict) -> bool:
        """Handle text entry action"""
        element = self._get_element(action)
        if not element:
            return False
        
        text = action.get('text', action.get('value', ''))
        clear_first = action.get('clear_first', True)
        
        try:
            if clear_first:
                element.clear()
            element.send_keys(text)
            return True
        except:
            return False
    
    def _handle_clear_text(self, action: Dict) -> bool:
        """Handle clear text action"""
        element = self._get_element(action)
        if not element:
            return False
        
        try:
            element.clear()
            return True
        except:
            return False
    
    def _handle_select_dropdown(self, action: Dict) -> bool:
        """Handle dropdown selection by value"""
        element = self._get_element(action)
        if not element:
            return False
        
        value = action.get('value', action.get('option_value', ''))
        
        try:
            select = Select(element)
            select.select_by_value(value)
            return True
        except:
            return False
    
    def _handle_select_dropdown_by_text(self, action: Dict) -> bool:
        """Handle dropdown selection by visible text"""
        element = self._get_element(action)
        if not element:
            return False
        
        text = action.get('text', action.get('option_text', ''))
        
        try:
            select = Select(element)
            select.select_by_visible_text(text)
            return True
        except:
            return False
    
    def _handle_click_checkbox(self, action: Dict) -> bool:
        """Handle checkbox click"""
        element = self._get_element(action)
        if not element:
            return False
        
        desired_state = action.get('checked', True)
        
        try:
            current_state = element.is_selected()
            if current_state != desired_state:
                element.click()
            return True
        except:
            return False
    
    def _handle_click_radio(self, action: Dict) -> bool:
        """Handle radio button click"""
        return self._handle_click(action)
    
    def _handle_hover(self, action: Dict) -> bool:
        """Handle hover action"""
        element = self._get_element(action)
        if not element:
            return False
        
        try:
            actions = ActionChains(self.driver)
            actions.move_to_element(element).perform()
            return True
        except:
            return False
    
    def _handle_scroll_to(self, action: Dict) -> bool:
        """Handle scroll to element"""
        element = self._get_element(action)
        if not element:
            return False
        
        try:
            self.driver.execute_script(
                "arguments[0].scrollIntoView({behavior: 'smooth', block: 'center'});",
                element
            )
            time.sleep(0.5)  # Wait for scroll animation
            return True
        except:
            return False
    
    def _handle_wait_for_element(self, action: Dict) -> bool:
        """Handle wait for element presence"""
        element = self._get_element(action)
        return element is not None
    
    def _handle_wait_for_clickable(self, action: Dict) -> bool:
        """Handle wait for element to be clickable"""
        locator = action.get('locator', '')
        locator_type = action.get('locator_type', 'xpath').lower()
        timeout = action.get('timeout', self.default_timeout)
        
        by_type = self._get_by_type(locator_type)
        
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.element_to_be_clickable((by_type, locator))
            )
            return True
        except:
            return False
    
    def _handle_wait_for_visible(self, action: Dict) -> bool:
        """Handle wait for element to be visible"""
        locator = action.get('locator', '')
        locator_type = action.get('locator_type', 'xpath').lower()
        timeout = action.get('timeout', self.default_timeout)
        
        by_type = self._get_by_type(locator_type)
        
        try:
            WebDriverWait(self.driver, timeout).until(
                EC.visibility_of_element_located((by_type, locator))
            )
            return True
        except:
            return False
    
    def _handle_sleep(self, action: Dict) -> bool:
        """Handle sleep/wait action"""
        duration = float(action.get('duration', action.get('value', 1)))
        time.sleep(duration)
        return True
    
    def _handle_press_key(self, action: Dict) -> bool:
        """Handle key press action"""
        element = self._get_element(action)
        if not element:
            return False
        
        key = action.get('key', '').upper()
        
        # Map key names to Keys
        key_mapping = {
            'ENTER': Keys.ENTER,
            'TAB': Keys.TAB,
            'ESCAPE': Keys.ESCAPE,
            'SPACE': Keys.SPACE,
            'BACKSPACE': Keys.BACKSPACE,
            'DELETE': Keys.DELETE,
            'ARROW_DOWN': Keys.ARROW_DOWN,
            'ARROW_UP': Keys.ARROW_UP,
            'ARROW_LEFT': Keys.ARROW_LEFT,
            'ARROW_RIGHT': Keys.ARROW_RIGHT
        }
        
        key_to_press = key_mapping.get(key, key)
        
        try:
            element.send_keys(key_to_press)
            return True
        except:
            return False
    
    def _handle_upload_file(self, action: Dict) -> bool:
        """Handle file upload"""
        element = self._get_element(action)
        if not element:
            return False
        
        file_path = action.get('file_path', '')
        
        try:
            element.send_keys(file_path)
            return True
        except:
            return False
    
    def _handle_switch_to_frame(self, action: Dict) -> bool:
        """Handle switching to iframe"""
        frame_locator = action.get('locator', action.get('frame', 0))
        
        try:
            if isinstance(frame_locator, int):
                self.driver.switch_to.frame(frame_locator)
            else:
                element = self._get_element(action)
                if element:
                    self.driver.switch_to.frame(element)
                else:
                    return False
            return True
        except:
            return False
    
    def _handle_switch_to_default(self, action: Dict) -> bool:
        """Handle switching back to default content"""
        try:
            self.driver.switch_to.default_content()
            return True
        except:
            return False
    
    def _handle_switch_to_parent_frame(self, action: Dict) -> bool:
        """Handle switching to parent frame"""
        try:
            self.driver.switch_to.parent_frame()
            return True
        except:
            return False
    
    def _handle_access_shadow_root(self, action: Dict) -> bool:
        """Handle accessing shadow DOM"""
        host_xpath = action.get('host_xpath', action.get('locator', ''))
        
        if not host_xpath:
            print("No shadow host xpath provided")
            return False
        
        try:
            # Get the shadow host element
            host_element = self.driver.find_element(By.XPATH, host_xpath)
            
            # Access shadow root via JavaScript
            script = "return arguments[0].shadowRoot"
            shadow_root = self.driver.execute_script(script, host_element)
            
            if shadow_root:
                # Store reference for later use (shadow roots can't be switched to like iframes)
                # Elements inside shadow DOM need to be accessed via execute_script
                return True
            else:
                print(f"No shadow root found on element: {host_xpath}")
                return False
                
        except Exception as e:
            print(f"Error accessing shadow DOM: {str(e)}")
            return False
    
    def _handle_execute_script(self, action: Dict) -> bool:
        """Handle JavaScript execution"""
        script = action.get('script', '')
        
        try:
            self.driver.execute_script(script)
            return True
        except:
            return False
    
    def execute_field_action(self, field_config: Dict) -> bool:
        """
        Execute action for a field from the JSON config
        
        Args:
            field_config: Field configuration dictionary from gui_fields
            
        Returns:
            True if successful
        """
        create_action = field_config.get('create_action', {})
        create_type = create_action.get('create_type', '')
        
        # Handle sleep before action
        sleep_before = create_action.get('webdriver_sleep_before_action', '')
        if sleep_before and sleep_before != 'None':
            try:
                time.sleep(float(sleep_before))
            except:
                pass
        
        # Build action from create_action
        locator = create_action.get('update_css', '')
        
        if not locator:
            print(f"Warning: No locator for field: {field_config.get('name', 'unknown')}")
            return False
        
        # Map create_type to action
        if create_type == 'enter_text':
            value = field_config.get('update_fields_assignment', {}).get('value', '')
            actions = [{
                'action': 'enter_text',
                'locator': locator,
                'locator_type': 'css',
                'text': value
            }]
        elif create_type == 'select_dropdown':
            value = field_config.get('update_fields_assignment', {}).get('value', '')
            actions = [{
                'action': 'select_dropdown',
                'locator': locator,
                'locator_type': 'css',
                'value': value
            }]
        elif create_type == 'click_button' or create_type == 'click_checkbox':
            actions = [{
                'action': 'click',
                'locator': locator,
                'locator_type': 'css'
            }]
        elif create_type == 'sleep':
            duration = create_action.get('value', '1')
            actions = [{
                'action': 'sleep',
                'duration': float(duration)
            }]
        else:
            print(f"Warning: Unknown create_type: {create_type}")
            return False
        
        return self.execute_actions(actions)


def test_executor():
    """Test the Selenium executor"""
    from selenium import webdriver
    
    driver = webdriver.Chrome()
    driver.get("https://www.example.com")
    
    executor = SeleniumExecutor(driver)
    
    # Test action sequence
    actions = [
        {
            'action': 'wait_for_element',
            'locator': '//input[@name="q"]',
            'locator_type': 'xpath',
            'timeout': 10
        },
        {
            'action': 'enter_text',
            'locator': '//input[@name="q"]',
            'locator_type': 'xpath',
            'text': 'selenium testing'
        },
        {
            'action': 'sleep',
            'duration': 2
        }
    ]
    
    success = executor.execute_actions(actions)
    print(f"Actions executed: {'✓' if success else '✗'}")
    
    driver.quit()


if __name__ == "__main__":
    test_executor()
