"""
Test script to run through the entire process from topic gathering to WordPress posting.
"""

import asyncio
import logging
from supabase_utils import supabase
from generate_topics import generate_topics
from source_fetcher import gather_sources
from post_synthesis import post_synthesis
from wp_utils import create_wordpress_post, fetch_categories, fetch_tags, auth_token

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

async def main():
    try:
        # Step 1: Generate topics
        logger.info("Step 1: Generating topics...")
        topics = await generate_topics(supabase, amount_of_topics=1)
        if not topics:
            logger.error("No topics generated. Exiting.")
            return
            
        topic = topics[0]
        logger.info(f"Selected topic: {topic['name']}")
        
        # Step 2: Gather sources
        logger.info("\nStep 2: Gathering sources...")
        sources = await gather_sources(supabase, topic, MIN_SOURCES=3)
        if not sources:
            logger.error("No sources gathered. Exiting.")
            return
        logger.info(f"Gathered {len(sources)} sources")
        
        # Step 3: Fetch WordPress categories and tags
        logger.info("\nStep 3: Fetching WordPress categories and tags...")
        categories = fetch_categories()
        tags = fetch_tags()
        logger.info(f"Fetched {len(categories)} categories and {len(tags)} tags")
        
        # Step 4: Generate post content
        logger.info("\nStep 4: Generating post content...")
        post_info = post_synthesis(topic, categories, tags)
        if not post_info:
            logger.error("Failed to generate post content. Exiting.")
            return
        logger.info("Successfully generated post content")
        
        # Step 5: Create WordPress post
        logger.info("\nStep 5: Creating WordPress post...")
        wp_response = create_wordpress_post(post_info, auth_token)
        
        if wp_response and wp_response.get('id'):
            logger.info(f"Successfully created WordPress post with ID: {wp_response['id']}")
            logger.info(f"Post URL: {wp_response.get('link', 'URL not available')}")
        else:
            logger.error("Failed to create WordPress post")
            
    except Exception as e:
        logger.error(f"Error in main process: {e}")

if __name__ == "__main__":
    asyncio.run(main()) 