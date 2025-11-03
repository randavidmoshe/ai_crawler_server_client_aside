# form_routes_explorer.py (Part 1 of 2)
# Version 3 - COMPLETE with ALL features
# Enhanced with: route consolidation, AND/OR detection, grid columns, edit/verify capture

import os
import json
import time
import random
from typing import List, Dict, Any, Optional, Tuple, Set
from dataclasses import dataclass, asdict, field

from selenium.webdriver.common.by import By
from selenium.common.exceptions import StaleElementReferenceException

from form_utils import (
    OUT_DIR_FORMS, OUT_DIR_ROUTES, OUT_DIR_VERIF, OUT_DIR_NAV, OUT_DIR_UPDATES,
    NEXT_BUTTON_KEYWORDS, SAVE_BUTTON_KEYWORDS, EDIT_BUTTON_KEYWORDS,
    POPUP_CLOSE_SELECTORS, FORM_NAME_HINTS,
    wait_dom_ready, safe_click, visible_text, sanitize_filename, all_inputs_on_page,
    element_selector_hint, select_by_visible_text_if_native, find_clickables_by_keywords,
    suggest_value_for_type, collect_error_messages, call_user_screenshot,
    create_form_page_folder,
    handle_iframe_switch, handle_shadow_root_access, handle_hover, 
    handle_scroll, handle_overlay_dismiss,
)

@dataclass
class FieldStage:
    field_id: str
    label: Optional[str]
    locator_hint: str
    field_type: str
    suggested_value: Optional[str]
    preconditions: List[Dict[str, Any]] = field(default_factory=list)
    actions: List[Dict[str, Any]] = field(default_factory=list)

@dataclass
class InteractionStage:
    label: str
    locator_hint: str
    actions: List[Dict[str, Any]]
    unlocks: List[str] = field(default_factory=list)
    preconditions: List[Dict[str, Any]] = field(default_factory=list)

