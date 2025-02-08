"""
Test script to demonstrate the new feed system.
"""

import asyncio
import json
from datetime import datetime
from topic_generator import get_latest_topics

async def main():
    # Test getting topics from all feeds
    print("Getting topics from all feeds...")
    all_topics = await get_latest_topics(limit=20)
    print(f"Found {len(all_topics)} topics\n")
    
    # Print topics in a readable format
    for topic in all_topics:
        print(f"Title: {topic['name']}")
        print(f"Provider: {topic['provider']}")
        print(f"Category: {topic['category']}")
        print(f"Published: {topic['date_published']}")
        print(f"URL: {topic['url']}")
        print("Description:")
        print(topic['description'][:200] + "..." if len(topic['description']) > 200 else topic['description'])
        print("-" * 80 + "\n")
    
    # Test getting topics by category
    print("\nGetting topics from vulnerability sources...")
    vuln_topics = await get_latest_topics(
        categories=['vulnerability_sources'],
        limit=5
    )
    print(f"Found {len(vuln_topics)} vulnerability topics")
    
    # Test getting topics from specific feeds
    print("\nGetting topics from specific feeds...")
    specific_topics = await get_latest_topics(
        feed_names=['The Hacker News', 'CISA Alerts'],
        limit=5
    )
    print(f"Found {len(specific_topics)} topics from specified feeds")

if __name__ == "__main__":
    asyncio.run(main()) 