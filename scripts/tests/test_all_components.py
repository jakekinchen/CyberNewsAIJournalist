import os
import asyncio
import time
from datetime import datetime
from dotenv import load_dotenv
from wp_utils import fetch_categories, fetch_tags, auth_token
from gpt_utils import list_available_models, query_dalle
from generate_topics import generate_topics
from supabase_utils import supabase, get_a_source_from_supabase
from source_fetcher import gather_sources, create_factsheets_for_sources, create_factsheet
from post_synthesis import post_synthesis, post_completion
from extract_text import test_scraping_site
from cisa import get_cisa_exploits

# Load environment variables
load_dotenv()

async def test_wordpress_utils():
    print("\n=== Testing WordPress Utils ===")
    print("Testing auth token...")
    if auth_token:
        print("✓ Auth token obtained successfully")
    else:
        print("✗ Failed to get auth token")

    print("\nFetching categories...")
    categories = fetch_categories()
    if categories:
        print(f"✓ Successfully fetched {len(categories)} categories")
    else:
        print("✗ Failed to fetch categories")

    print("\nFetching tags...")
    tags = fetch_tags()
    if tags:
        print(f"✓ Successfully fetched {len(tags)} tags")
    else:
        print("✗ Failed to fetch tags")

async def test_gpt_utils():
    print("\n=== Testing GPT Utils ===")
    print("Testing model listing...")
    models = list_available_models()
    if models:
        print(f"✓ Successfully listed {len(models)} models")
    else:
        print("✗ Failed to list models")

    print("\nTesting DALL-E...")
    try:
        prompt = "A simple test image of a blue circle"
        response = query_dalle(prompt)
        if response:
            print("✓ Successfully generated DALL-E image")
        else:
            print("✗ Failed to generate DALL-E image")
    except Exception as e:
        print(f"✗ DALL-E test failed: {e}")

async def test_topic_generation():
    print("\n=== Testing Topic Generation ===")
    topics = generate_topics(supabase, 1)
    if topics:
        print(f"✓ Successfully generated {len(topics)} topic(s)")
        return topics[0]
    else:
        print("✗ Failed to generate topics")
        return None

async def test_source_fetching(topic):
    print("\n=== Testing Source Fetching ===")
    if not topic:
        print("✗ Cannot test source fetching without a topic")
        return None
    
    try:
        sources = await gather_sources(supabase, topic, MIN_SOURCES=2, overload=False)
        if sources:
            print(f"✓ Successfully gathered {len(sources)} sources")
            return sources
        else:
            print("✗ Failed to gather sources")
            return None
    except Exception as e:
        print(f"✗ Source fetching failed: {e}")
        return None

async def test_factsheet_creation():
    print("\n=== Testing Factsheet Creation ===")
    
    # Test case 1: Create a test source with a unique URL
    test_source = {
        'id': 999999,  # Using a high ID to avoid conflicts
        'topic_id': 123,
        'content': """As many as 768 vulnerabilities with designated CVE identifiers were reported as exploited in the wild in 2024, up from 639 CVEs in 2023, registering a 20% increase year-over-year. VulnCheck said 23.6% of known exploited vulnerabilities (KEV) were known to be weaponized either on or before the day their CVEs were publicly disclosed.""",
        'url': 'https://test-unique-url.com/article1',
        'factsheet': None
    }
    
    print("\nTest 1: Creating factsheet for new source...")
    try:
        factsheet1 = await create_factsheet(test_source, 'Test Topic')
        if factsheet1:
            print("✓ Successfully created factsheet for new source")
            print(f"Factsheet content: {factsheet1[:200]}...")
        else:
            print("✗ Failed to create factsheet for new source")
    except Exception as e:
        print(f"✗ Factsheet creation failed: {e}")

    # Test case 2: Try to create factsheet for source with same URL
    print("\nTest 2: Attempting to create factsheet for source with same URL...")
    test_source_duplicate = {
        'id': 999998,  # Different ID
        'topic_id': 123,
        'content': test_source['content'],
        'url': test_source['url'],  # Same URL
        'factsheet': None
    }
    
    try:
        factsheet2 = await create_factsheet(test_source_duplicate, 'Test Topic')
        if factsheet2 is None:
            print("✓ Correctly skipped creating duplicate factsheet")
        else:
            print("✗ Unexpectedly created duplicate factsheet")
    except Exception as e:
        print(f"✗ Error during duplicate test: {e}")

    # Test case 3: Create factsheet for source with different URL
    print("\nTest 3: Creating factsheet for source with different URL...")
    test_source_different = {
        'id': 999997,
        'topic_id': 123,
        'content': test_source['content'],
        'url': 'https://test-unique-url.com/article2',  # Different URL
        'factsheet': None
    }
    
    try:
        factsheet3 = await create_factsheet(test_source_different, 'Test Topic')
        if factsheet3:
            print("✓ Successfully created factsheet for different URL")
            print(f"Factsheet content: {factsheet3[:200]}...")
        else:
            print("✗ Failed to create factsheet for different URL")
    except Exception as e:
        print(f"✗ Factsheet creation failed: {e}")

async def test_post_synthesis(topic):
    print("\n=== Testing Post Synthesis ===")
    if not topic:
        print("✗ Cannot test post synthesis without a topic")
        return
    
    try:
        categories = fetch_categories() or [{'id': 1, 'name': 'Uncategorized'}]
        tags = fetch_tags() or []
        post_info = post_synthesis(topic, categories, tags)
        if post_info:
            print("✓ Successfully synthesized post")
            print(f"Post title: {post_info.get('title', 'No title')}")
        else:
            print("✗ Failed to synthesize post")
    except Exception as e:
        print(f"✗ Post synthesis failed: {e}")

async def test_cisa_exploits():
    print("\n=== Testing CISA Exploits Fetching ===")
    try:
        start_time = time.time()
        result = await get_cisa_exploits()
        if result:
            print(f"✓ Successfully fetched CISA exploits in {time.time() - start_time:.2f} seconds")
        else:
            print("✗ Failed to fetch CISA exploits")
    except Exception as e:
        print(f"✗ CISA exploits fetching failed: {e}")

async def test_scraping():
    print("\n=== Testing Web Scraping ===")
    try:
        result = await test_scraping_site()
        if result:
            print("✓ Successfully tested web scraping")
        else:
            print("✗ Failed to test web scraping")
    except Exception as e:
        print(f"✗ Web scraping test failed: {e}")

async def main():
    print("Starting component tests...")
    total_start_time = time.time()

    # Test WordPress utils
    await test_wordpress_utils()

    # Test GPT utils
    await test_gpt_utils()

    # Test topic generation and dependent functions
    topic = await test_topic_generation()
    if topic:
        sources = await test_source_fetching(topic)
        await test_post_synthesis(topic)

    # Test factsheet creation
    await test_factsheet_creation()

    # Test CISA exploits fetching
    await test_cisa_exploits()

    # Test web scraping
    await test_scraping()

    total_time = time.time() - total_start_time
    print(f"\nAll tests completed in {total_time:.2f} seconds")

if __name__ == "__main__":
    asyncio.run(main()) 