import os
import httpx
import datetime
import utils
from wp_utils import fetch_categories, fetch_tags
from gpt_utils import list_models, query_dalle
from datetime import datetime, timedelta
from generate_topics import generate_topics
from supabase_utils import supabase, insert_post_info_into_supabase, delete_topic, get_a_source_from_supabase
from utils import inspect_all_methods
from source_fetcher import gather_sources, create_factsheets_for_sources, create_factsheet
from post_synthesis import post_synthesis
from wp_utils import create_wordpress_post, token
from content_optimization import test_seo_and_readability_optimization
from extract_text import test_scraping_site
import asyncio
from cisa import get_cisa_exploits
# Load environment variables
from dotenv import load_dotenv
import logging
import time
load_dotenv()

amount_of_topics = 1
MIN_SOURCES = 2
exploit_fetcher_activated = False
debug = False
synthesize_factsheets = False

def test_query_dalle():
    prompt = "A digital chessboard with a shadowy figure holding a cloak of invisibility advancing unseen pieces forward."
    response = query_dalle(prompt)
    print(response)

async def test_create_factsheet():
    # Get source content from Supabase
    source = get_a_source_from_supabase(1678)
    # Create factsheet
    #print(f"Source: {source}")
    factsheet = await create_factsheet(source, 'The Millenium Rat')
    print(f"Factsheet: {factsheet}")

async def process_topic(topic, token):
    # Fetch Categories and Tags
    categories = fetch_categories(token)
    tags = fetch_tags(token)
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
        topic['factsheet'], topic['external_source_info'] = await create_factsheets_for_sources(topic)
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
        post_info = post_synthesis(token, topic, categories, tags)
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
        create_wordpress_post(token, post_info)
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

    if token is None:
        print("Failed to get token")
        return
    

    if debug:
        print("Debug mode enabled")
        #test_query_dalle()
        #await test_create_factsheet()
        #list_models()
        await test_scraping_site("https://www.nytimes.com/2023/11/09/us/politics/river-to-the-sea-israel-gaza-palestinians.html")
        #inspect_all_methods(['load_dotenv', 'create_client'])
        #update_links()
        #test_inject_images_into_post_info()
        #delete_supabase_images_not_in_wp()
        
        #test_seo_and_readability_optimization()
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
