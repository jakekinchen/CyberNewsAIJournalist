import httpx
import xml.etree.ElementTree as ET
import json
import logging
from datetime import datetime, timedelta
from gpt_utils import query_gpt
from dotenv import load_dotenv
from typing import List, Dict, Any
from topic_similarity import is_topic_unique
from topic_generator import get_latest_topics
from inspect import isawaitable
from topic_evaluation import filter_topics_structured
from scripts.supabase_utils import supabase

# Load environment variables
load_dotenv()

def fetch_and_process_xml(url):
    response = httpx.get(url)
    data = response.text
    etree = ET.ElementTree(ET.fromstring(data))
    return etree.findall("./channel/item")

async def filter_new_topics(topics, existing_topics, use_structured_output: bool = True):
    """Filter out topics that already exist in the database based on URL."""
    try:
        if use_structured_output:
            try:
                # Use the new structured output approach
                filtered_topics = await filter_topics_structured(topics, supabase)
                if filtered_topics:
                    print(f"Successfully filtered topics using structured output approach")
                    return filtered_topics
                else:
                    print("Structured output filtering failed, falling back to traditional approach")
            except Exception as e:
                print(f"Error in structured output filtering: {e}")
                print("Falling back to traditional approach")
                
        # Traditional filtering approach (fallback)
        existing_urls = set()
        url_to_topic = {}
        for topic in existing_topics:
            url = topic.get('url')
            if not url:
                continue
            url = url.split('?')[0].rstrip('/')
            if 'CVE-2024-57609' in url:
                continue
            existing_urls.add(url)
            url_to_topic[url] = topic
            
        print(f"Found {len(existing_urls)} existing URLs")
        print("First 5 existing URLs:")
        for url in list(existing_urls)[:5]:
            topic = url_to_topic[url]
            print(f"  - {url} (ID={topic.get('id')}, Name={topic.get('name', 'Unknown')})")
        
        filtered_topics = []
        topics_list = topics if isinstance(topics, list) else await topics
        
        for topic in topics_list:
            url = topic.get('url')
            if not url:
                print(f"Skipping topic with empty URL")
                continue
                
            url = url.split('?')[0].rstrip('/')
            print(f"\nChecking URL: {url}")
            
            if url in existing_urls:
                matching_topic = url_to_topic.get(url)
                if matching_topic:
                    print(f"Found matching URL in database: {url}")
                    print(f"Existing topic: ID={matching_topic.get('id')}, Name={matching_topic.get('name', 'Unknown')}")
                else:
                    print(f"Found matching URL in database but no topic info: {url}")
                continue
                
            if any(pattern in url.lower() for pattern in [
                '/search/label/',
                '/search?',
                'page=',
                'category=',
                'tag=',
                'archive=',
                'author=',
                'feed=',
                'rss=',
                'index.html'
            ]):
                print(f"Skipping non-article URL: {url}")
                continue
                
            print(f"Adding new topic with URL: {url}")
            filtered_topics.append(topic)
            
        return filtered_topics
            
    except Exception as e:
        print(f"Error filtering topics: {e}")
        topics_count = len(topics_list) if topics_list is not None else 0
        existing_count = len(existing_topics) if existing_topics is not None else 0
        print(f"Topics count: {topics_count}")
        print(f"Existing topics count: {existing_count}")
        return []

def get_ordered_topics(topics, amount_of_topics):
    topics_list = [topic['name'] for topic in topics]
    user_prompt = f"""Order the following topics by relevance to cybersecurity and expected popularity...{topics_list}"""
    system_prompt = 'You are a data computer that formats data into JSON.'
    ordered_topics_json = query_gpt(user_prompt, system_prompt)

    if ordered_topics_json and ordered_topics_json.startswith('[') and ordered_topics_json.endswith(']'):
        return json.loads(ordered_topics_json)[:amount_of_topics]
    else:
        raise ValueError("The GPT-3 response is not in the expected JSON array format.")

async def generate_topics(supabase, amount_of_topics: int = 1, use_structured_output: bool = True) -> List[Dict[str, Any]]:
    """
    Generate topics from various feeds and filter out duplicates.
    
    Args:
        supabase: Supabase client instance
        amount_of_topics: Number of topics to generate
        use_structured_output: Whether to use the new structured output approach for topic evaluation
        
    Returns:
        List of unique topics
    """
    print("Starting topic generation...")
    
    try:
        # Get existing topics from database
        existing_topics = supabase.table("topics").select("*").execute()
        print(f"Found {len(existing_topics.data)} existing topics")
        
        # Get the maximum ID from Supabase
        max_id_result = supabase.table('topics').select('id').order('id', desc=True).limit(1).execute()
        max_id = max_id_result.data[0]['id'] if max_id_result.data else 0
        print(f"Current maximum topic ID: {max_id}")
        
        # Get topics from feeds
        # We'll get more than we need since some might be filtered out
        topics = await get_latest_topics(limit=amount_of_topics * 3, max_age_hours=48)
        if not topics:
            print("Failed to generate topics")
            return []
            
        print(f"Generated {len(topics)} potential topics")
        
        # Filter out existing topics using either the new or traditional approach
        filtered_topics = await filter_new_topics(topics, existing_topics.data, use_structured_output)
        
        # Assign IDs to new topics
        for i, topic in enumerate(filtered_topics):
            topic['id'] = max_id + i + 1
            
        # Limit to requested amount
        topics_to_process = filtered_topics[:amount_of_topics]
        print(f"Using {len(topics_to_process)} topics after limiting to requested amount")
        
        # If using structured output, topics will already have additional metadata
        if use_structured_output:
            for topic in topics_to_process:
                print(f"\nTopic: {topic.get('name', 'Untitled')}")
                if 'relevance_score' in topic:
                    print(f"Relevance Score: {topic['relevance_score']}")
                if 'significance_score' in topic:
                    print(f"Significance Score: {topic['significance_score']}")
                if 'priority_rank' in topic:
                    print(f"Priority Rank: {topic['priority_rank']}")
                if 'suggested_tags' in topic:
                    print(f"Suggested Tags: {', '.join(topic['suggested_tags'])}")
        
        return topics_to_process
        
    except Exception as e:
        print(f"Error generating topics: {e}")
        return []

def prioritize_topics(topics):
    response = None
    message = f"Prioritize the following topics in order of relevance to Cybersecurity:\n\n{topics}"
    try:
        response = query_gpt(message, "You are a data computer that outputs the pure information as a list and nothing else")
    except Exception as e:
        logging.error(f"Failed to prioritize topics: {e}")
        return []
    # Process the response to get a list of titles in order of relevance
    prioritized_titles = response.choices[0].message.content.split("\n")
    return prioritized_titles

