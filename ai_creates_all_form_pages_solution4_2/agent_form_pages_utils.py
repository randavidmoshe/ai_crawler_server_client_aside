# form_utils.py
# Shared constants, helpers, and utilities
# Version 3 - Complete

import os
import re
import json
import time
import random
import platform
from typing import List, Dict, Any, Optional, Tuple
from pathlib import Path

from bs4 import BeautifulSoup
from selenium.webdriver.common.by import By
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.support.ui import WebDriverWait, Select
from selenium.common.exceptions import StaleElementReferenceException

# ------------------------------------------------------------
# Output locations
# ------------------------------------------------------------

# ------------------------------------------------------------
# Heuristics and limits
# ------------------------------------------------------------
NEXT_BUTTON_KEYWORDS = [
    "next", "continue", "proceed", "next step", "go on", "step", "forward", "advance"
]
SAVE_BUTTON_KEYWORDS = [
    "save", "finish", "submit", "done", "complete", "create", "confirm"
]
EDIT_BUTTON_KEYWORDS = [
    "edit", "update", "modify", "change", "revise"
]
FORM_NAME_HINTS = [
    "name", "title", "advertisement", "finding", "campaign", "record", "project"
]
ERROR_SELECTORS = [
    ".error",
    ".error-message",
    ".invalid-feedback",
    ".validation-error",
    ".help-block.error",
    ".text-danger",
    ".is-invalid + .invalid-feedback",
    "[role='alert']",
    "[aria-invalid='true']"
]
POPUP_CLOSE_SELECTORS = [
    ".modal [data-dismiss='modal']",
    ".modal .close",
    ".dialog .close",
    "[aria-label='Close']",
]

MAX_ROUTE_DEPTH = 5
MAX_STEPS_PER_ROUTE = 80
MAX_POPUP_DEPTH = 3

# ------------------------------------------------------------
# Project-specific folder creation
# ------------------------------------------------------------
def get_project_base_dir(project_name: str) -> Path:
    """
    Returns the base directory for the project based on OS.
    Linux/Mac/Windows: ~/automation_product_config/ai_projects/{project_name}/
    """
    # Use Path.home() for all systems - works on Linux, Mac, and Windows
    base = Path.home() / "automation_product_config" / "ai_projects"

    project_dir = base / sanitize_filename(project_name)

    try:
        project_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Project] ✅ Using directory: {project_dir}")
    except PermissionError as e:
        print(f"[ERROR] ❌ Permission denied: {project_dir}")
        print(f"[ERROR] Falling back to current working directory")
        # Fallback to project directory
        project_dir = Path.cwd() / "output" / sanitize_filename(project_name)
        project_dir.mkdir(parents=True, exist_ok=True)
        print(f"[Project] ✅ Fallback directory: {project_dir}")

    return project_dir

def create_form_page_folder(project_name: str, form_page_name: str) -> Path:
    """
    Creates and returns the folder path for a specific form page.
    Path: {base}/ai_projects/{project_name}/{form_page_name}/
    """
    project_base = get_project_base_dir(project_name)
    form_folder = project_base / sanitize_filename(form_page_name)
    form_folder.mkdir(parents=True, exist_ok=True)
    
    # Create subdirectories for different output types
    (form_folder / "routes").mkdir(exist_ok=True)
    (form_folder / "verification").mkdir(exist_ok=True)
    (form_folder / "navigation").mkdir(exist_ok=True)
    (form_folder / "updates").mkdir(exist_ok=True)
    (form_folder / "screenshots").mkdir(exist_ok=True)
    
    return form_folder

# ------------------------------------------------------------
# Utilities
# ------------------------------------------------------------
def wait_dom_ready(driver, timeout=8):
    try:
        WebDriverWait(driver, timeout).until(
            lambda d: d.execute_script("return document.readyState") == "complete"
        )
    except Exception as e:
        # Timeout or other error - continue anyway
        print(f"[wait_dom_ready] ⚠️ Timeout or error: {e}")
        pass

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
    try:
        return (el.text or "").strip()
    except Exception:
        return ""

def page_has_form_fields_html(html: str) -> bool:
    soup = BeautifulSoup(html, "lxml")
    return bool(soup.select("input, select, textarea"))


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

            // Get ancestors up to 10 levels for button
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

            // Check if any input shares an ancestor with button
            for (var i = 0; i < inputs.length; i++) {
                var inputAncestors = getAncestors(inputs[i], 10);

                // Check for common ancestor
                for (var j = 0; j < buttonAncestors.length; j++) {
                    for (var k = 0; k < inputAncestors.length; k++) {
                        if (buttonAncestors[j] === inputAncestors[k]) {
                            return true;  // Found common ancestor
                        }
                    }
                }
            }

            return false;
        """, button, visible_inputs)

        return result

    except Exception as e:
        print(f"[Form Check]     ⚠️ Container check failed: {e}, assuming True")
        return True  # Default to True if check fails

def sanitize_filename(name: str) -> str:
    name = name.replace(" ", "_")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name.strip()) or "form_page"

def all_inputs_on_page(driver):
    inputs = []
    for css in ("input", "select", "textarea"):
        inputs.extend(driver.find_elements(By.CSS_SELECTOR, css))
    return inputs

def element_selector_hint(el) -> str:
    try:
        _id = el.get_attribute("id")
        if _id:
            return f"#{_id}"
        name = el.get_attribute("name")
        if name:
            return f"[name='{name}']"
        role = el.get_attribute("role")
        if role:
            return f"[role='{role}']:{visible_text(el)[:30]}"
        cls = el.get_attribute("class") or ""
        cls = "." + ".".join([c for c in cls.split() if c]) if cls else ""
        tag = el.tag_name.lower()
        if cls:
            return f"{tag}{cls}"
        return f"{tag}:{visible_text(el)[:30]}"
    except Exception:
        return "element"

def select_by_visible_text_if_native(el, value: str) -> bool:
    try:
        Select(el).select_by_visible_text(value)
        return True
    except Exception:
        return False

def find_clickables_by_keywords(driver, keywords:List[str]) -> List:
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

def rand_name():
    first = ["Alice","Bob","Carol","David","Emma","Frank","Grace","Hannah","Ilan","Julia"]
    last = ["Cohen","Levi","Katz","Miller","Smith","Johnson","Brown"]
    return random.choice(first), random.choice(last)

def suggest_value_for_type(field_type: str, label: str = "", name: str = "") -> str:
    l = (label or "").lower() + " " + (name or "").lower()
    if "email" in l or field_type == "email":
        f, ln = rand_name()
        return f"{f}.{ln}{random.randint(10,9999)}@example.com".lower()
    if "phone" in l or field_type in ("tel", "phone"):
        return str(random.randint(2000000000, 9999999999))
    if "number" in l or field_type == "number":
        return str(random.randint(1000, 99999))
    if "first" in l or "fname" in l:
        return rand_name()[0]
    if "last" in l or "lname" in l or "surname" in l:
        return rand_name()[1]
    if field_type in ("date", "datetime-local", "month", "time"):
        return "2025-01-01"
    if "city" in l:
        return "Springfield"
    if "address" in l:
        return "123 Main St"
    return "TestValue"

# ------------------------------------------------------------
# Obstacle Handling Utilities
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