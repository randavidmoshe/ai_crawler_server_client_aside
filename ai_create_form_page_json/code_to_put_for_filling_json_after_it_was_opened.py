


def map_currently_open_form(driver, form_name, ai_client, existing_json_path):
    """
    Map currently open form and UPDATE the existing JSON file with gui_fields

    Args:
        driver: Selenium WebDriver
        form_name: Name for the form
        ai_client: AI client instance
        existing_json_path: Path to FULL JSON that will be UPDATED (e.g., "engagement_main_setup.json")

    Returns:
        dict: Complete updated form JSON
    """
    from form_mapper_orchestrator import FormMapperOrchestrator
    import json

    # Load existing JSON
    with open(existing_json_path, 'r') as f:
        existing_json = json.load(f)

    # Create orchestrator
    orchestrator = FormMapperOrchestrator(
        selenium_driver=driver,
        ai_client=ai_client,
        form_name=form_name
    )

    # Map the form (AI discovers gui_fields)
    result = orchestrator.start_mapping(max_iterations=30)

    # Update the existing JSON with the new gui_fields
    existing_json['gui_fields'] = result['gui_fields']

    # Write back to the SAME file (updates it in place)
    with open(existing_json_path, 'w') as f:
        json.dump(existing_json, f, indent=4, ensure_ascii=False)

    print(f"✓ Updated {existing_json_path} with {len(result['gui_fields'])} gui_fields")

    return existing_json


# Usage:
result = map_currently_open_form(
    driver=driver,
    form_name="engagement",
    ai_client=ai_client,
    existing_json_path="engagement_main_setup.json"  # This file gets UPDATED!(we put here full path and it will update in this path
)