class FormRoutesExplorer:
    """
    Complete FormRoutesExplorer Ver 3 with ALL features:
    - Route consolidation and dependency detection
    - Smart AND/OR hiding conditions
    - Grid column verification (3-stage flow)
    - Edit & Verify capture after each route
    - Extended actions as dicts
    - All CSS fields left empty
    """

    def __init__(self, driver, form_name: str, start_url: str, base_url: str, project_name: str = "default_project", ai_helper=None):
        self.driver = driver
        self.form_name = form_name
        self.start_url = start_url
        self.base_url = base_url  # NEW: For navigation back
        self.form_slug = sanitize_filename(form_name)
        self.project_name = project_name
        self.ai_helper = ai_helper

        # Create form-specific folder
        self.form_folder = create_form_page_folder(project_name, form_name)

        # Consolidated JSON files
        self.main_setup_json_path = str(self.form_folder / f"{self.form_slug}_main_setup.json")
        self.setup_json_path = str(self.form_folder / f"{self.form_slug}_setup.json")

        # Stores for building JSONs
        self.gui_pre_create_actions: List[Dict[str, Any]] = []
        self.gui_pre_update_actions: List[Dict[str, Any]] = []
        self.gui_pre_verification_actions: List[Dict[str, Any]] = []
        self.gui_fields: List[Dict[str, Any]] = []
        
        # Route tracking for consolidation
        self.all_routes: List[Dict[str, Any]] = []
        self.field_appearances: Dict[str, List[Dict[str, Any]]] = {}
        
        # NEW: Track edit and verify selectors captured after each route
        self.edit_selectors: Dict[str, str] = {}  # field_id -> edit selector
        self.verify_selectors: Dict[str, str] = {}  # field_id -> verify selector
        
        # Old stores for compatibility
        self.verification_store: Dict[str, Dict[str, Any]] = {}
        self.navigation_store: Dict[str, Any] = {}
        self.routes_bundle: List[Dict[str, Any]] = []

        print(f"[FormRoutesExplorer] Created folder: {self.form_folder}")
        if self.ai_helper:
            print(f"[FormRoutesExplorer] AI-powered with obstacle handling enabled")

    def _load_existing_json(self, path: str, default):
        if os.path.exists(path):
            try:
                return json.load(open(path, "r", encoding="utf-8"))
            except Exception:
                return default
        return default

    # ========== Helper methods ==========
    def _label_for(self, el) -> Optional[str]:
        try:
            _id = el.get_attribute("id")
            if _id:
                label_el = self.driver.find_elements(By.CSS_SELECTOR, f"label[for='{_id}']")
                if label_el:
                    return visible_text(label_el[0])
        except Exception:
            return None
        try:
            parent = el.find_element(By.XPATH, "./ancestor-or-self::*[1]")
            sibs = parent.find_elements(By.XPATH, ".//preceding::label | .//following::label")
            for s in sibs[:5]:
                t = visible_text(s)
                if t:
                    return t
        except Exception:
            pass
        return None

    def _find_name_field(self) -> Optional[Any]:
        for el in self.driver.find_elements(By.CSS_SELECTOR, "input[type='text'], input:not([type]), textarea"):
            try:
                if not el.is_displayed():
                    continue
                lab = (self._label_for(el) or "").lower()
                plc = (el.get_attribute("placeholder") or "").lower()
                nm  = (el.get_attribute("name") or "").lower()
                hay = " ".join([lab, plc, nm])
                if any(h in hay for h in FORM_NAME_HINTS):
                    return el
            except Exception:
                continue
        return None

    def _post_action_check_and_fix(self, route_note: str) -> bool:
        errs = collect_error_messages(self.driver)
        if not errs:
            return True
        fixed = self._try_fix_errors(errs)
        if fixed:
            return True
        call_user_screenshot(self.driver, f"{route_note} error after action: {' | '.join(errs)[:200]}")
        return False

    def _try_fix_errors(self, error_messages: List[str]) -> bool:
        fixed_something = False
        inputs = all_inputs_on_page(self.driver)
        for msg in error_messages:
            target = None
            for el in inputs:
                try:
                    if not el.is_displayed():
                        continue
                    lab = self._label_for(el) or ""
                    nm = el.get_attribute("name") or ""
                    if lab and lab.lower() in msg.lower():
                        target = el; break
                    if nm and nm.lower() in msg.lower():
                        target = el; break
                except Exception:
                    continue
            if target is None:
                for el in inputs:
                    try:
                        if not el.is_displayed():
                            continue
                        req = el.get_attribute("required")
                        val = el.get_attribute("value") or ""
                        if req and not val:
                            target = el; break
                    except Exception:
                        continue

            if target is not None:
                ftype = target.get_attribute("type") or target.tag_name
                suggested = suggest_value_for_type(ftype, self._label_for(target) or "", target.get_attribute("name") or "")
                try:
                    safe_click(self.driver, target)
                    try: target.clear()
                    except Exception: pass
                    target.send_keys(suggested)
                    fixed_something = True
                except Exception:
                    continue

        return fixed_something

    def _click_next_if_available(self, route_note: str) -> bool:
        btns = find_clickables_by_keywords(self.driver, NEXT_BUTTON_KEYWORDS)
        for b in reversed(btns):
            try:
                if not b.is_displayed():
                    continue
                if safe_click(self.driver, b):
                    time.sleep(0.3)
                    if not self._post_action_check_and_fix(route_note):
                        return False
                    wait_dom_ready(self.driver)
                    return True
            except Exception:
                continue
        return False

    def _save_if_available(self, route_note: str) -> Tuple[bool, List[str]]:
        btns = find_clickables_by_keywords(self.driver, SAVE_BUTTON_KEYWORDS)
        for b in reversed(btns):
            try:
                if not b.is_displayed():
                    continue
                if safe_click(self.driver, b):
                    time.sleep(0.5)
                    ok = self._post_action_check_and_fix(route_note)
                    errs = [] if ok else collect_error_messages(self.driver)
                    wait_dom_ready(self.driver)
                    return ok, errs
            except Exception:
                continue
        return False, []

    def _handle_popups_if_any(self, route_note: str):
        try:
            modals = self.driver.find_elements(By.CSS_SELECTOR, ".modal.show, .dialog[open], .ant-modal, .mat-dialog-container")
            for m in modals:
                if not m.is_displayed():
                    continue
                for sel in POPUP_CLOSE_SELECTORS:
                    try:
                        close_el = m.find_element(By.CSS_SELECTOR, sel)
                        if close_el and close_el.is_displayed():
                            if safe_click(self.driver, close_el):
                                time.sleep(0.2)
                                self._post_action_check_and_fix(route_note)
                                break
                    except Exception:
                        continue
        except Exception:
            pass

        if len(self.driver.window_handles) > 1:
            base = self.driver.current_window_handle
            for h in self.driver.window_handles:
                if h != base:
                    try:
                        self.driver.switch_to.window(h)
                        self.driver.close()
                    except Exception:
                        pass
            try:
                self.driver.switch_to.window(base)
            except Exception:
                pass

    # ========== Main route exploration ==========
    def explore_and_save_all_routes(self):
        """Explore all routes, capture edit/verify after each, then consolidate"""
        visited = set()
        stack = [([], self.driver.current_url)]

        name_field_selector_hint = None
        nf = self._find_name_field()
        if nf is not None:
            name_field_selector_hint = element_selector_hint(nf)

        route_index = 0

        # Explore all routes
        while stack:
            stages_so_far, url_snap = stack.pop()
            self.driver.get(url_snap)
            wait_dom_ready(self.driver)

            route_hint_parts = []
            for st in stages_so_far:
                if st.get("field_id") and st.get("suggested_value"):
                    route_hint_parts.append(f"{st['field_id']}={st['suggested_value']}")
            route_hint = "_".join(route_hint_parts)[:80] or "base"

            route_entity_name = f"tested_AI_{self.form_slug}_{route_hint}"
            if name_field_selector_hint:
                el = self._find_by_hint(name_field_selector_hint)
                if el is not None and el.is_displayed():
                    try:
                        safe_click(self.driver, el)
                        try: el.clear()
                        except Exception: pass
                        el.send_keys(route_entity_name)
                        self._post_action_check_and_fix(route_entity_name)
                    except Exception:
                        pass

            new_stages, branch_actions = self._discover_current_step(stages_so_far, route_entity_name)

            for b in branch_actions:
                key = json.dumps([stages_so_far, b], sort_keys=True, default=str)
                if key in visited:
                    continue
                visited.add(key)

                self._perform_branch_action(b, route_entity_name)
                wait_dom_ready(self.driver)
                new_url = self.driver.current_url

                stack.append((stages_so_far + new_stages + [b], new_url))

                self.driver.get(url_snap)
                wait_dom_ready(self.driver)

            progressed = True
            while progressed:
                progressed = self._click_next_if_available(route_entity_name)
                if progressed:
                    n_st, b_act = self._discover_current_step(stages_so_far + new_stages, route_entity_name)
                    new_stages.extend(n_st)
                    for b2 in b_act:
                        key2 = json.dumps([stages_so_far + new_stages, b2], sort_keys=True, default=str)
                        if key2 in visited:
                            continue
                        visited.add(key2)
                        self._perform_branch_action(b2, route_entity_name)
                        wait_dom_ready(self.driver)
                        push_url = self.driver.current_url
                        stack.append((stages_so_far + new_stages + [b2], push_url))
                        self.driver.back()
                        wait_dom_ready(self.driver)

            ok, errs = self._save_if_available(route_entity_name)
            if not ok and errs:
                call_user_screenshot(self.driver, f"{route_entity_name} save failed: {' | '.join(errs)[:200]}")

            # Store this route
            route_record = {
                "route_name": route_entity_name,
                "stages": stages_so_far + new_stages,
                "preconditions": self._precondition_list(stages_so_far)
            }
            self.all_routes.append(route_record)
            
            # Track field appearances
            for st in (stages_so_far + new_stages):
                if "field_id" in st:
                    fid = st["field_id"]
                    if fid not in self.field_appearances:
                        self.field_appearances[fid] = []
                    self.field_appearances[fid].append({
                        "route": route_entity_name,
                        "preconditions": self._precondition_list(stages_so_far),
                        "stage": st
                    })

            # Save individual route
            route_path = str(self.form_folder / "routes" / f"{sanitize_filename(route_entity_name)}_stages.json")
            with open(route_path, "w", encoding="utf-8") as f:
                json.dump(route_record, f, indent=2)

            self.routes_bundle.append(route_record)

            # NEW: Capture edit & verify selectors after this route
            if ok:  # Only if save was successful
                try:
                    print(f"[Capture] Capturing edit & verify selectors for {route_entity_name}")
                    self._capture_edit_and_verify_selectors_after_save(
                        route_entity_name, 
                        stages_so_far + new_stages
                    )
                except Exception as e:
                    print(f"[WARN] Edit/Verify capture failed for {route_entity_name}: {e}")

            # Return to form start URL for next route
            self.driver.get(self.start_url)
            wait_dom_ready(self.driver)
            route_index += 1

        # Consolidate all routes into final JSONs
        print("[FormRoutesExplorer] Consolidating all routes...")
        self._consolidate_routes_and_build_final_json()
        
        # Save final consolidated JSONs
        self._save_main_setup_json()
        self._save_setup_json()
        
        print(f"[FormRoutesExplorer] Exploration complete. Saved {len(self.all_routes)} routes.")

    # ========== TO BE CONTINUED IN PART 2 ==========
    # form_routes_explorer.py (Part 2 of 2)
    # CONTINUATION - Field discovery, capture, consolidation, JSON generation

    # ========== Field discovery with AI and obstacles ==========
    def _discover_current_step(self, stages_so_far: List[Dict[str, Any]], route_note: str):
        """Router: use AI if available, otherwise original logic"""
        if self.ai_helper:
            return self._discover_current_step_ai(stages_so_far, route_note)
        else:
            return self._discover_current_step_original(stages_so_far, route_note)

    def _discover_current_step_ai(self, stages_so_far: List[Dict[str, Any]], route_note: str):
        """AI-powered field discovery with comprehensive obstacle handling"""
        new_stages: List[Dict[str, Any]] = []
        branch_actions: List[Dict[str, Any]] = []

        self._handle_popups_if_any(route_note)

        try:
            print(f"[AI] Analyzing form fields with obstacles...")
            page_html = self.driver.page_source
            page_url = self.driver.current_url

            fields_data = self.ai_helper.analyze_form_fields(page_html, page_url)

            for field_info in fields_data:
                selector = field_info.get("selector", "")
                field_type = field_info.get("field_type", "text")
                label = field_info.get("label", "")
                name = field_info.get("name", "")
                options = field_info.get("options", [])
                obstacles = field_info.get("obstacles", [])

                try:
                    # Handle obstacles BEFORE accessing field
                    obstacle_stages = self._handle_obstacles(obstacles, route_note)
                    new_stages.extend(obstacle_stages)

                    # Find the actual element
                    el = self._find_element_with_obstacles(field_info)
                    if not el or not el.is_displayed():
                        continue

                    fid = el.get_attribute("id") or el.get_attribute(
                        "name") or name or f"field-{random.randint(10, 999999)}"
                    locator = selector

                    # Handle different field types
                    if field_type == "select" and options:
                        chosen = options[0] if options else "first"
                        self._set_select_value(el, chosen, route_note)
                        new_stages.append(self._field_stage(fid, label, locator, field_type, chosen, stages_so_far))

                        for alt in options[1:]:
                            branch_actions.append({
                                "kind": "branch-select",
                                "field_id": fid,
                                "label": label,
                                "locator_hint": locator,
                                "actions": [
                                    {"action": "click", "selector_hint": locator},
                                    {"action": "select_by_text", "selector_hint": locator, "value": alt}
                                ],
                                "note": f"alternative select value {alt}"
                            })

                    elif field_type == "radio":
                        if safe_click(self.driver, el):
                            self._post_action_check_and_fix(route_note)
                            chosen_val = el.get_attribute("value") or visible_text(el) or "selected"
                            new_stages.append(
                                self._field_stage(fid, label, locator, field_type, chosen_val, stages_so_far))

                    elif field_type == "checkbox":
                        checked = el.is_selected()
                        if not checked:
                            if safe_click(self.driver, el):
                                self._post_action_check_and_fix(route_note)
                                checked = True
                        val = "true" if checked else "false"
                        new_stages.append(self._field_stage(fid, label, locator, field_type, val, stages_so_far))

                    else:
                        suggested = self.ai_helper.suggest_field_value(field_info)
                        if safe_click(self.driver, el):
                            try:
                                el.clear()
                            except Exception:
                                pass
                            el.send_keys(suggested)
                            self._post_action_check_and_fix(route_note)
                            new_stages.append(
                                self._field_stage(fid, label, locator, field_type, suggested, stages_so_far))

                    # Check for popups after each field
                    self._handle_popups_if_any(route_note)

                except Exception as e:
                    print(f"[AI] Could not interact with field {selector}: {e}")
                    continue

            print(f"[AI] Processed {len(new_stages)} fields")

        except Exception as e:
            print(f"[AI] Field analysis failed: {e}")
            print("[AI] Falling back to original field discovery")
            return self._discover_current_step_original(stages_so_far, route_note)

        return new_stages, branch_actions

    def _handle_obstacles(self, obstacles: List[Dict[str, Any]], route_note: str) -> List[Dict[str, Any]]:
        """Handle all obstacles before accessing a field, return obstacle stages"""
        obstacle_stages = []

        for obstacle in obstacles:
            obs_type = obstacle.get("type", "")
            solution = obstacle.get("solution", {})
            action = solution.get("action", "")
            selector = solution.get("selector", "")
            details = solution.get("details", "")

            if obs_type == "iframe" and action == "switch_iframe":
                if handle_iframe_switch(self.driver, selector):
                    obstacle_stages.append({
                        "action": "switch_to_iframe",
                        "selector": selector,
                        "description": f"Enter iframe: {selector}"
                    })

            elif obs_type == "shadow_root" and action == "pierce_shadow":
                shadow_root = handle_shadow_root_access(self.driver, selector)
                if shadow_root:
                    obstacle_stages.append({
                        "action": "access_shadow_root",
                        "host_selector": selector,
                        "description": f"Access shadow root: {selector}"
                    })

            elif obs_type == "hover" and action == "hover":
                try:
                    hover_el = self.driver.find_element(By.CSS_SELECTOR, selector)
                    if handle_hover(self.driver, hover_el):
                        obstacle_stages.append({
                            "action": "hover",
                            "selector": selector,
                            "description": f"Hover over: {selector}"
                        })
                except Exception:
                    pass

            elif obs_type == "scroll" and action == "scroll":
                direction = details.get("direction", "down") if isinstance(details, dict) else "down"
                if handle_scroll(self.driver, direction):
                    obstacle_stages.append({
                        "action": "scroll",
                        "direction": direction,
                        "description": f"Scroll {direction}"
                    })

            elif obs_type == "overlay" and action == "dismiss_overlay":
                if handle_overlay_dismiss(self.driver, selector):
                    obstacle_stages.append({
                        "action": "dismiss_overlay",
                        "selector": selector,
                        "description": f"Dismiss overlay: {selector}"
                    })

            elif obs_type == "lazy_load" and action == "wait":
                wait_time = int(details) if details and str(details).isdigit() else 2
                time.sleep(wait_time)
                obstacle_stages.append({
                    "action": "sleep",
                    "duration": wait_time,
                    "description": f"Wait for lazy load: {wait_time}s"
                })

        return obstacle_stages

    def _find_element_with_obstacles(self, field_info: Dict[str, Any]):
        """Find element considering iframe/shadow DOM context"""
        selector = field_info.get("selector", "")
        in_iframe = field_info.get("in_iframe", False)
        iframe_selector = field_info.get("iframe_selector", "")
        in_shadow = field_info.get("in_shadow_root", False)
        shadow_host = field_info.get("shadow_host_selector", "")

        try:
            if in_shadow and shadow_host:
                shadow_root = handle_shadow_root_access(self.driver, shadow_host)
                if shadow_root:
                    return shadow_root.find_element(By.CSS_SELECTOR, selector)

            return self.driver.find_element(By.CSS_SELECTOR, selector)
        except Exception:
            return None

    def _discover_current_step_original(self, stages_so_far: List[Dict[str, Any]], route_note: str):
        """Original field discovery (fallback)"""
        new_stages: List[Dict[str, Any]] = []
        branch_actions: List[Dict[str, Any]] = []

        self._handle_popups_if_any(route_note)

        for el in all_inputs_on_page(self.driver):
            try:
                if not el.is_displayed():
                    continue
                tag = el.tag_name.lower()
                ftype = el.get_attribute("type") or tag
                fid = el.get_attribute("id") or el.get_attribute("name") or f"{tag}-{random.randint(10, 999999)}"
                label = self._label_for(el)
                locator = element_selector_hint(el)

                if tag == "select":
                    options = [o.text.strip() for o in el.find_elements(By.TAG_NAME, "option") if o.text.strip()]
                    if options:
                        chosen = options[0]
                        self._set_select_value(el, chosen, route_note)
                        new_stages.append(self._field_stage(fid, label, locator, ftype, chosen, stages_so_far))

                        for alt in options[1:]:
                            branch_actions.append({
                                "kind": "branch-select",
                                "field_id": fid,
                                "label": label,
                                "locator_hint": locator,
                                "actions": [
                                    {"action": "click", "selector_hint": locator},
                                    {"action": "select_by_text", "selector_hint": locator, "value": alt}
                                ],
                                "note": f"alternative select value {alt}"
                            })
                        continue

                if ftype == "radio":
                    name = el.get_attribute("name") or fid
                    radios = self.driver.find_elements(By.CSS_SELECTOR, f"input[type='radio'][name='{name}']")
                    chosen_val = None
                    chosen_loc = None
                    for r in radios:
                        try:
                            if not r.is_displayed():
                                continue
                            if safe_click(self.driver, r):
                                self._post_action_check_and_fix(route_note)
                                chosen_val = r.get_attribute("value") or visible_text(r)
                                chosen_loc = element_selector_hint(r)
                                break
                        except Exception:
                            continue
                    if chosen_val:
                        new_stages.append(
                            self._field_stage(name, label, chosen_loc or locator, "radio", chosen_val, stages_so_far))
                    for r in radios:
                        try:
                            if not r.is_displayed():
                                continue
                            alt_val = r.get_attribute("value") or visible_text(r)
                            loc_r = element_selector_hint(r)
                            if alt_val != chosen_val:
                                branch_actions.append({
                                    "kind": "branch-radio",
                                    "field_id": name,
                                    "label": label,
                                    "locator_hint": loc_r,
                                    "actions": [{"action": "click", "selector_hint": loc_r}],
                                    "note": f"alternative radio {alt_val}"
                                })
                        except Exception:
                            continue
                    continue

                if ftype == "checkbox":
                    checked = el.is_selected()
                    if not checked:
                        if safe_click(self.driver, el):
                            self._post_action_check_and_fix(route_note)
                            checked = True
                    val = "true" if checked else "false"
                    new_stages.append(self._field_stage(fid, label, locator, "checkbox", val, stages_so_far))
                    branch_actions.append({
                        "kind": "branch-checkbox-toggle",
                        "field_id": fid,
                        "label": label,
                        "locator_hint": locator,
                        "actions": [{"action": "click", "selector_hint": locator}],
                        "note": "checkbox opposite state"
                    })
                    continue

                if tag in ("input", "textarea"):
                    suggested = suggest_value_for_type(ftype, label, fid)
                    if safe_click(self.driver, el):
                        try:
                            el.clear()
                        except Exception:
                            pass
                        el.send_keys(suggested)
                        self._post_action_check_and_fix(route_note)
                        new_stages.append(self._field_stage(fid, label, locator, ftype, suggested, stages_so_far))
                        continue

            except StaleElementReferenceException:
                continue
            except Exception:
                continue

        return new_stages, branch_actions

    # ========== NEW: Edit & Verify Selector Capture ==========
    def _capture_edit_and_verify_selectors_after_save(self, item_name: str, stages: List[Dict[str, Any]]):
        """
        After saving a route, capture selectors in both verify and edit modes.
        This is called AFTER each successful save.
        """
        print(f"[Capture] Navigating to list to find '{item_name}'...")

        # Navigate back to list page
        try:
            self.driver.get(self.base_url)
            wait_dom_ready(self.driver)
            time.sleep(1.0)
        except Exception as e:
            print(f"[Capture] Failed to navigate to base URL: {e}")
            return

        # Search for the item (simplified - assumes there's a search field)
        try:
            search_inputs = self.driver.find_elements(By.CSS_SELECTOR,
                                                      "input[type='search'], input[placeholder*='Search'], input[placeholder*='search']")
            if search_inputs:
                search_input = search_inputs[0]
                search_input.clear()
                search_input.send_keys(item_name)
                time.sleep(1.0)
        except Exception as e:
            print(f"[Capture] Could not use search: {e}")

        # Click on first row to open the item
        try:
            first_row = self.driver.find_element(By.CSS_SELECTOR,
                                                 "table tbody tr:first-child, .list-item:first-child, .grid-item:first-child")
            safe_click(self.driver, first_row)
            wait_dom_ready(self.driver)
            time.sleep(1.0)
        except Exception as e:
            print(f"[Capture] Could not click first row: {e}")
            return

        # Check if there's an Edit button (means we're in VIEW mode)
        edit_button_found = False
        try:
            edit_buttons = find_clickables_by_keywords(self.driver, EDIT_BUTTON_KEYWORDS)
            if edit_buttons and edit_buttons[0].is_displayed():
                edit_button_found = True
                print(f"[Capture] VIEW mode detected (Edit button present)")

                # Capture VERIFY selectors (readonly mode)
                self._capture_verify_selectors_from_current_page(stages)

                # Now click Edit to enter edit mode
                safe_click(self.driver, edit_buttons[0])
                wait_dom_ready(self.driver)
                time.sleep(1.0)
                print(f"[Capture] Entered EDIT mode")
        except Exception:
            pass

        if not edit_button_found:
            print(f"[Capture] EDIT mode only (no separate view mode)")
            # No separate view mode - use edit selectors for verification too
            self._capture_verify_selectors_from_current_page(stages)

        # Capture EDIT selectors
        self._capture_edit_selectors_from_current_page(stages)

        print(f"[Capture] Completed capture for '{item_name}'")

    def _capture_verify_selectors_from_current_page(self, stages: List[Dict[str, Any]]):
        """Capture verification selectors from current page (readonly or edit mode)"""
        for stage in stages:
            if "field_id" not in stage:
                continue

            fid = stage["field_id"]
            label = stage.get("label", "")

            # Try to find the field element
            try:
                # Try multiple strategies
                selectors_to_try = [
                    f"#{fid}",
                    f"[name='{fid}']",
                    f"span:contains('{label}')",
                    f"div:contains('{label}')",
                ]

                found_selector = None
                for sel in selectors_to_try:
                    try:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        if els and els[0].is_displayed():
                            found_selector = sel
                            break
                    except Exception:
                        continue

                if found_selector:
                    self.verify_selectors[fid] = found_selector
                    print(f"[Verify] {fid}: {found_selector}")
            except Exception as e:
                print(f"[Verify] Could not capture selector for {fid}: {e}")

    def _capture_edit_selectors_from_current_page(self, stages: List[Dict[str, Any]]):
        """Capture edit selectors from current page (edit mode)"""
        for stage in stages:
            if "field_id" not in stage:
                continue

            fid = stage["field_id"]

            # Try to find the field element
            try:
                selectors_to_try = [
                    f"#{fid}",
                    f"[name='{fid}']",
                    f"input#{fid}",
                    f"textarea#{fid}",
                    f"select#{fid}",
                ]

                found_selector = None
                for sel in selectors_to_try:
                    try:
                        els = self.driver.find_elements(By.CSS_SELECTOR, sel)
                        if els and els[0].is_displayed():
                            found_selector = sel
                            break
                    except Exception:
                        continue

                if found_selector:
                    self.edit_selectors[fid] = found_selector
                    print(f"[Edit] {fid}: {found_selector}")
            except Exception as e:
                print(f"[Edit] Could not capture selector for {fid}: {e}")

    # CONTINUE TO NEXT MESSAGE FOR REST OF CODE...
    # form_routes_explorer.py (Part 3 of 3 - FINAL)
    # Consolidation, AND/OR detection, Grid columns, JSON generation

    # ========== Route Consolidation & Smart AND/OR Detection ==========
    def _consolidate_routes_and_build_final_json(self):
        """
        Consolidate all routes to detect hiding conditions and build final JSONs
        """
        print("[Consolidation] Analyzing all routes...")

        unified_fields = {}

        for field_id, appearances in self.field_appearances.items():
            first_appearance = appearances[0]["stage"]
            routes_with_field = [app["route"] for app in appearances]
            all_route_names = [r["route_name"] for r in self.all_routes]
            routes_without_field = [r for r in all_route_names if r not in routes_with_field]

            # Detect HIDING conditions (AND or OR)
            hiding_conditions = self._detect_hiding_conditions(
                field_id, appearances, routes_without_field
            )

            # Get field info for assignment rules
            field_info = {
                "field_type": first_appearance.get("field_type", "text"),
                "label": first_appearance.get("label", ""),
                "name": field_id,
                "options": self._get_field_options(field_id, appearances)
            }

            # Auto-fill update_fields_assignment
            if self.ai_helper:
                update_fields_assignment = self.ai_helper.determine_field_assignment(field_info)
            else:
                update_fields_assignment = {"type": "assign_random_text", "size": "50"}

            # Build verification_fields_assignment with HIDING conditions
            verification_fields_assignment = self._build_verification_assignment(hiding_conditions)

            # Get captured selectors
            verify_selector = self.verify_selectors.get(field_id, first_appearance.get("locator_hint", ""))
            edit_selector = self.edit_selectors.get(field_id, "")

            # Build gui_field entry
            gui_field = {
                "update_fields_assignment": update_fields_assignment,
                "verification_fields_assignment": verification_fields_assignment,
                "verification": {
                    "verification_method": "assertEqual",
                    "verification_css_location": verify_selector,  # FILLED
                    "verification_css_location_playwright": ""  # EMPTY
                },
                "update_api_fields_assignment": {},
                "update_action": self._build_update_action_if_different(
                    first_appearance, edit_selector
                ),
                "create_action": {
                    "create_type": "",
                    "update_ai_stages": self._build_ai_stages_for_field(first_appearance),
                    "action_description": f"interact with {sanitize_filename(first_appearance.get('label', field_id))}",
                    "update_css": "",  # LEFT EMPTY
                    "update_css_playwright": "",  # LEFT EMPTY
                    "non_editable_condition": self._detect_non_editable_condition(field_id, appearances,
                                                                                  routes_without_field),
                    "update_mandatory": True,
                    "validate_non_editable": False,
                    "webdriver_sleep_before_action": "",
                    "playwright_sleep_before_action": ""
                },
                "name": sanitize_filename(first_appearance.get("label", field_id)).replace(" ", "_").lower(),
                "api_name": ""
            }

            unified_fields[field_id] = gui_field

        # Identify grid column fields
        grid_column_fields = self._identify_grid_column_fields(unified_fields)

        # Build ordered gui_fields (grid columns first, then click, then detail fields)
        self.gui_fields = self._build_ordered_gui_fields(unified_fields, grid_column_fields)

        # Build gui_pre_verification_actions
        self.gui_pre_verification_actions = self._build_gui_pre_verification_actions()

        # Build gui_pre_update_actions (similar to verification + edit click)
        self.gui_pre_update_actions = self._build_gui_pre_update_actions()

        print(f"[Consolidation] Built {len(self.gui_fields)} unified fields")
        print(f"[Consolidation] Grid columns: {len(grid_column_fields)}")

    def _detect_hiding_conditions(
            self,
            field_id: str,
            appearances: List[Dict],
            routes_without: List[str]
    ) -> Optional[Dict[str, Any]]:
        """
        Detect HIDING conditions (when field is NOT visible).
        Returns AND or OR operator with conditions.
        Condition TRUE = field HIDDEN
        """
        if not appearances or not routes_without:
            return None

        # Build signatures for routes WITH field
        routes_with_field = {}
        for app in appearances:
            route_name = app.get("route", "")
            preconds = app.get("preconditions", [])

            precond_dict = {}
            for precond in preconds:
                if "field_id" in precond and "value" in precond:
                    precond_dict[precond["field_id"]] = precond["value"]

            routes_with_field[route_name] = precond_dict

        # Build signatures for routes WITHOUT field
        routes_without_field = {}

        for route in self.all_routes:
            route_name = route.get("route_name", "")
            if route_name not in routes_without:
                continue

            precond_dict = {}
            for stage in route.get("stages", []):
                if "field_id" in stage:
                    fid = stage["field_id"]
                    fval = stage.get("suggested_value")
                    if fid and fval:
                        precond_dict[fid] = fval

            routes_without_field[route_name] = precond_dict

        if not routes_without_field:
            return None

        # Find fields that appear in HIDDEN routes (potential hiding triggers)
        hiding_predictor_fields = set()
        for route_preconds in routes_without_field.values():
            hiding_predictor_fields.update(route_preconds.keys())

        if not hiding_predictor_fields:
            return None

        # Analyze each predictor to find HIDING values
        hiding_analysis = {}

        for predictor_field in hiding_predictor_fields:
            values_when_hidden = []
            for route_name, preconds in routes_without_field.items():
                if predictor_field in preconds:
                    values_when_hidden.append(preconds[predictor_field])

            values_when_visible = []
            for route_name, preconds in routes_with_field.items():
                if predictor_field in preconds:
                    values_when_visible.append(preconds[predictor_field])

            hidden_values_set = set(values_when_hidden)
            visible_values_set = set(values_when_visible)

            hiding_values = list(hidden_values_set - visible_values_set)

            if hiding_values:
                hiding_analysis[predictor_field] = {
                    "hiding_values": hiding_values,
                    "appears_in_hidden": len(values_when_hidden),
                    "total_hidden_routes": len(routes_without_field),
                    "is_always_present_when_hidden": len(values_when_hidden) == len(routes_without_field)
                }

        if not hiding_analysis:
            return None

        # Determine AND vs OR logic for HIDING
        predictors_always_in_hidden = [
            pred for pred, analysis in hiding_analysis.items()
            if analysis["is_always_present_when_hidden"]
        ]

        # Check if it's AND logic (all conditions must be true to hide)
        if len(predictors_always_in_hidden) > 1:
            is_and_logic = True

            # Verify: ALL hidden routes have ALL these conditions
            for route_preconds in routes_without_field.values():
                has_all_conditions = True
                for pred in predictors_always_in_hidden:
                    if pred not in route_preconds or \
                            route_preconds[pred] not in hiding_analysis[pred]["hiding_values"]:
                        has_all_conditions = False
                        break

                if not has_all_conditions:
                    is_and_logic = False
                    break

            # Verify: NO visible routes have ALL these conditions
            if is_and_logic:
                for route_preconds in routes_with_field.values():
                    has_all_conditions = True
                    for pred in predictors_always_in_hidden:
                        if pred not in route_preconds or \
                                route_preconds[pred] not in hiding_analysis[pred]["hiding_values"]:
                            has_all_conditions = False
                            break

                    if has_all_conditions:
                        is_and_logic = False
                        break

            if is_and_logic:
                print(f"[Hiding Logic] Field '{field_id}' uses AND hiding")
                conditions = [
                    {"field": pred, "value": hiding_analysis[pred]["hiding_values"]}
                    for pred in predictors_always_in_hidden
                ]
                return {
                    "operator": "and",
                    "conditions": conditions
                }

        # Otherwise, it's OR logic
        print(f"[Hiding Logic] Field '{field_id}' uses OR hiding")
        conditions = [
            {"field": pred, "value": analysis["hiding_values"]}
            for pred, analysis in hiding_analysis.items()
        ]

        return {
            "operator": "or",
            "conditions": conditions
        }

    def _build_verification_assignment(self, hiding_conditions: Optional[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Build verification_fields_assignment based on HIDING conditions.
        Condition TRUE = None (hidden)
        Condition FALSE = verify value
        """
        if not hiding_conditions:
            return {
                "type": "assign_same_value_as_in_assign_for_create"
            }

        operator = hiding_conditions.get("operator", "or")
        conditions = hiding_conditions.get("conditions", [])

        if not conditions:
            return {
                "type": "assign_same_value_as_in_assign_for_create"
            }

        if operator == "or":
            return {
                "type": "assign_with_conditions",
                "or condition": conditions,
                "condition_value_type": "None",  # When TRUE → hidden
                "else_condition_value_type": "assign_same_value_as_in_assign_for_create"  # When FALSE → verify
            }
        else:  # operator == "and"
            return {
                "type": "assign_with_conditions",
                "and condition": conditions,
                "condition_value_type": "None",
                "else_condition_value_type": "assign_same_value_as_in_assign_for_create"
            }

    def _detect_non_editable_condition(self, field_id: str, appearances: List[Dict], routes_without: List[str]) -> Dict[
        str, Any]:
        """Detect when field is HIDDEN (non-editable condition) - same as hiding conditions"""
        hiding = self._detect_hiding_conditions(field_id, appearances, routes_without)
        if hiding:
            result = {"operator": hiding["operator"]}
            for cond in hiding.get("conditions", []):
                result[cond["field"]] = cond["value"]
            return result
        return {"operator": "or"}

    def _get_field_options(self, field_id: str, appearances: List[Dict]) -> List[str]:
        """Get dropdown/radio options if applicable"""
        for app in appearances:
            stage = app["stage"]
            if stage.get("field_type") in ["select", "radio"]:
                options = set()
                for route in self.all_routes:
                    for s in route.get("stages", []):
                        if s.get("field_id") == field_id:
                            val = s.get("suggested_value")
                            if val:
                                options.add(val)
                return list(options)
        return []

    def _build_ai_stages_for_field(self, stage: Dict[str, Any]) -> List[Dict[str, Any]]:
        """Build update_ai_stages as list of DICTS (not strings!)"""
        ai_stages = []
        locator = stage.get("locator_hint", "")
        field_type = stage.get("field_type", "text")

        if field_type == "select":
            ai_stages.append({"action": "click", "locator": locator})
            ai_stages.append({"action": "select_by_text", "locator": locator})
        elif field_type in ["checkbox", "radio"]:
            ai_stages.append({"action": "click", "locator": locator})
        else:
            ai_stages.append({"action": "click", "locator": locator})
            ai_stages.append({"action": "type", "locator": locator})

        return ai_stages

    def _build_update_action_if_different(self, stage: Dict[str, Any], edit_selector: str) -> Dict[str, Any]:
        """Build update_action only if different from create_action"""
        create_selector = stage.get("locator_hint", "")

        # If selectors are the same or edit not captured, return empty
        if not edit_selector or edit_selector == create_selector:
            return {}

        # Different selector → build update_action
        field_type = stage.get("field_type", "text")
        update_ai_stages = []

        if field_type == "select":
            update_ai_stages.append({"action": "click", "locator": edit_selector})
            update_ai_stages.append({"action": "select_by_text", "locator": edit_selector})
        elif field_type in ["checkbox", "radio"]:
            update_ai_stages.append({"action": "click", "locator": edit_selector})
        else:
            update_ai_stages.append({"action": "click", "locator": edit_selector})
            update_ai_stages.append({"action": "clear", "locator": edit_selector})
            update_ai_stages.append({"action": "type", "locator": edit_selector})

        return {
            "update_type": "",
            "update_ai_stages": update_ai_stages,
            "action_description": f"update {stage.get('label', '')}",
            "update_css": "",  # LEFT EMPTY
            "update_css_playwright": "",
            "non_editable_condition": {"operator": "or"},
            "update_mandatory": True,
            "validate_non_editable": False,
            "webdriver_sleep_before_action": "",
            "playwright_sleep_before_action": ""
        }

    def _identify_grid_column_fields(self, unified_fields: Dict) -> List[str]:
        """Identify 3-5 most important fields for grid columns"""
        column_candidates = []

        for field_id, field_data in unified_fields.items():
            field_name = field_data.get("name", "").lower()

            score = 0
            if "name" in field_name or "title" in field_name:
                score += 100
            if "type" in field_name:
                score += 80
            if "status" in field_name or "state" in field_name:
                score += 70
            if "date" in field_name:
                score += 60
            if "email" in field_name:
                score += 50

            if score > 0:
                column_candidates.append({
                    "field_id": field_id,
                    "name": field_name,
                    "score": score
                })

        column_candidates.sort(key=lambda x: x["score"], reverse=True)
        top_columns = column_candidates[:5]  # Max 5 columns

        grid_column_ids = [col["field_id"] for col in top_columns]
        print(f"[Grid Columns] Selected: {[col['name'] for col in top_columns]}")

        return grid_column_ids

    def _build_ordered_gui_fields(
            self,
            unified_fields: Dict,
            grid_column_fields: List[str]
    ) -> List[Dict[str, Any]]:
        """
        Build gui_fields in 3-stage order:
        1. Grid column verification (empty assignments)
        2. Click action to open detail
        3. All detail form fields
        """
        ordered_fields = []

        # Stage 1: Grid column verification fields
        for idx, field_id in enumerate(grid_column_fields, 1):
            if field_id in unified_fields:
                field_data = unified_fields[field_id].copy()

                field_data["update_fields_assignment"] = {}  # EMPTY
                field_data["verification_fields_assignment"] = {}  # EMPTY
                field_data["create_action"] = {}  # EMPTY
                field_data["update_action"] = {}  # EMPTY

                field_data["verification"] = {
                    "verification_method": "assertEqual",
                    "verification_css_location": f"table tbody tr:first-child td:nth-child({idx})",
                    "verification_css_location_playwright": ""
                }

                field_data["is_grid_column"] = True
                ordered_fields.append(field_data)

        # Stage 2: Click action to open detail page
        click_action_field = {
            "update_fields_assignment": {},
            "verification_fields_assignment": {},
            "verification": {
                "verification_method": "click_button",
                "verification_ai_stages": [
                    {"action": "click", "locator": "table tbody tr:first-child"}
                ],
                "verification_css_location": "",  # EMPTY (action method)
                "verification_css_location_playwright": ""
            },
            "update_api_fields_assignment": {},
            "update_action": {},
            "create_action": {},
            "name": "open_detail_page",
            "api_name": "",
            "is_click_action": True
        }
        ordered_fields.append(click_action_field)

        # Stage 3: All detail form fields
        for field_id, field_data in unified_fields.items():
            if field_id not in grid_column_fields:
                ordered_fields.append(field_data)

        return ordered_fields

    def _build_gui_pre_verification_actions(self) -> List[Dict[str, Any]]:
        """Build gui_pre_verification_actions with navigation and search"""
        actions = []

        # Add navigation steps from form discovery
        for step in self.gui_pre_verification_actions:
            if step.get("action") == "click":
                actions.append({
                    "update_type": "click_button",
                    "action_description": step.get("action_description", "navigate"),
                    "update_ai_stages": [
                        {"action": "click", "locator": step.get("locator_text", "")}
                    ],
                    "update_css": "",
                    "update_css_playwright": "",
                    "webdriver_sleep_before_action": "",
                    "playwright_sleep_before_action": "",
                    "non_editable_condition": {}
                })

        # Find name field for search
        name_field = self._find_name_field_info()

        if name_field:
            # Add search input action
            actions.append({
                "name": name_field["name"],
                "update_type": "enter_text",
                "action_description": f"enter_{name_field['name']}_to_search_it",
                "update_ai_stages": [
                    {"action": "type", "locator": "input[placeholder*='Search']"}
                ],
                "update_css": "",
                "update_css_playwright": "",
                "webdriver_sleep_before_action": "5",
                "playwright_sleep_before_action": "2",
                "non_editable_condition": {"operator": "or"}
            })

            # Add sleep after search
            actions.append({
                "update_type": "sleep",
                "action_description": "wait for search results",
                "non_editable_condition": {},
                "value": "2"
            })

        return actions

    def _build_gui_pre_update_actions(self) -> List[Dict[str, Any]]:
        """Build gui_pre_update_actions (same as verification + edit click)"""
        actions = self._build_gui_pre_verification_actions().copy()

        # Add click edit button
        actions.append({
            "update_type": "click_button",
            "action_description": "click edit button",
            "update_ai_stages": [
                {"action": "click_if_visible", "locator": "button.edit, button[aria-label='Edit']", "timeout": "2"}
            ],
            "update_css": "",
            "update_css_playwright": "",
            "webdriver_sleep_before_action": "",
            "playwright_sleep_before_action": "",
            "non_editable_condition": {}
        })

        return actions

    def _find_name_field_info(self) -> Optional[Dict[str, Any]]:
        """Find the name/title field from gui_fields"""
        for field in self.gui_fields:
            field_name = field.get("name", "").lower()
            if any(hint in field_name for hint in ["name", "title"]):
                return {"name": field.get("name")}

        if self.gui_fields:
            return {"name": self.gui_fields[0].get("name")}

        return None

    # ========== JSON Generation ==========
    def _save_main_setup_json(self):
        """Save main_setup.json (the main entity JSON)"""
        main_setup = {
            "gui_pre_create_actions": self.gui_pre_create_actions,
            "css_values": [
                {"name": "save_button_css", "value": ""},
                {"name": "edit_button_css", "value": ""},
                # ... (all CSS values left empty)
            ],
            "gui_post_update_actions": [],
            "gui_post_create_actions": [],
            "gui_pre_update_actions": self.gui_pre_update_actions,
            "gui_pre_verification_actions": self.gui_pre_verification_actions,
            "system_values": [
                {"name": "main_component_tab", "value": "main"},
                {"name": "is_sub_project", "value": False},
                {"name": "form_page_is_a_list", "value": False},
                # ... (other system values)
            ],
            "sub_components": [],
            "pre_fields_values": [],
            "non_editable_condition": {},
            "gui_fields": self.gui_fields
        }

        with open(self.main_setup_json_path, "w", encoding="utf-8") as f:
            json.dump(main_setup, f, indent=2)
        print(f"[JSON] Saved {self.main_setup_json_path}")

    def _save_setup_json(self):
        """Save setup.json (sub-project JSON)"""
        setup = {
            "gui_pre_create_actions": [],
            "css_values": [],
            "all_sub_components_items_list": [self.form_name, f"{self.form_name}_main"],
            "gui_pre_verification_actions": [],
            "gui_pre_update_actions": [],
            "system_values": [
                {"name": "is_sub_project", "value": True},
                # ... (other system values)
            ],
            "sub_components": [{"type": "single", "name": "main"}],
            "gui_fields": []
        }

        with open(self.setup_json_path, "w", encoding="utf-8") as f:
            json.dump(setup, f, indent=2)
        print(f"[JSON] Saved {self.setup_json_path}")

    # ========== Supporting methods ==========
    def _field_stage(self, fid, label, locator, ftype, value, preconds):
        return asdict(FieldStage(
            field_id=fid, label=label, locator_hint=locator,
            field_type=ftype, suggested_value=value,
            preconditions=self._precondition_list(preconds),
            actions=[
                {"action": "click", "selector_hint": locator},
                {"action": "type_or_set", "selector_hint": locator, "value": value}
            ]
        ))

    def _precondition_list(self, stages_so_far: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        out = []
        for st in stages_so_far:
            if "field_id" in st:
                out.append({"field_id": st["field_id"], "value": st.get("suggested_value")})
            elif "label" in st and st.get("actions"):
                out.append({"interaction": st["label"]})
        return out

    def _set_select_value(self, el, value: str, route_note: str):
        if not select_by_visible_text_if_native(el, value):
            try:
                safe_click(self.driver, el)
                el.send_keys(value)
            except Exception:
                pass
        self._post_action_check_and_fix(route_note)

    def _perform_branch_action(self, action_dict: Dict[str, Any], route_note: str):
        acts = action_dict.get("actions", [])
        for a in acts:
            hint = a.get("selector_hint")
            val = a.get("value")
            el = self._find_by_hint(hint)
            if not el:
                continue
            if a["action"] == "click":
                safe_click(self.driver, el)
            elif a["action"] == "select_by_text":
                if not select_by_visible_text_if_native(el, val):
                    safe_click(self.driver, el)
                    try:
                        el.send_keys(val)
                    except Exception:
                        pass
            if not self._post_action_check_and_fix(route_note):
                break
            time.sleep(0.1)

    def _find_by_hint(self, hint: str):
        if not hint:
            return None
        try:
            if hint.startswith("#") or hint.startswith("["):
                return self.driver.find_element(By.CSS_SELECTOR, hint)
            if ":" in hint and not hint.startswith("//"):
                tag, _, txt = hint.partition(":")
                cands = self.driver.find_elements(By.TAG_NAME, tag or "*")
                for c in cands:
                    if txt.strip().lower() in visible_text(c).lower():
                        return c
            return self.driver.find_element(By.CSS_SELECTOR, hint)
        except Exception:
            return None
