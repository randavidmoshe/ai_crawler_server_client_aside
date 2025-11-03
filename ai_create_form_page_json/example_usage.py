"""
Complete Example: Form Mapper
Demonstrates the full AI-Selenium form mapping workflow
"""

import os
import sys
import json
from selenium import webdriver
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.chrome.service import Service

# Import our modules
from form_mapper_orchestrator import FormMapperOrchestrator
from ai_client_wrapper import AIClientWrapper, MockAIClient


def setup_selenium_driver(headless: bool = False):
    """
    Setup and return a Selenium WebDriver
    
    Args:
        headless: Run browser in headless mode
        
    Returns:
        WebDriver instance
    """
    options = Options()
    
    if headless:
        options.add_argument('--headless')
    
    options.add_argument('--no-sandbox')
    options.add_argument('--disable-dev-shm-usage')
    options.add_argument('--disable-gpu')
    options.add_argument('--window-size=1920,1080')
    
    # Initialize driver
    # Note: Make sure chromedriver is in your PATH or specify path to Service
    try:
        driver = webdriver.Chrome(options=options)
    except Exception as e:
        print(f"Error initializing Chrome driver: {e}")
        print("Make sure you have Chrome and chromedriver installed")
        sys.exit(1)
    
    return driver


def map_form_with_real_ai(
    form_url: str,
    form_name: str,
    api_key: str = None,
    headless: bool = False
):
    """
    Map a form using real AI (Claude)
    
    Args:
        form_url: URL of the form to map
        form_name: Name for the form (used in output filename)
        api_key: Anthropic API key (or from environment)
        headless: Run browser in headless mode
    """
    print("="*70)
    print("FORM MAPPER - Real AI Mode (Claude)")
    print("="*70)
    print(f"Form URL: {form_url}")
    print(f"Form Name: {form_name}")
    print()
    
    # Setup Selenium
    print("Setting up Selenium WebDriver...")
    driver = setup_selenium_driver(headless=headless)
    
    try:
        # Navigate to form
        print(f"Navigating to: {form_url}")
        driver.get(form_url)
        
        # Wait for page load
        driver.implicitly_wait(3)
        
        # Setup AI client
        print("Initializing AI client...")
        ai_client = AIClientWrapper(
            api_key=api_key,
            provider="claude",
            model="claude-3-5-sonnet-20241022"
        )
        
        # Create orchestrator
        orchestrator = FormMapperOrchestrator(
            selenium_driver=driver,
            ai_client=ai_client,
            form_name=form_name
        )
        
        # Start mapping
        print("\nStarting form mapping process...")
        print("This may take several minutes depending on form complexity.")
        print()
        
        result_json = orchestrator.start_mapping(max_iterations=30)
        
        # Print summary
        print("\n" + "="*70)
        print("MAPPING COMPLETE!")
        print("="*70)
        print(f"Total fields mapped: {len(result_json.get('gui_fields', []))}")
        print(f"Total iterations: {orchestrator.state.iteration_count}")
        print(f"Interactions performed: {len(orchestrator.state.interaction_history)}")
        print(f"Output file: {form_name}_main_setup.json")
        print()
        
        # Save state for potential resume
        orchestrator.save_state()
        
        return result_json
        
    except KeyboardInterrupt:
        print("\n\nMapping interrupted by user.")
        print("Saving current state...")
        orchestrator.save_state()
        print("You can resume later by loading the state file.")
        
    except Exception as e:
        print(f"\n\nError during mapping: {str(e)}")
        import traceback
        traceback.print_exc()
        
    finally:
        print("\nClosing browser...")
        driver.quit()


def map_form_with_mock_ai(
    form_url: str,
    form_name: str,
    headless: bool = False
):
    """
    Map a form using mock AI (for testing without API)
    
    Args:
        form_url: URL of the form to map
        form_name: Name for the form
        headless: Run browser in headless mode
    """
    print("="*70)
    print("FORM MAPPER - Mock AI Mode (Testing)")
    print("="*70)
    print(f"Form URL: {form_url}")
    print(f"Form Name: {form_name}")
    print()
    
    # Setup Selenium
    print("Setting up Selenium WebDriver...")
    driver = setup_selenium_driver(headless=headless)
    
    try:
        # Navigate to form
        print(f"Navigating to: {form_url}")
        driver.get(form_url)
        driver.implicitly_wait(3)
        
        # Setup mock AI client
        print("Initializing mock AI client...")
        ai_client = MockAIClient()
        
        # Create orchestrator
        orchestrator = FormMapperOrchestrator(
            selenium_driver=driver,
            ai_client=ai_client,
            form_name=form_name
        )
        
        # Start mapping
        print("\nStarting form mapping process (mock mode)...")
        print()
        
        result_json = orchestrator.start_mapping(max_iterations=5)
        
        # Print summary
        print("\n" + "="*70)
        print("MOCK MAPPING COMPLETE!")
        print("="*70)
        print(f"Total fields mapped: {len(result_json.get('gui_fields', []))}")
        print(f"Output file: {form_name}_main_setup.json")
        print()
        
        return result_json
        
    finally:
        print("\nClosing browser...")
        driver.quit()


