import os
import httpx
import datetime
from datetime import datetime, timedelta
from generate_topics import generate_topics
from supabase_utils import supabase, insert_post_info_into_supabase, delete_topic
from utils import inspect_all_methods
from source_fetcher import gather_sources, create_factsheets_for_sources
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

# Go through every post in the posts table in Supabase and if there is a slug, then concatenate the slug with the URL https://cybernow.info/ and update the post field 'link' with the new URL
# This is a one time script to update the links in the posts table
def update_links():
    try:
        posts = supabase.table('posts').select('id, slug, link').execute()
        posts = posts.data
        
        # Filter out posts without slugs or with already correct links
        posts_to_update = [
            post for post in posts 
            if post['slug'] and post.get('link') != f"https://cybernow.info/{post['slug']}/"
        ]

        if not posts_to_update:
            logging.info("No posts need link updates.")
            return
        
        # Prepare data for bulk upsert
        bulk_data = [
            {'id': post['id'], 'link': f"https://cybernow.info/{post['slug']}/"} 
            for post in posts_to_update
        ]

        # Perform the bulk upsert
        for data in bulk_data:
            supabase.table('posts').update(data).eq('id', data['id']).execute()

        logging.info(f"Updated links for {len(bulk_data)} posts.")

    except Exception as e:
        logging.error(f"Failed to update links: {e}")



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

    if token is None:
        print("Failed to get token")
        return
    
    if debug:
        print("Debug mode enabled")
        #await test_scraping_site()
        #inspect_all_methods(['load_dotenv', 'create_client'])
        #update_links()
        #test_inject_images_into_post_info()
        test_seo_and_readability_optimization()
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
