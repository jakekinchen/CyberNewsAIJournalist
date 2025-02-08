import asyncio
from supabase_utils import get_topics_without_posts, store_post_info
from wp_utils import fetch_categories, fetch_tags
from post_synthesis import post_synthesis
from source_fetcher import gather_sources
from scripts.supabase_utils import supabase

async def process_unpublished_topics():
    """Process all topics that don't have associated posts."""
    # Get topics without posts
    topics = get_topics_without_posts()
    print(f"\nFound {len(topics)} topics without posts")
    
    if not topics:
        print("No topics to process")
        return
        
    # Process each topic
    for topic in topics:
        print(f"\nProcessing topic: {topic['name']} (ID: {topic['id']})...")
        
        try:
            # Gather sources if needed
            sources = await gather_sources(supabase, topic, MIN_SOURCES=3)
            if not sources:
                print(f"No sources found for topic {topic['id']}, skipping...")
                continue
            print(f"Gathered {len(sources)} sources")
            
            # Fetch categories and tags
            categories = fetch_categories()
            tags = fetch_tags()
            
            # Generate post content
            post_info = post_synthesis(topic, categories, tags)
            if not post_info:
                print(f"Failed to generate post content for topic {topic['id']}, skipping...")
                continue
                
            # Add topic_id to post_info
            post_info['topic_id'] = topic['id']
            
            # Store post info in Supabase
            try:
                store_post_info(supabase, post_info)
                print(f"Successfully created post for topic {topic['id']}")
            except Exception as e:
                print(f"Failed to store post info for topic {topic['id']}: {e}")
                
        except Exception as e:
            print(f"Error processing topic {topic['id']}: {e}")
            continue

if __name__ == "__main__":
    asyncio.run(process_unpublished_topics()) 