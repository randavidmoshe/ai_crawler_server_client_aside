# ai_form_mapper_end_prompter.py
# Assign test cases to stages after test completion

import json
import anthropic
from typing import List, Dict

class AIFormPageEndPrompter:
    """Assigns test_case field to completed stages"""
    
    def __init__(self, api_key: str):
        self.client = anthropic.Anthropic(api_key=api_key)
        self.model = "claude-sonnet-4-5-20250929"
    
    def assign_test_cases(self, stages: List[Dict], test_cases: List[Dict]) -> List[Dict]:
        """
        Call AI to assign test_case field to each stage
        
        Args:
            stages: List of stage dicts (each stage should have "test_case": "" field)
            test_cases: List of test case dicts from test_cases1.json
            
        Returns:
            Updated stages list with test_case assigned
        """
        prompt = f"""You are a test automation assistant. You previously created these stages to fill a form page according to test cases.

Now you need to assign the correct test_case field to each stage.

## Test Cases:
{json.dumps(test_cases, indent=2)}

## Stages (to be updated):
{json.dumps(stages, indent=2)}

## Your Task:
For each stage in the stages array, determine which test case it belongs to and update the "test_case" field with the correct test_id (e.g., "TEST_1_create_form", "TEST_2_edit_form", etc.).

**Rules:**
- Stages for creating/filling the form → assign to TEST_1 (or first test)
- Stages for editing/updating fields → assign to TEST_2 (or second test)
- Use the test_id from test_cases exactly as shown
- Keep all other fields in each stage unchanged

Return ONLY the updated stages array as valid JSON. No explanation, just the JSON array.
"""
        
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=20000,
                messages=[{"role": "user", "content": prompt}]
            )
            
            response_text = message.content[0].text
            
            # Extract JSON array
            import re
            json_match = re.search(r'\[[\s\S]*\]', response_text)
            if json_match:
                updated_stages = json.loads(json_match.group())
                return updated_stages
            else:
                print("❌ Failed to parse AI response")
                return stages
                
        except Exception as e:
            print(f"❌ Error calling AI: {e}")
            return stages
