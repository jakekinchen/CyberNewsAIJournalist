import os
import httpx
from datetime import datetime, timedelta
import utils
from wp_utils import fetch_categories, fetch_tags, update_posts_with_new_html, create_wordpress_post, auth_token
from gpt_utils import list_available_models as list_models, query_dalle, generate_wp_field_completion_function
from generate_topics import generate_topics, filter_new_topics
from supabase_utils import supabase, store_post_info, delete_topic, get_a_source_from_supabase
from utils import inspect_all_methods
from source_fetcher import gather_sources, create_factsheets_for_sources, create_factsheet, search_related_sources
from post_synthesis import post_synthesis, post_completion
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
MIN_SOURCES = 3
exploit_fetcher_activated = False
debug = False
synthesize_factsheets = True

def test_update_posts_with_new_html():
    # Second argument is the starting date (the 1st of november 2023)
    update_posts_with_new_html(auth_token, datetime(2023, 11, 1))

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

async def process_topic(topic):
    """Process a single topic."""
    try:
        response = supabase.table("topics").insert([{
            'id': topic['id'],
            'name': topic['name'],
            'description': topic['description'],
            'date_accessed': topic['date_accessed'],
            'date_published': topic['date_published'],
            'provider': topic['provider'],
            'url': topic['url']
        }]).execute()
        print(f"Successfully created topic: {topic['name']} (ID: {topic['id']})")
    except Exception as e:
        print(f"Failed to create topic in Supabase: {e}")
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

async def main(amount_of_topics=1):
    """Main function to generate and process topics."""
    # Get existing topics first
    print("Fetching existing topics from database...")
    try:
        existing_topics = supabase.table("topics").select("*").execute()
        print(f"Found {len(existing_topics.data)} existing topics")
    except Exception as e:
        print(f"Failed to fetch existing topics: {e}")
        return

    # Get the maximum ID from Supabase
    try:
        max_id_result = supabase.table('topics').select('id').order('id', desc=True).limit(1).execute()
        max_id = max_id_result.data[0]['id'] if max_id_result.data else 0
        print(f"Current maximum topic ID: {max_id}")
    except Exception as e:
        print(f"Failed to get maximum topic ID: {e}")
        return

    # Generate new topics
    topics = await generate_topics(supabase, amount_of_topics)
    if not topics:
        print("Failed to generate topics")
        return

    # Filter out existing topics
    filtered_topics = await filter_new_topics(topics, existing_topics.data)
    print(f"Found {len(filtered_topics)} new topics")

    # Assign IDs to new topics
    for i, topic in enumerate(filtered_topics):
        topic['id'] = max_id + i + 1

    # Limit to requested amount
    topics_to_process = filtered_topics[:amount_of_topics]
    print(f"Using {len(topics_to_process)} topics after limiting to requested amount")

    # Process each topic
    for topic in topics_to_process:
        # First create the topic
        await process_topic(topic)
        
        print(f"\nGathering sources for topic: {topic['name']} (ID: {topic['id']})...")
        # Then gather sources
        sources = await gather_sources(supabase, topic, MIN_SOURCES)
        if not sources:
            print(f"No sources found for topic {topic['id']}")
            continue
        print(f"Found {len(sources)} sources for topic {topic['id']}")
        
        if len(sources) < MIN_SOURCES:
            print(f"Looking for additional sources for topic: {topic['name']}")
            additional_sources = search_related_sources(topic['name'])
            if additional_sources:
                for source in additional_sources:
                    if len(sources) >= MIN_SOURCES:
                        break
                    try:
                        content = await scrape_content(source['url'])
                        if content:
                            source_record = {
                                'topic_id': topic['id'],
                                'url': source['url'],
                                'content': content,
                                'date_accessed': datetime.now().isoformat(),
                                'external_source': True
                            }
                            response = supabase.table('sources').insert(source_record).execute()
                            if response.data:
                                sources.extend(response.data)
                                print(f"Added additional source: {source['url']}")
                    except Exception as e:
                        print(f"Error adding additional source {source['url']}: {e}")
                        continue
        
        if len(sources) < MIN_SOURCES:
            print(f"Warning: Could only gather {len(sources)} sources for topic {topic['id']}, wanted {MIN_SOURCES}")
        
        if synthesize_factsheets:
            print(f"\nCreating factsheets for topic: {topic['name']} (ID: {topic['id']})...")
            # Create factsheets from sources
            factsheet, external_source_info = await create_factsheets_for_sources(topic)
            if factsheet:
                print(f"Successfully created factsheet for topic {topic['id']}")
                
                # Create and publish post
                print(f"\nCreating post for topic: {topic['name']} (ID: {topic['id']})...")
                try:
                    # Fetch categories and tags
                    categories = fetch_categories()
                    tags = fetch_tags()
                    
                    # Generate post content
                    post_info = post_synthesis(topic, categories, tags)
                    
                    # Add topic_id to post_info
                    post_info['topic_id'] = topic['id']
                    
                    # Store post info in Supabase
                    try:
                        store_post_info(supabase, post_info)
                        print("Successfully stored post info in Supabase")
                    except Exception as e:
                        print(f"Failed to store post info in Supabase: {e}")
                except Exception as e:
                    print(f"Error creating post: {e}")
                    print(f"Error details: ", e.__class__.__name__)
            else:
                print(f"Failed to create factsheet for topic {topic['id']}")

if __name__ == "__main__":
    asyncio.run(main())

