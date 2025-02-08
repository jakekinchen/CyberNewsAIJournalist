import os
from dotenv import load_dotenv
from supabase import create_client

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_URL')
supabase_service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not supabase_url or not supabase_service_role_key:
    raise ValueError("Missing required environment variables: SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY")

print("Supabase URL:", supabase_url)
print("Supabase Service Role Key (first 10 chars):", supabase_service_role_key[:10] if supabase_service_role_key else "Not found")

try:
    # Create client with service role key
    supabase = create_client(supabase_url, supabase_service_role_key)
    
    # Try to fetch from a table
    response = supabase.table("topics").select("*").limit(1).execute()
    print("\nSample topic data:")
    if response.data:
        # Print the keys of the first record to see the table structure
        print("Table columns:", list(response.data[0].keys()))
        print("\nSample record:", response.data[0])
    else:
        print("No topics found in the table")
except Exception as e:
    print("Failed to connect to Supabase:", str(e)) 