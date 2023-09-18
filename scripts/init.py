import os
import requests
import datetime
from datetime import datetime
from generate_topics import generate_topics
from supabase import create_client, Client
from source_fetcher import gather_sources
from content_optimization import create_factsheet
from post_synthesis import post_synthesis
from wp_post import create_wordpress_post, add_tag_to_wordpress
from image_fetcher import test_image_upload
import asyncio
import httpx
from cisa import get_cisa_exploits
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Supabase configuration
supabase_url: str = os.getenv('SUPABASE_ENDPOINT')
supabase_key: str = os.getenv('SUPABASE_KEY')
# Initialize Supabase
supabase: Client = create_client(supabase_url = supabase_url, supabase_key = supabase_key)

wp_username = os.getenv('WP_ADMIN_USERNAME')
wp_password = os.getenv('WP_ADMIN_PASSWORD')

amount_of_topics = 1
MIN_SOURCES = 3
exploit_fetcher_activated = False
debug = True
synthesize_factsheets = True

# Access your API keys and token
wp_username = os.getenv('WP_ADMIN_USERNAME')
wp_password = os.getenv('WP_ADMIN_PASSWORD')
wp_token = os.getenv('WP_TOKEN')  # Get the token from environment variables

# Get the JWT token for WordPress
def get_jwt_token(username, password):

    if wp_token:
        print("Using existing token")
        return wp_token
    
    token_endpoint = "http://cybernow.info/wp-json/jwt-auth/v1/token"
    payload = {
        'username': username,
        'password': password
    }
    response = requests.post(token_endpoint, data=payload)
    if response.status_code == 200:
        token = response.json().get('token')  # Get token directly from JSON response
        print(f"Received token: {token}")
        return token
    else:
        print(f"Failed to get JWT token: {response.text}")
        return None

async def delete_topic(topic_id):
    # Delete all related sources
    response = supabase.table("sources").delete().eq("topic_id", topic_id).execute()
    if response.error:
        print(f"Failed to delete related sources: {response.error}")
        return
    # Delete the topic
    response = supabase.table("topics").delete().eq("id", topic_id).execute()
    if response.error:
        print(f"Failed to delete topic: {response.error}")
        return
    print(f"Successfully deleted topic with ID {topic_id} and all related sources.")

def post_the_most_recent_topic(token):
    # Get the most recent topic
    response = supabase.table("topics").select("*").execute()
    topic = response.data[0]
    # Post the most recent topic
    post_info = post_synthesis(token, topic)
    # Upload post info to wordpress if post_info['complete_with_images'] is not None and post_info['complete_with_images'] == True:
    if post_info['complete_with_images'] == True:
        create_wordpress_post(post_info, datetime.now() + datetime.timedelta(days=1))
    else:
        print("Uploaded to Supabase but not to WordPress because the WP database would not allow images to be uploaded")

def add_Authentication_tag(token, tag):
    add_tag_to_wordpress(token, tag)

async def main():
    token = get_jwt_token(wp_username, wp_password)
    
    if debug:
        print("Debug mode enabled")
        #add_Authentication_tag(token, "2FA")
        test_image_upload(token)
        return
    
    # Upload new cisa exploits
    result = await get_cisa_exploits()
    if result == False:
        print("Failed to get CISA exploits")
    else:
        print("Successfully got CISA exploits")
    
    # Generate topics
    try:
        generated_topics = generate_topics(supabase, amount_of_topics)
        print(f"Generated {len(generated_topics)} new topics")
        # Iterate through each recently generated topic and gather sources and factsheets
        for topic in generated_topics:
            print(f"Processing topic: {topic['name']}")
            
            # Gather Sources
            gather_sources(supabase, topic, MIN_SOURCES, False)
            print("Sources gathered")

            # Generate Fact Sheets
            create_factsheet(topic)
            print("Factsheet created")
            
            # Generate News
            post_info = post_synthesis(token, topic)
            print(f"Post info: {post_info}")
            
            create_wordpress_post(token, post_info, datetime.now())

            print("Not uploaded to WP because its database would not allow images to be uploaded")
    except Exception as e:
        print(f"Failed to process new topics: {e}")
    
    
    
    print("Program Complete.")

if __name__ == "__main__":
    asyncio.run(main())
