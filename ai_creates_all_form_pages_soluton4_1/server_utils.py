# server_utils.py
# Server-side utilities - Functions that don't need Selenium driver
# Extracted from form_utils.py

import os
import re
import random
from typing import List
from pathlib import Path
from bs4 import BeautifulSoup

# ------------------------------------------------------------
# Output locations
# ------------------------------------------------------------
OUT_DIR_FORMS = "../forms_json"
OUT_DIR_ROUTES = "../form_routes"
OUT_DIR_VERIF = "../form_verifications"
OUT_DIR_NAV = "../form_navigation"
OUT_DIR_UPDATES = "../form_updates"
OUT_DIR_HIER = "../form_hierarchy"
OUT_MASTER_PAGES = "form_pages.json"

for d in [OUT_DIR_FORMS, OUT_DIR_ROUTES, OUT_DIR_VERIF, OUT_DIR_NAV, OUT_DIR_UPDATES, OUT_DIR_HIER]:
    os.makedirs(d, exist_ok=True)

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
# Project-specific folder creation (Server-side only)
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
# Utilities (No Selenium needed)
# ------------------------------------------------------------

def sanitize_filename(name: str) -> str:
    name = name.replace(" ", "_")
    return re.sub(r"[^a-zA-Z0-9._-]", "_", name.strip()) or "form_page"


def page_has_form_fields_html(html: str) -> bool:
    """Check if HTML string has form fields (no driver needed)"""
    soup = BeautifulSoup(html, "lxml")
    return bool(soup.select("input, select, textarea"))


def element_selector_hint(el) -> str:
    """Generate selector hint from Selenium element"""
    try:
        _id = el.get_attribute("id")
        if _id:
            return f"#{_id}"
        name = el.get_attribute("name")
        if name:
            return f"[name='{name}']"
        role = el.get_attribute("role")
        if role:
            # Use visible_text from agent_utils
            from agent_utils import visible_text
            return f"[role='{role}']:{visible_text(el)[:30]}"
        cls = el.get_attribute("class") or ""
        cls = "." + ".".join([c for c in cls.split() if c]) if cls else ""
        tag = el.tag_name.lower()
        if cls:
            return f"{tag}{cls}"
        from agent_utils import visible_text
        return f"{tag}:{visible_text(el)[:30]}"
    except Exception:
        return "element"


def select_by_visible_text_if_native(el, value: str) -> bool:
    """Select by visible text in native select element"""
    try:
        from selenium.webdriver.support.ui import Select
        Select(el).select_by_visible_text(value)
        return True
    except Exception:
        return False


def rand_name():
    """Generate random name"""
    first = ["Alice", "Bob", "Carol", "David", "Emma", "Frank", "Grace", "Hannah", "Ilan", "Julia"]
    last = ["Cohen", "Levi", "Katz", "Miller", "Smith", "Johnson", "Brown"]
    return random.choice(first), random.choice(last)


def suggest_value_for_type(field_type: str, label: str = "", name: str = "") -> str:
    """Suggest test value for field type"""
    l = (label or "").lower() + " " + (name or "").lower()
    if "email" in l or field_type == "email":
        f, ln = rand_name()
        return f"{f}.{ln}{random.randint(10, 9999)}@example.com".lower()
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
