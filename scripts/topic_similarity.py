"""
Module for checking similarity between topics using structured outputs.
"""

from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from pydantic import BaseModel
from openai import OpenAI
import logging
from extract_text import scrape_content, fetch_using_proxy
from topic_generator import get_latest_topics
from scripts.supabase_utils import supabase

logger = logging.getLogger(__name__)

class SimilarityResponse(BaseModel):
    is_similar: bool
    explanation: str

async def get_topic_content(topic: Dict[str, Any]) -> Optional[str]:
    """
    Get the full content of a topic by scraping its URL.
    
    Args:
        topic: The topic dictionary containing the URL
        
    Returns:
        Optional[str]: The scraped content if successful, None otherwise
    """
    try:
        # First try direct scraping
        content = await scrape_content(topic['url'])
        if content:
            return content
            
        # If that fails, try with proxy
        content = await fetch_using_proxy(topic['url'])
        return content
        
    except Exception as e:
        logger.error(f"Error fetching content for topic {topic['name']}: {e}")
        return None

async def get_recent_topics(hours: int = 48) -> List[Dict[str, Any]]:
    """
    Get topics from the last specified hours.
    
    Args:
        hours: Number of hours to look back
        
    Returns:
        List of recent topics
    """
    try:
        cutoff_time = datetime.now() - timedelta(hours=hours)
        response = supabase.table('topics').select('*').gte('date_published', cutoff_time.isoformat()).execute()
        
        # Filter to only include topics within our time window
        recent_topics = []
        for topic in response.data if response and hasattr(response, 'data') else []:
            try:
                date_published = datetime.fromisoformat(topic['date_published'].replace('Z', '+00:00'))
                if date_published >= cutoff_time:
                    # Get the content for each topic
                    content = await get_topic_content(topic)
                    if content:
                        topic['content'] = content
                    recent_topics.append(topic)
            except (ValueError, KeyError) as e:
                logger.warning(f"Error parsing date for topic {topic.get('name')}: {e}")
                continue
                
        return recent_topics
    except Exception as e:
        logger.error(f"Error fetching recent topics: {e}")
        return []

async def check_topic_similarity(new_topic: Dict[str, Any], recent_topics: List[Dict[str, Any]]) -> bool:
    """
    Check if a new topic is similar to any recent topics using the OpenAI API.
    
    Args:
        new_topic: The new topic to check
        recent_topics: List of recent topics to compare against
        
    Returns:
        bool: True if the topic is similar to any recent topics
    """
    if not recent_topics:
        return False
        
    client = OpenAI()
    
    # Get content for the new topic if not already present
    if 'content' not in new_topic:
        new_topic['content'] = await get_topic_content(new_topic)
    
    # Format topics for comparison
    comparison_data = []
    for topic in recent_topics:
        topic_data = {
            'title': topic['name'],
            'content_preview': topic.get('content', '')[:500] if topic.get('content') else ''
        }
        comparison_data.append(topic_data)
    
    comparison_str = "\n\n".join([
        f"Title: {data['title']}\nContent Preview: {data['content_preview']}"
        for data in comparison_data
    ])
    
    try:
        completion = client.beta.chat.completions.parse(
            model="o3-mini",
            messages=[
                {
                    "role": "system",
                    "content": "You are an expert at determining if cybersecurity topics are similar or duplicates. "
                              "Compare the new topic with the list of recent topics and determine if they cover the same or very similar subject matter. "
                              "Consider both the title and content preview for semantic similarity, not just exact matches."
                },
                {
                    "role": "user",
                    "content": (
                        f"New topic:\nTitle: {new_topic['name']}\n"
                        f"Content Preview: {new_topic.get('content', '')[:500]}\n\n"
                        f"Recent topics:\n{comparison_str}"
                    )
                }
            ],
            response_format=SimilarityResponse
        )
        
        result = completion.choices[0].message.parsed
        if not result:
            logger.error("Failed to get parsed response from OpenAI")
            return False
            
        if result.is_similar:
            logger.info(f"Topic '{new_topic['name']}' was found to be similar to existing topics. Explanation: {result.explanation}")
        
        return result.is_similar
        
    except Exception as e:
        logger.error(f"Error checking topic similarity: {e}")
        # In case of error, let it through (better to have a potential duplicate than miss content)
        return False

async def is_topic_unique(topic: Dict[str, Any]) -> bool:
    """
    Check if a topic is unique compared to recent topics.
    
    Args:
        topic: The topic to check
        
    Returns:
        bool: True if the topic is unique, False if it's similar to recent topics
    """
    try:
        # Get recent topics
        recent_topics = await get_recent_topics(hours=48)
        logger.info(f"Found {len(recent_topics)} topics from the last 48 hours")
        
        # Check similarity
        is_similar = await check_topic_similarity(topic, recent_topics)
        
        return not is_similar
        
    except Exception as e:
        logger.error(f"Error checking topic uniqueness: {e}")
        # In case of error, let it through (better to have a potential duplicate than miss content)
        return True 