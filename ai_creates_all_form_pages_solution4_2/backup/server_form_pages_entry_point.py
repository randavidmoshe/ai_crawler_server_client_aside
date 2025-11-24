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
    START_URL = "https://opensource-demo.orangehrmlive.com/web/index.php/auth/login"

    USERNAME = "Admin"
    PASSWORD = "admin123"
    LOGGED_IN = False

    API_KEY = os.environ.get("ANTHROPIC_API_KEY")

    if API_KEY:
        print(f"[Server] ✅ API Key loaded")
    else:
        print("[Server] ❌ No API key - Server AI will not work")

    DISCOVERY_ONLY = True
    TARGET_FORMS = []
    MAX_PAGES = 50
    MAX_DEPTH = 20
    SLOW_MODE = True
    HEADLESS = False
    HIDDEN = False

    print("[Server] Instructing agent to start crawl...")
    print("="*70 + "\n")

    # ============================================================
    # CREATE SERVER AND AGENT
    # ============================================================
    
    try:
        # Create server
        server = Server(api_key=API_KEY)
        
        # Create agent
        agent = Agent()
        
        # Start driver on agent
        agent.start_driver(headless=HEADLESS, hidden=HIDDEN)
        
        # Run crawler - pass server to agent
        agent.run_crawler(
            start_url=START_URL,
            project_name=PROJECT_NAME,
            username=USERNAME,
            password=PASSWORD,
            logged_in=LOGGED_IN,
            target_form_pages=TARGET_FORMS,
            server=server,
            max_pages=MAX_PAGES,
            max_depth=MAX_DEPTH,
            discovery_only=DISCOVERY_ONLY,
            slow_mode=SLOW_MODE
        )
        
        # Stop driver
        agent.stop_driver()
        
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
