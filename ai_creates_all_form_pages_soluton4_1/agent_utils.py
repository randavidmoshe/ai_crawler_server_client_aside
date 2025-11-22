# agent_utils.py
# Agent-side utilities - Functions that use Selenium driver
# Extracted from form_utils.py

import time
from typing import List
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait
from selenium.common.exceptions import StaleElementReferenceException

# Import constants from server_utils
from server_utils import ERROR_SELECTORS


# ------------------------------------------------------------
# Selenium utilities (need driver)
# ------------------------------------------------------------

def wait_dom_ready(driver, timeout=8):
    WebDriverWait(driver, timeout).until(
        lambda d: d.execute_script("return document.readyState") == "complete"
    )


def scroll_into_view(driver, el):
    driver.execute_script("arguments[0].scrollIntoView({block:'center'})", el)


def safe_click(driver, el) -> bool:
    try:
        scroll_into_view(driver, el)
        ActionChains(driver).move_to_element(el).pause(0.05).click().perform()
        return True
    except Exception:
        try:
            el.click()
            return True
        except Exception:
            try:
                # Third attempt: JavaScript click
                driver.execute_script("arguments[0].click();", el)
                return True
            except Exception:
                return False


def visible_text(el) -> str:
    """Get visible text from element - no driver needed but used with Selenium elements"""
    try:
        return (el.text or "").strip()
    except Exception:
        return ""


def page_has_form_fields(driver, ai_classifier=None) -> bool:
    """Check if page has form fields AND submission button in the same container"""
    try:
        # Check for form fields
        input_fields = driver.find_elements(By.CSS_SELECTOR,
                                            "input:not([type='hidden']), textarea, select")
        visible_inputs = [f for f in input_fields if f.is_displayed()]

        print(f"[Form Check] Found {len(visible_inputs)} visible input fields")

        if len(visible_inputs) < 1:
            print(f"[Form Check] ❌ No input fields found")
            return False

        # Find buttons
        button_blacklist = ['search', 'filter', 'find', 'reset', 'clear', 'back', 'cancel', 'close']
        buttons = driver.find_elements(By.CSS_SELECTOR,
                                       "button, input[type='submit'], input[type='button']")

        print(f"[Form Check] Found {len(buttons)} buttons total")

        checked_count = 0
        for button in buttons:
            if not button.is_displayed():
                continue

            text = (button.text or button.get_attribute('value') or '').strip()
            if not text:
                continue

            print(f"[Form Check]   Checking button: '{text}'")
            checked_count += 1

            # Check blacklist
            if any(blacklisted in text.lower() for blacklisted in button_blacklist):
                print(f"[Form Check]     ❌ Blacklisted")
                continue

            # Use AI if provided
            if ai_classifier:
                print(f"[Form Check]     → Calling AI classifier...")
                if ai_classifier(text):
                    # ✅ AI says this is a submission button - now check if it shares container with inputs
                    if _button_shares_container_with_inputs(driver, button, visible_inputs):
                        print(f"[Form Check]     ✅ AI says YES + shares container with inputs!")
                        return True
                    else:
                        print(f"[Form Check]     ❌ AI says YES but NOT in same container as inputs")
                else:
                    print(f"[Form Check]     ❌ AI says NO")
            else:
                print(f"[Form Check]     ⚠️ No AI classifier provided!")

        print(f"[Form Check] Checked {checked_count} buttons, none were submission buttons in same container")
        return False

    except Exception as e:
        print(f"[Form Check] ❌ Exception: {e}")
        return False


def _button_shares_container_with_inputs(driver, button, visible_inputs) -> bool:
    """Check if button is in the same parent container as input fields"""
    try:
        # Use JavaScript to check if button and inputs share a common ancestor within 10 levels
        result = driver.execute_script("""
            var button = arguments[0];
            var inputs = arguments[1];

            // Helper function to get ancestors up to N levels
            function getAncestors(element, levels) {
                var ancestors = [element];
                var current = element;
                for (var i = 0; i < levels && current.parentElement; i++) {
                    current = current.parentElement;
                    ancestors.push(current);
                }
                return ancestors;
            }

            // Get ancestors of button
            var buttonAncestors = getAncestors(button, 10);

            // Check if any input shares an ancestor with button
            for (var i = 0; i < inputs.length; i++) {
                var inputAncestors = getAncestors(inputs[i], 10);

                // Find common ancestors
                for (var j = 0; j < buttonAncestors.length; j++) {
                    for (var k = 0; k < inputAncestors.length; k++) {
                        if (buttonAncestors[j] === inputAncestors[k]) {
                            // Check if the common ancestor is close enough (not body/html)
                            var tagName = buttonAncestors[j].tagName.toLowerCase();
                            if (tagName !== 'body' && tagName !== 'html') {
                                return true;
                            }
                        }
                    }
                }
            }

            return false;
        """, button, visible_inputs)

        return result

    except Exception as e:
        print(f"[Form Check] ❌ Error checking container: {e}")
        # Fallback: assume they're in same container if we can't determine
        return True


def all_inputs_on_page(driver):
    inputs = []
    for css in ["input", "textarea", "select"]:
        inputs.extend(driver.find_elements(By.CSS_SELECTOR, css))
    return inputs


