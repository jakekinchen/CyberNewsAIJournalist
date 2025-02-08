import os
import pytest
from dotenv import load_dotenv
from gpt_utils import query_gpt
from openai import OpenAI, AuthenticationError, APIError

# Load environment variables
load_dotenv()

def test_query_gpt_basic():
    """Test basic functionality of query_gpt."""
    # Test parameters
    user_prompt = "What is 2+2?"
    system_prompt = "You are a helpful math tutor. Give direct, concise answers."
    
    # Call the function
    response = query_gpt(user_prompt, system_prompt)
    
    # Basic assertions
    assert response is not None
    assert isinstance(response, str)
    assert len(response) > 0
    assert "4" in response.lower()  # The response should contain "4" since 2+2=4

def test_query_gpt_system_behavior():
    """Test if the system prompt effectively controls the response behavior."""
    user_prompt = "Tell me about cybersecurity."
    system_prompt = "You are a cybersecurity expert. Limit your response to exactly one sentence."
    
    # Call the function
    response = query_gpt(user_prompt, system_prompt)
    
    # Verify it's a single sentence
    assert response is not None
    assert isinstance(response, str)
    assert len(response.split('.')) <= 2  # Account for possible abbreviations like "U.S."

def test_query_gpt_error_handling():
    """Test various error cases for query_gpt."""
    # Test empty prompts
    with pytest.raises(ValueError, match="cannot be empty or None"):
        query_gpt("", "test system prompt")
    
    with pytest.raises(ValueError, match="cannot be empty or None"):
        query_gpt("test user prompt", "")
    
    # Test None values
    with pytest.raises(ValueError, match="cannot be empty or None"):
        query_gpt(None, "test system prompt")
    
    with pytest.raises(ValueError, match="cannot be empty or None"):
        query_gpt("test user prompt", None)
    
    # Test API errors
    original_api_key = os.getenv('OPENAI_API_KEY')
    try:
        os.environ['OPENAI_API_KEY'] = 'invalid_key'
        with pytest.raises(AuthenticationError):
            query_gpt("test prompt", "test system prompt")
    finally:
        if original_api_key:
            os.environ['OPENAI_API_KEY'] = original_api_key
        else:
            del os.environ['OPENAI_API_KEY']

if __name__ == "__main__":
    # Run the tests
    print("Running query_gpt tests...")
    
    print("\nTesting basic functionality...")
    test_query_gpt_basic()
    print("✓ Basic functionality test passed")
    
    print("\nTesting system behavior...")
    test_query_gpt_system_behavior()
    print("✓ System behavior test passed")
    
    print("\nTesting error handling...")
    try:
        test_query_gpt_error_handling()
        print("✓ Error handling test passed")
    except Exception as e:
        print(f"✗ Error handling test failed: {e}")
    
    print("\nAll tests completed!") 