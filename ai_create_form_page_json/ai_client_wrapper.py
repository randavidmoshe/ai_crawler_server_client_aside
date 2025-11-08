"""
AI Client Wrapper
Wrapper for AI API (Claude, GPT, etc.) to generate form mappings
"""

import json
import os
import time
from typing import Dict, Optional


class AIClientWrapper:
    """
    Wrapper for AI API client
    Supports Claude (Anthropic) and OpenAI GPT
    """
    
    def __init__(self, api_key: str = None, provider: str = "claude", model: str = None):
        """
        Args:
            api_key: API key for the AI service
            provider: "claude" or "openai"
            model: Model name (e.g., "claude-3-opus-20240229" or "gpt-4")
        """
        self.provider = provider.lower()
        self.api_key = api_key or self._get_api_key_from_env()
        
        if self.provider == "claude":
            self.model = model or "claude-sonnet-4-20250514"
            self._init_claude()
        elif self.provider == "openai":
            self.model = model or "gpt-4-turbo-preview"
            self._init_openai()
        else:
            raise ValueError(f"Unsupported provider: {provider}")
    
    def _get_api_key_from_env(self) -> str:
        """Get API key from environment variables"""
        if self.provider == "claude":
            return os.getenv("ANTHROPIC_API_KEY", "")
        elif self.provider == "openai":
            return os.getenv("OPENAI_API_KEY", "")
        return ""
    
    def _init_claude(self):
        """Initialize Claude (Anthropic) client"""
        try:
            import anthropic
            self.client = anthropic.Anthropic(api_key=self.api_key)
        except ImportError:
            raise ImportError("Please install anthropic: pip install anthropic")
    
    def _init_openai(self):
        """Initialize OpenAI client"""
        try:
            import openai
            openai.api_key = self.api_key
            self.client = openai
        except ImportError:
            raise ImportError("Please install openai: pip install openai")
    
    def generate(self, prompt: str, max_tokens: int = 8000, max_retries: int = 5) -> str:
        """
        Generate response from AI with retry logic
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens in response
            max_retries: Maximum number of retry attempts (default 5)
            
        Returns:
            AI response text
            
        Raises:
            Exception: After all retries exhausted
        """
        for attempt in range(max_retries):
            try:
                if self.provider == "claude":
                    return self._generate_claude(prompt, max_tokens)
                elif self.provider == "openai":
                    return self._generate_openai(prompt, max_tokens)
                    
            except Exception as e:
                error_str = str(e)
                
                # Check if this is a retryable error
                is_retryable = any([
                    "overloaded" in error_str.lower(),
                    "rate" in error_str.lower(),
                    "timeout" in error_str.lower(),
                    "529" in error_str,  # Overloaded
                    "503" in error_str,  # Service unavailable
                    "500" in error_str,  # Internal server error
                ])
                
                if not is_retryable or attempt == max_retries - 1:
                    # Not retryable or final attempt - raise
                    print(f"❌ AI API error (attempt {attempt + 1}/{max_retries}): {error_str}")
                    raise
                
                # Calculate exponential backoff delay
                delay = min(2 ** attempt, 60)  # Cap at 60 seconds
                print(f"⚠️  AI API error (attempt {attempt + 1}/{max_retries}): {error_str}")
                print(f"⏳ Retrying in {delay} seconds...")
                time.sleep(delay)
        
        # Should never reach here, but just in case
        raise Exception(f"Failed after {max_retries} retries")
    
    def _generate_claude(self, prompt: str, max_tokens: int) -> str:
        """Generate response from Claude"""
        try:
            message = self.client.messages.create(
                model=self.model,
                max_tokens=max_tokens,
                messages=[
                    {
                        "role": "user",
                        "content": prompt
                    }
                ]
            )
            
            return message.content[0].text
            
        except Exception as e:
            print(f"Error calling Claude API: {str(e)}")
            raise
    
    def _generate_openai(self, prompt: str, max_tokens: int) -> str:
        """Generate response from OpenAI"""
        try:
            response = self.client.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing HTML forms and creating structured JSON mappings for automated form filling."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                temperature=0.1
            )
            
            return response.choices[0].message.content
            
        except Exception as e:
            print(f"Error calling OpenAI API: {str(e)}")
            raise
    
    def generate_streaming(self, prompt: str, max_tokens: int = 8000):
        """
        Generate response with streaming (for real-time display)
        
        Args:
            prompt: Input prompt
            max_tokens: Maximum tokens in response
            
        Yields:
            Chunks of AI response
        """
        if self.provider == "claude":
            yield from self._generate_claude_streaming(prompt, max_tokens)
        elif self.provider == "openai":
            yield from self._generate_openai_streaming(prompt, max_tokens)
    
    def _generate_claude_streaming(self, prompt: str, max_tokens: int):
        """Generate streaming response from Claude"""
        try:
            with self.client.messages.stream(
                model=self.model,
                max_tokens=max_tokens,
                messages=[{"role": "user", "content": prompt}]
            ) as stream:
                for text in stream.text_stream:
                    yield text
        except Exception as e:
            print(f"Error in Claude streaming: {str(e)}")
            raise
    
    def _generate_openai_streaming(self, prompt: str, max_tokens: int):
        """Generate streaming response from OpenAI"""
        try:
            response = self.client.ChatCompletion.create(
                model=self.model,
                messages=[
                    {
                        "role": "system",
                        "content": "You are an expert at analyzing HTML forms."
                    },
                    {
                        "role": "user",
                        "content": prompt
                    }
                ],
                max_tokens=max_tokens,
                stream=True
            )
            
            for chunk in response:
                if chunk.choices[0].delta.get("content"):
                    yield chunk.choices[0].delta.content
                    
        except Exception as e:
            print(f"Error in OpenAI streaming: {str(e)}")
            raise


