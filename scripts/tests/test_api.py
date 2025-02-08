from dotenv import load_dotenv
import os
from gpt_utils import query_gpt

def test_api():
    load_dotenv()
    model = os.getenv('SUMMARIZATION_MODEL')
    print(f'Using model: {model}')
    
    try:
        response = query_gpt('How are you doing?', 'You are a friendly AI assistant.')
        print(f'Response: {response}')
    except Exception as e:
        print(f'Error: {e}')

if __name__ == "__main__":
    test_api() 