import os
import httpx
import datetime
from datetime import datetime, timedelta
from generate_topics import generate_topics
from supabase_utils import supabase
from utils import inspect_all_methods
from source_fetcher import gather_sources
from content_optimization import create_factsheets_for_sources
from post_synthesis import post_synthesis, insert_post_info_into_supabase
from wp_post import create_wordpress_post
from extract_text import test_scraping_site
import asyncio
from cisa import get_cisa_exploits
# Load environment variables
from dotenv import load_dotenv
import logging
import time
load_dotenv()

amount_of_topics = 2
MIN_SOURCES = 3
exploit_fetcher_activated = False
debug = False
synthesize_factsheets = False

# Access your API keys and token
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')
wp_token = os.getenv('WP_TOKEN')

# Get the JWT token for WordPress
def get_jwt_token(username, password):

    if wp_token:
        logging.info("Using existing token")
        return wp_token
    
    token_endpoint = "http://cybernow.info/wp-json/jwt-auth/v1/token"
    payload = {
        'username': username,
        'password': password
    }
    response = httpx.post(token_endpoint, data=payload)
    if response.status_code == 200:
        token = response.json().get('token')  # Get token directly from JSON response
        #logging.info(f"Received token: {token}")
        return token
    else:
        logging.info(f"Failed to get JWT token: {response.text}")
        raise Exception(f"Failed to get JWT token: {response.text}")

async def delete_topic(topic_id):
    # Delete the topic
    try:
        response = supabase.table("topics").delete().eq("id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete topic: {e}")
        return
    print(f"Successfully deleted topic with ID {topic_id} and all related sources.")

async def delete_supabase_post(topic_id):
    # topic_id is a foreign key in the supabase table posts
    # Delete the post
    try:
        response = supabase.table("posts").delete().eq("topic_id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete post: {e}")
        return
  
    print(f"Successfully deleted post with topic ID {topic_id}.")

async def process_topic(topic, token):
    # Gather Sources
    start_time = time.time()
    try:
        gather_sources(supabase, topic, MIN_SOURCES, False)
        print(f"Sources gathered in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Failed to gather sources: {e}")
        await delete_topic(topic['id'])
        return

    # Generate Fact Sheets
    start_time = time.time()
    try:
        topic['factsheet'], topic['external_source_info'] = create_factsheets_for_sources(topic)
        if topic['factsheet'] is None:
            print("Failed to create any factsheets")
            await delete_topic(topic['id'])
            return
        print(f"Factsheet created in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Failed to create factsheet: {e}")
        await delete_topic(topic['id'])
        return
    if topic['factsheet'] is None:
        print("Failed to create any factsheets")
        await delete_topic(topic['id'])
        return
    # Generate News
    start_time = time.time()
    try:
        post_info = post_synthesis(token, topic)
        if post_info is None:
            print("Failed to create post info")
            await delete_topic(topic['id'])
            return
        print(f"Post synthesized in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Failed to synthesize post: {e}")
        await delete_topic(topic['id'])
        return
    
    # Insert Post Info into Supabase
    start_time = time.time()
    try:
        insert_post_info_into_supabase(post_info)
        print(f"Post info inserted into Supabase in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Failed to insert post info into Supabase: {e}")
        await delete_topic(topic['id'])
        return
    
    # Create WordPress Post
    start_time = time.time()
    try:
        create_wordpress_post(token, post_info, datetime.now())
        print(f"Post created in {time.time() - start_time:.2f} seconds")
    except Exception as e:
        print(f"Failed to create post: {e}")
        await delete_topic(topic['id'])
        return

async def fetch_cisa_exploits():
    # Upload new cisa exploits
    start_time = time.time()
    result = await get_cisa_exploits()
    if result == False:
        print("Failed to get CISA exploits")
        return
    else:
        print(f"Got CISA exploits in {time.time() - start_time:.2f} seconds")

async def main():
    total_start_time = time.time()
    token = get_jwt_token(wp_username, wp_password)

    if token is None:
        print("Failed to get token")
        return
    
    if debug:
        print("Debug mode enabled")
        #await test_scraping_site()
        inspect_all_methods(['load_dotenv', 'create_client'])
        #await fetch_cisa_exploits()

        return
    
    await fetch_cisa_exploits()
    
    # Generate topics
    try:
        start_time = time.time()
        generated_topics = generate_topics(supabase, amount_of_topics)
        print(f"Generated {len(generated_topics)} new topics in {time.time() - start_time:.2f} seconds")
        for topic in generated_topics:
            print(f"Processing topic: {topic['name']}")
            await process_topic(topic, token)
    except Exception as e:
        print(f"Failed to process new articles: {e}")
    print(f"Total program took {time.time() - total_start_time:.2f} seconds")
    print("Program Complete.")

if __name__ == "__main__":
    asyncio.run(main())
