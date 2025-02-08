from openai import OpenAI
from dotenv import load_dotenv
import os
import asyncio
import time
from source_fetcher import create_factsheet

# Load environment variables
load_dotenv()

model = os.getenv('SUMMARIZATION_MODEL')

def test_query(client):
    print("\nTesting API Query with o3-mini-2025-01-31:")
    print("----------------------------------------")
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a helpful assistant."},
                {"role": "user", "content": "What's the best way to test if an API is working?"}
            ]
        )
        print("\nResponse:")
        print(response.choices[0].message.content)
    except Exception as e:
        print(f"Error making test query: {e}")

async def test_create_factsheet():
    print("\nTesting create_factsheet method:")
    print("------------------------------")
    
    # Create a test source with explicit model
    test_source = {
        'id': 1,
        'topic_id': 123,
        'content': """As many as 768 vulnerabilities with designated CVE identifiers were reported as exploited in the wild in 2024, up from 639 CVEs in 2023, registering a 20% increase year-over-year. VulnCheck said 23.6% of known exploited vulnerabilities (KEV) were known to be weaponized either on or before the day their CVEs were publicly disclosed.""",
        'factsheet': None,
        'model': model  # Explicitly set the model
    }
    
    try:
        start_time = time.time()
        # Create a direct query to test
        client = OpenAI()
        system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail."
        user_prompt = f"Create a factsheet summarizing the key points from this text about CVE Exploits in 2024: {test_source['content']}"
        
        print("\nMaking direct API call...")
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        
        factsheet = response.choices[0].message.content
        end_time = time.time()
        
        print(f"\nTime taken: {end_time - start_time:.2f} seconds")
        
        if factsheet:
            print("\nFactsheet created successfully:")
            print(factsheet)
        else:
            print("\nNo factsheet was created (returned None)")
            
    except Exception as e:
        print(f"\nError creating factsheet: {e}")

async def main():
    # Initialize the OpenAI client
    client = OpenAI()
    
    try:
        # Get the list of models
        models = client.models.list()
        
        # Print models in a formatted way
        print("\nAvailable OpenAI Models:")
        print("----------------------")
        for model in models.data:
            print(f"- {model.id}")
            
        # Test the API with a query
        test_query(client)
        
        # Test create_factsheet
        await test_create_factsheet()
            
    except Exception as e:
        print(f"Error listing models: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 