class MockAIClient:
    """
    Mock AI client for testing without API calls
    Returns pre-defined responses for testing
    """
    
    def __init__(self):
        self.call_count = 0
    
    def generate(self, prompt: str, max_tokens: int = 8000) -> str:
        """Generate mock response"""
        self.call_count += 1
        
        # Return a sample response
        if self.call_count == 1:
            # First iteration - map visible fields
            response = {
                "gui_fields": [
                    {
                        "name": "engagement_name",
                        "create_action": {
                            "create_type": "enter_text",
                            "action_description": "enter engagement name",
                            "update_css": "input[name='engagementName']",
                            "non_editable_condition": {},
                            "update_mandatory": True,
                            "validate_non_editable": False,
                            "webdriver_sleep_before_action": "0.5"
                        },
                        "update_fields_assignment": {
                            "type": "assign_random_text",
                            "size": "50"
                        },
                        "verification_fields_assignment": {},
                        "verification": {},
                        "update_api_fields_assignment": {},
                        "update_action": {
                            "webdriver_sleep_before_action": ""
                        },
                        "api_name": ""
                    }
                ],
                "mapping_complete": False,
                "interaction_request": {
                    "locator": "//div[@id='tab_Details']",
                    "locator_type": "xpath",
                    "action_type": "click_button",
                    "description": "Click Details tab to reveal more fields",
                    "selenium_actions": [
                        {
                            "action": "wait_for_clickable",
                            "locator": "//div[@id='tab_Details']",
                            "locator_type": "xpath",
                            "timeout": 10
                        },
                        {
                            "action": "click",
                            "locator": "//div[@id='tab_Details']",
                            "locator_type": "xpath"
                        },
                        {
                            "action": "sleep",
                            "duration": 1
                        }
                    ]
                },
                "reasoning": "Mapped the engagement name field and identified a Details tab that likely contains more fields."
            }
        else:
            # Subsequent iterations - complete mapping
            response = {
                "gui_fields": [
                    # Previous fields would be included here
                ],
                "mapping_complete": True,
                "reasoning": "All fields have been mapped and all tabs explored."
            }
        
        return json.dumps(response, indent=2)


# Test function
def test_ai_client():
    """Test the AI client wrapper"""
    
    # Test with mock client
    print("Testing with mock client...")
    mock_client = MockAIClient()
    
    prompt = "Test prompt"
    response = mock_client.generate(prompt)
    print("Response:", response[:200], "...")
    
    # Test with real Claude API (if API key available)
    if os.getenv("ANTHROPIC_API_KEY"):
        print("\nTesting with real Claude API...")
        client = AIClientWrapper(provider="claude")
        
        test_prompt = "Analyze this form and list the field types: <input name='test' />"
        response = client.generate(test_prompt, max_tokens=500)
        print("Response:", response[:200], "...")


if __name__ == "__main__":
    test_ai_client()
