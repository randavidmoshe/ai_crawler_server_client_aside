# agent_discovery_extension.py
# Code to ADD to MultiFormsDiscoveryAgent class in agent_selenium.py

"""
INSTRUCTIONS:
Add this method to the MultiFormsDiscoveryAgent class in agent_selenium.py
Place it after the existing methods in that class (around line 1850+)

This is the ONLY change needed to agent_selenium.py
"""

def get_stable_dom(self, timeout: int = 10) -> Dict:
    """
    Wait for page content to stabilize, then return DOM
    All waiting happens locally on agent side to minimize network calls
    
    This ensures dynamic content (AJAX, React, Vue) has finished loading
    before returning the DOM to the orchestrator
    
    Args:
        timeout: Maximum seconds to wait for stability (default 10)
        
    Returns:
        Dict with success and html content:
        {
            "success": True,
            "html": "...",
            "stable": True,  # Whether DOM stabilized or timed out
            "wait_time": 3.5  # How long it waited
        }
    """
    try:
        import time
        start_time = time.time()
        
        # First wait for basic DOM ready
        self.wait_dom_ready()
        time.sleep(0.5)  # Small delay for initial rendering
        
        # Now wait for DOM to stop changing (AJAX/dynamic content)
        previous_dom = None
        stable_count = 0
        attempts = 0
        max_attempts = int(timeout / 0.5)  # Check every 0.5 seconds
        
        while attempts < max_attempts:
            current_dom = self.driver.page_source
            
            # Check if DOM is unchanged
            if current_dom == previous_dom:
                stable_count += 1
                # If stable for 3 consecutive checks (1.5 seconds), we're done
                if stable_count >= 3:
                    wait_time = time.time() - start_time
                    return {
                        "success": True,
                        "html": current_dom,
                        "stable": True,
                        "wait_time": round(wait_time, 2)
                    }
            else:
                # DOM changed, reset counter
                stable_count = 0
            
            previous_dom = current_dom
            time.sleep(0.5)
            attempts += 1
        
        # Timeout reached - return whatever we have
        wait_time = time.time() - start_time
        return {
            "success": True,
            "html": self.driver.page_source,
            "stable": False,  # Timed out, might not be fully stable
            "wait_time": round(wait_time, 2)
        }
        
    except Exception as e:
        clean_error = self._clean_error_message(e)
        return {
            "success": False,
            "error": clean_error,
            "html": "",
            "stable": False,
            "wait_time": 0
        }