def resume_mapping(
    state_file: str,
    form_url: str,
    api_key: str = None,
    headless: bool = False
):
    """
    Resume a previously interrupted mapping session
    
    Args:
        state_file: Path to saved state JSON file
        form_url: URL of the form
        api_key: Anthropic API key
        headless: Run browser in headless mode
    """
    print("="*70)
    print("FORM MAPPER - Resuming Session")
    print("="*70)
    print(f"State file: {state_file}")
    print()
    
    # Setup Selenium
    driver = setup_selenium_driver(headless=headless)
    
    try:
        # Navigate to form
        driver.get(form_url)
        driver.implicitly_wait(3)
        
        # Setup AI client
        ai_client = AIClientWrapper(api_key=api_key, provider="claude")
        
        # Extract form name from state file
        form_name = state_file.replace('_mapping_state.json', '')
        
        # Create orchestrator
        orchestrator = FormMapperOrchestrator(
            selenium_driver=driver,
            ai_client=ai_client,
            form_name=form_name
        )
        
        # Load previous state
        print("Loading previous state...")
        orchestrator.load_state(state_file)
        
        print(f"Resuming from iteration {orchestrator.state.iteration_count}")
        print()
        
        # Continue mapping
        result_json = orchestrator.start_mapping(max_iterations=30)
        
        print("\n" + "="*70)
        print("MAPPING COMPLETE!")
        print("="*70)
        
        return result_json
        
    finally:
        driver.quit()


def main():
    """Main entry point with command-line interface"""
    import argparse
    
    parser = argparse.ArgumentParser(
        description="AI-powered form mapper using Selenium"
    )
    
    parser.add_argument(
        'url',
        help='URL of the form to map'
    )
    
    parser.add_argument(
        'form_name',
        help='Name for the form (used in output filename)'
    )
    
    parser.add_argument(
        '--api-key',
        help='Anthropic API key (or set ANTHROPIC_API_KEY env var)',
        default=None
    )
    
    parser.add_argument(
        '--mock',
        action='store_true',
        help='Use mock AI for testing (no API calls)'
    )
    
    parser.add_argument(
        '--headless',
        action='store_true',
        help='Run browser in headless mode'
    )
    
    parser.add_argument(
        '--resume',
        help='Resume from a saved state file',
        default=None
    )
    
    args = parser.parse_args()
    
    # Resume mode
    if args.resume:
        resume_mapping(
            state_file=args.resume,
            form_url=args.url,
            api_key=args.api_key,
            headless=args.headless
        )
        return
    
    # Mock mode
    if args.mock:
        map_form_with_mock_ai(
            form_url=args.url,
            form_name=args.form_name,
            headless=args.headless
        )
        return
    
    # Real AI mode
    if not args.api_key and not os.getenv('ANTHROPIC_API_KEY'):
        print("ERROR: No API key provided.")
        print("Either:")
        print("  1. Use --api-key argument")
        print("  2. Set ANTHROPIC_API_KEY environment variable")
        print("  3. Use --mock flag for testing without API")
        sys.exit(1)
    
    map_form_with_real_ai(
        form_url=args.url,
        form_name=args.form_name,
        api_key=args.api_key,
        headless=args.headless
    )


if __name__ == "__main__":
    # Example usage (uncomment to run directly)
    
    # Example 1: Mock mode (no API needed)
    # map_form_with_mock_ai(
    #     form_url="https://example.com/form",
    #     form_name="test_form",
    #     headless=False
    # )
    
    # Example 2: Real AI mode
    # map_form_with_real_ai(
    #     form_url="https://your-app.com/engagement-form",
    #     form_name="engagement",
    #     api_key="your-api-key-here",
    #     headless=False
    # )
    
    # Example 3: Command-line interface
    main()
