# server_entry_point.py
# SERVER SIDE - Entry point only
# Tells agent what to do

import os

# Import AGENT
from agent_form_pages_main import Agent
# Import SERVER
from server_form_pages_main import Server


if __name__ == "__main__":
    # ============================================================
    # SERVER CONFIGURATION
    # ============================================================
    
    print("\n" + "="*70)
    print("🖥️  SERVER: Starting crawler via agent")
    print("="*70)

    PROJECT_NAME = "orange_app"
    
    # List of login configurations
    # Each item can have: url (required), username (optional), password (optional)
    # If username/password are missing, no login/logout will be performed
    LOGIN_CONFIGS = [
        {
            "url": "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login",
            "username": "Admin",
            "password": "admin123"
        },
        {
            "url": "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login",
            "username": "Admin",
            "password": "admin123"
        }
        # Add more login configs here for multiple users:
        # {
        #     "url": "https://app.com/user-login",
        #     "username": "user",
        #     "password": "user123"
        # },
        # {
        #     "url": "https://app.com/no-login"  # No username/password = no login
        # }
    ]

    LOGGED_IN = False

    API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    if API_KEY:
        print(f"[Server] ✅ API Key loaded")
    else:
        print("[Server] ❌ No API key - Server AI will not work")

    DISCOVERY_ONLY = True
    TARGET_FORMS = []
    MAX_FORM_PAGES_TO_LOCATE = None
    MAX_DEPTH = 20
    SLOW_MODE = True
    HEADLESS = False
    HIDDEN = False
    UI_VERIFICATION = True  # Enable AI-powered UI defect detection

    print("[Server] Instructing agent to start crawl...")
    print("="*70 + "\n")

    # ============================================================
    # CREATE SERVER AND AGENT
    # ============================================================
    
    try:
        # Create agent
        agent = Agent()
        
        # Create server with max form pages limit and agent reference
        server = Server(api_key=API_KEY, max_form_pages=MAX_FORM_PAGES_TO_LOCATE, agent=agent)
        server.ui_verification = UI_VERIFICATION  # Set UI verification flag
        
        # Start driver on agent
        agent.start_driver(headless=HEADLESS, hidden=HIDDEN)
        
        # Run crawler with login configs - pass server to agent
        agent.run_crawler_with_multiple_logins(
            login_configs=LOGIN_CONFIGS,
            project_name=PROJECT_NAME,
            logged_in=LOGGED_IN,
            target_form_pages=TARGET_FORMS,
            server=server,
            max_depth=MAX_DEPTH,
            discovery_only=DISCOVERY_ONLY,
            slow_mode=SLOW_MODE
        )
        
        # Stop driver
        agent.stop_driver()
        
        # Print AI cost summary
        server.print_ai_cost_summary()
        
        print("\n" + "="*70)
        print("🖥️  SERVER: Agent completed successfully")
        print("="*70)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()
        
        # Try to stop driver
        try:
            agent.stop_driver()
        except:
            pass
