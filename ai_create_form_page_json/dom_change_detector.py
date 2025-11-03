"""
DOM Change Detector - Compares DOMs to detect field appearances/disappearances
"""

from typing import Dict, List, Set, Optional
from dataclasses import dataclass
import re


@dataclass
class DOMChange:
    """Represents a change in the DOM"""
    appeared_fields: List[Dict]  # Fields that appeared
    disappeared_fields: List[Dict]  # Fields that disappeared
    unchanged_fields: List[Dict]  # Fields present in both


class DOMChangeDetector:
    """
    Detects changes between two DOM states.
    Identifies form fields that appeared, disappeared, or remained.
    """
    
    def __init__(self):
        self.field_patterns = {
            'input': r'<input[^>]*>',
            'select': r'<select[^>]*>.*?</select>',
            'textarea': r'<textarea[^>]*>.*?</textarea>',
            'button': r'<button[^>]*>.*?</button>'
        }
    
    def detect_changes(self, previous_dom: Optional[str], current_dom: str) -> DOMChange:
        """
        Compare two DOMs and detect field changes.
        
        Args:
            previous_dom: Previous DOM HTML (or None for first iteration)
            current_dom: Current DOM HTML
            
        Returns:
            DOMChange object with lists of appeared/disappeared/unchanged fields
        """
        if not previous_dom:
            # First iteration - all fields are "new"
            current_fields = self._extract_fields(current_dom)
            return DOMChange(
                appeared_fields=[],  # Don't mark as appeared on first iteration
                disappeared_fields=[],
                unchanged_fields=current_fields
            )
        
        # Extract fields from both DOMs
        previous_fields = self._extract_fields(previous_dom)
        current_fields = self._extract_fields(current_dom)
        
        # Create sets of field identifiers
        prev_ids = {self._get_field_id(f) for f in previous_fields}
        curr_ids = {self._get_field_id(f) for f in current_fields}
        
        # Detect changes
        appeared_ids = curr_ids - prev_ids
        disappeared_ids = prev_ids - curr_ids
        unchanged_ids = prev_ids & curr_ids
        
        # Build result
        return DOMChange(
            appeared_fields=[f for f in current_fields if self._get_field_id(f) in appeared_ids],
            disappeared_fields=[f for f in previous_fields if self._get_field_id(f) in disappeared_ids],
            unchanged_fields=[f for f in current_fields if self._get_field_id(f) in unchanged_ids]
        )
    
    def _extract_fields(self, dom_html: str) -> List[Dict]:
        """
        Extract all form fields from DOM.
        
        Returns:
            List of field dicts with {type, id, name, tag}
        """
        fields = []
        
        # Extract inputs
        for match in re.finditer(self.field_patterns['input'], dom_html, re.DOTALL | re.IGNORECASE):
            tag_html = match.group(0)
            field_info = self._parse_field_tag(tag_html, 'input')
            if field_info:
                fields.append(field_info)
        
        # Extract selects
        for match in re.finditer(self.field_patterns['select'], dom_html, re.DOTALL | re.IGNORECASE):
            tag_html = match.group(0)
            field_info = self._parse_field_tag(tag_html, 'select')
            if field_info:
                fields.append(field_info)
        
        # Extract textareas
        for match in re.finditer(self.field_patterns['textarea'], dom_html, re.DOTALL | re.IGNORECASE):
            tag_html = match.group(0)
            field_info = self._parse_field_tag(tag_html, 'textarea')
            if field_info:
                fields.append(field_info)
        
        return fields
    
    def _parse_field_tag(self, tag_html: str, tag_type: str) -> Optional[Dict]:
        """
        Parse a field tag and extract attributes.
        
        Returns:
            Dict with field info or None
        """
        # Extract id
        id_match = re.search(r'id=["\']([^"\']+)["\']', tag_html, re.IGNORECASE)
        field_id = id_match.group(1) if id_match else None
        
        # Extract name
        name_match = re.search(r'name=["\']([^"\']+)["\']', tag_html, re.IGNORECASE)
        field_name = name_match.group(1) if name_match else None
        
        # Extract type (for inputs)
        type_match = re.search(r'type=["\']([^"\']+)["\']', tag_html, re.IGNORECASE)
        input_type = type_match.group(1) if type_match else 'text'
        
        # Skip hidden fields
        if input_type == 'hidden':
            return None
        
        # Need at least id or name
        if not field_id and not field_name:
            return None
        
        return {
            'tag': tag_type,
            'id': field_id,
            'name': field_name,
            'type': input_type if tag_type == 'input' else tag_type,
            'html': tag_html[:200]  # First 200 chars for reference
        }
    
    def _get_field_id(self, field: Dict) -> str:
        """
        Create unique identifier for a field.
        Uses id if available, otherwise name.
        """
        if field['id']:
            return f"{field['tag']}#{field['id']}"
        elif field['name']:
            return f"{field['tag']}@{field['name']}"
        else:
            # Fallback to hash of html
            return f"{field['tag']}:{hash(field['html'])}"
    
    def format_change_summary(self, change: DOMChange) -> str:
        """Create human-readable summary of changes"""
        lines = []
        
        if change.appeared_fields:
            lines.append(f"  ✨ {len(change.appeared_fields)} field(s) APPEARED:")
            for field in change.appeared_fields[:5]:  # Show first 5
                field_desc = field['id'] or field['name'] or field['tag']
                lines.append(f"     + {field_desc}")
        
        if change.disappeared_fields:
            lines.append(f"  ⚠️  {len(change.disappeared_fields)} field(s) DISAPPEARED:")
            for field in change.disappeared_fields[:5]:
                field_desc = field['id'] or field['name'] or field['tag']
                lines.append(f"     - {field_desc}")
        
        if not change.appeared_fields and not change.disappeared_fields:
            lines.append(f"  ✓ No changes ({len(change.unchanged_fields)} fields stable)")
        
        return "\n".join(lines)
    
    def extract_interactive_elements_from_dom(self, dom_html: str, depth: int = 0, parent_path: List[Dict] = None) -> List[Dict]:
        """
        Extract ALL interactive elements from DOM for exploration.
        Includes: dropdowns, tabs, radio buttons, checkboxes, buttons
        
        Args:
            dom_html: HTML content
            depth: Current nesting depth
            parent_path: Path taken to reach this DOM state
            
        Returns:
            List of interactive element dicts
        """
        if parent_path is None:
            parent_path = []
        
        elements = []
        
        # 1. DROPDOWNS - Extract with their options
        select_pattern = r'<select[^>]*(?:id=["\']([^"\']+)["\']|name=["\']([^"\']+)["\'])[^>]*>(.*?)</select>'
        for match in re.finditer(select_pattern, dom_html, re.DOTALL | re.IGNORECASE):
            select_id = match.group(1) or match.group(2)
            select_content = match.group(3)
            
            if not select_id:
                continue
            
            # Extract options
            options = []
            option_pattern = r'<option[^>]*value=["\']([^"\']*)["\']'
            for opt_match in re.finditer(option_pattern, select_content, re.IGNORECASE):
                value = opt_match.group(1)
                if value and value.strip() and value.lower() not in ['', 'select', 'choose', 'select one']:
                    options.append(value)
            
            if options:
                xpath = f"//select[@id='{select_id}']" if match.group(1) else f"//select[@name='{select_id}']"
                
                # FILTER: Only explore dropdowns with ≤ 4 options
                # Dropdowns with many options are data fields (countries, states, years)
                # Dropdowns with few options are conditional triggers (type, category)
                MAX_DROPDOWN_OPTIONS = 4
                
                if len(options) <= MAX_DROPDOWN_OPTIONS:
                    elements.append({
                        'id': select_id,
                        'type': 'dropdown',
                        'locator': xpath,
                        'options': options,
                        'depth': depth,
                        'parent_path': parent_path
                    })
                else:
                    print(f"  ⏭️ Skipping dropdown '{select_id}' ({len(options)} options - data field, not conditional trigger)")
        
        # 2. (REMOVED: Tabs are navigation, not choice selection)
        
        # 2. RADIO BUTTON GROUPS - Group by name attribute
        radio_pattern = r'<input[^>]*type=["\']radio["\'][^>]*name=["\']([^"\']+)["\'][^>]*value=["\']([^"\']+)["\'][^>]*>'
        radio_groups = {}
        for match in re.finditer(radio_pattern, dom_html, re.IGNORECASE):
            radio_name = match.group(1)
            radio_value = match.group(2)
            
            if radio_name not in radio_groups:
                radio_groups[radio_name] = []
            radio_groups[radio_name].append(radio_value)
        
        for radio_name, radio_values in radio_groups.items():
            if len(radio_values) > 1:  # Only if multiple options
                xpath = f"//input[@type='radio' and @name='{radio_name}']"
                
                elements.append({
                    'id': radio_name,
                    'type': 'radio',
                    'locator': xpath,
                    'options': radio_values,
                    'depth': depth,
                    'parent_path': parent_path,
                    'radio_name': radio_name
                })
        
        # 3. CHECKBOX GROUPS + TOGGLE CHECKBOXES
        # AND Single toggle checkboxes (binary choice like on/off, yes/no)
        checkbox_pattern = r'<input[^>]*type=["\']checkbox["\'][^>]*(?:id=["\']([^"\']+)["\']|name=["\']([^"\']+)["\'])[^>]*>'
        checkbox_groups = {}
        single_checkboxes = {}
        
        for match in re.finditer(checkbox_pattern, dom_html, re.IGNORECASE):
            checkbox_id = match.group(1) or match.group(2)
            
            if not checkbox_id:
                continue
            
            # Check if this is part of a group (multiple checkboxes with same name)
            checkbox_name = match.group(2) if match.group(2) else checkbox_id
            
            if checkbox_name not in checkbox_groups:
                checkbox_groups[checkbox_name] = []
            checkbox_groups[checkbox_name].append({
                'id': checkbox_id,
                'name': checkbox_name,
                'match': match
            })
        
        # Process checkbox groups vs single checkboxes
        for checkbox_name, checkboxes in checkbox_groups.items():
            if len(checkboxes) > 1:
                # CHECKBOX GROUP - Multiple checkboxes with same name
                # These are choice selections (select multiple from list)
                xpath = f"//input[@type='checkbox' and @name='{checkbox_name}']"
                
                elements.append({
                    'id': checkbox_name,
                    'type': 'checkbox_group',
                    'locator': xpath,
                    'options': [cb['id'] for cb in checkboxes],  # Each checkbox is an option
                    'depth': depth,
                    'parent_path': parent_path
                })
                print(f"  ✓ Found checkbox group '{checkbox_name}' with {len(checkboxes)} options")
            # REMOVED: Single checkboxes (toggle switches) are NOT conditional triggers
            # They're just binary on/off fields, not choice selections like dropdowns
            # else:
            #     # SINGLE CHECKBOX - Toggle switch (on/off, yes/no)
            #     # Binary choice that might trigger conditional fields
            #     checkbox = checkboxes[0]
            #     xpath = f"//input[@type='checkbox' and @id='{checkbox['id']}']" if match.group(1) else f"//input[@type='checkbox' and @name='{checkbox['name']}']"
            #     
            #     elements.append({
            #         'id': checkbox['id'],
            #         'type': 'checkbox_toggle',
            #         'locator': xpath,
            #         'options': ['checked', 'unchecked'],  # Two states
            #         'depth': depth,
            #         'parent_path': parent_path
            #     })
            #     print(f"  ✓ Found toggle checkbox '{checkbox['id']}'")
        
        # 5. (REMOVED: Regular buttons are actions, not choice selection)
        
        return elements