def find_clickables_by_keywords(driver, keywords: List[str]) -> List:
    els = driver.find_elements(By.XPATH, "//*")
    matches = []
    seen = set()
    for el in els:
        try:
            if not el.is_displayed():
                continue
            tag = el.tag_name.lower()
            if tag in ("script", "style", "meta", "link"):
                continue
            txt = visible_text(el).lower()
            if not txt or len(txt) > 100:
                continue
            if any(k in txt for k in keywords):
                key = (tag, txt, el.location.get("y", 0), el.location.get("x", 0))
                if key not in seen:
                    matches.append(el)
                    seen.add(key)
        except StaleElementReferenceException:
            continue
    matches.sort(key=lambda e: e.location.get("y", 0))
    return matches


# ------------------------------------------------------------
# Obstacle Handling Utilities (Selenium)
# ------------------------------------------------------------

def handle_iframe_switch(driver, iframe_selector: str) -> bool:
    """Switch to iframe by selector"""
    try:
        iframe = driver.find_element(By.CSS_SELECTOR, iframe_selector)
        driver.switch_to.frame(iframe)
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f"[Obstacle] Failed to switch to iframe {iframe_selector}: {e}")
        return False


def handle_shadow_root_access(driver, host_selector: str):
    """Access shadow root and return shadow root element"""
    try:
        host = driver.find_element(By.CSS_SELECTOR, host_selector)
        shadow_root = driver.execute_script("return arguments[0].shadowRoot", host)
        return shadow_root
    except Exception as e:
        print(f"[Obstacle] Failed to access shadow root {host_selector}: {e}")
        return None


def handle_hover(driver, element) -> bool:
    """Hover over element"""
    try:
        ActionChains(driver).move_to_element(element).perform()
        time.sleep(0.3)
        return True
    except Exception as e:
        print(f"[Obstacle] Failed to hover: {e}")
        return False


def handle_scroll(driver, direction: str = "down", amount: int = 500) -> bool:
    """Scroll page"""
    try:
        if direction == "down":
            driver.execute_script(f"window.scrollBy(0, {amount})")
        elif direction == "up":
            driver.execute_script(f"window.scrollBy(0, -{amount})")
        time.sleep(0.5)
        return True
    except Exception as e:
        print(f"[Obstacle] Failed to scroll: {e}")
        return False


def handle_overlay_dismiss(driver, overlay_selector: str) -> bool:
    """Dismiss overlay/modal"""
    try:
        overlay = driver.find_element(By.CSS_SELECTOR, overlay_selector)
        if overlay.is_displayed():
            close_btn = overlay.find_element(By.CSS_SELECTOR, ".close, [aria-label='Close'], button")
            safe_click(driver, close_btn)
            time.sleep(0.3)
            return True
    except Exception as e:
        print(f"[Obstacle] Failed to dismiss overlay: {e}")
        return False


# ------------------------------------------------------------
# Screenshot hook
# ------------------------------------------------------------

def call_user_screenshot(driver, note: str):
    try:
        print_screen(driver, note)  # type: ignore  # noqa: F821
    except Exception:
        ts = int(time.time())
        path = f"screenshot_error_{ts}.png"
        try:
            driver.save_screenshot(path)
            print(f"Saved local screenshot {path}  note: {note}")
        except Exception:
            print("Could not take local screenshot")


# ------------------------------------------------------------
# Error detection
# ------------------------------------------------------------

def collect_error_messages(driver) -> List[str]:
    msgs = []
    for sel in ERROR_SELECTORS:
        try:
            for el in driver.find_elements(By.CSS_SELECTOR, sel):
                if el.is_displayed():
                    t = visible_text(el)
                    if t:
                        msgs.append(t)
        except Exception:
            continue
    return list(dict.fromkeys(msgs))


def dismiss_all_popups_and_overlays(driver):
    """Dismiss ALL popups: cookies, modals, overlays, chat widgets"""
    dismissed = False

    # Strategy 1: Cookie consent buttons
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
                elements = driver.find_elements(By.XPATH, sel)
            else:
                elements = driver.find_elements(By.CSS_SELECTOR, sel)

            for el in elements:
                if el.is_displayed():
                    safe_click(driver, el)
                    time.sleep(0.3)
                    dismissed = True
                    print(f"[Popup] ✓ Dismissed: {sel[:50]}")
                    break
        except:
            pass

    # Strategy 2: Close buttons on modals
    close_selectors = [
        ".modal.show .close", ".modal.show [data-dismiss='modal']",
        ".dialog[open] .close", "[role='dialog'] button[aria-label='Close']",
        ".ant-modal-close", ".MuiDialog-root button[aria-label='close']"
    ]

    for sel in close_selectors:
        try:
            elements = driver.find_elements(By.CSS_SELECTOR, sel)
            for el in elements:
                if el.is_displayed():
                    safe_click(driver, el)
                    time.sleep(0.3)
                    dismissed = True
                    print(f"[Popup] ✓ Closed modal")
                    break
        except:
            pass

    # Strategy 3: Overlay dismissal (click backdrop)
    try:
        overlays = driver.find_elements(By.CSS_SELECTOR, ".modal-backdrop, .overlay, [class*='backdrop']")
        for overlay in overlays:
            if overlay.is_displayed():
                safe_click(driver, overlay)
                time.sleep(0.3)
                dismissed = True
                print(f"[Popup] ✓ Clicked overlay backdrop")
                break
    except:
        pass

    # Strategy 4: ESC key (close any modal)
    try:
        from selenium.webdriver.common.keys import Keys
        driver.find_element(By.TAG_NAME, 'body').send_keys(Keys.ESCAPE)
        time.sleep(0.2)
    except:
        pass

    if not dismissed:
        print("[Popup] ✓ No popups detected")

    return dismissed
