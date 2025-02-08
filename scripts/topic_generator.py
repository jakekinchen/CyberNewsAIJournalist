"""
Module for generating topics from various RSS feeds and other sources.
"""

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import List, Dict, Any, Optional
from rss_config import get_all_feeds, get_feeds_by_category, get_feed_by_name
from feed_parsers import fetch_feed_content, parse_feed
from dateutil import parser
import pytz

logger = logging.getLogger(__name__)

def parse_date_safely(date_str: str) -> Optional[datetime]:
    """Parse date string to datetime, handling various formats."""
    try:
        # Parse the date string
        dt = parser.parse(date_str)
        # If the datetime is naive (no timezone info), assume UTC
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=pytz.UTC)
        # Otherwise, convert to UTC
        else:
            dt = dt.astimezone(pytz.UTC)
        return dt
    except (ValueError, TypeError) as e:
        print(f"Error parsing date '{date_str}': {e}")
        return None

async def gather_topics_from_feed(feed_config: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Gather topics from a single feed source."""
    try:
        print(f"Attempting to gather topics from {feed_config['name']}")
        content = await fetch_feed_content(
            feed_config['url'],
            format=feed_config.get('format', 'xml')
        )
        
        if content is None:
            print(f"Failed to fetch content from {feed_config['name']}")
            return []
            
        print(f"Successfully fetched content from {feed_config['name']}, parsing...")
        topics = await parse_feed(content, feed_config)
        print(f"Successfully gathered {len(topics)} topics from {feed_config['name']}")
        return topics
        
    except Exception as e:
        print(f"Error gathering topics from {feed_config['name']}: {e.__class__.__name__}: {str(e)}")
        return []

def filter_topics_by_age(topics, max_age_hours=72):
    """Filter topics based on their age.
    
    Args:
        topics (list): List of topic dictionaries
        max_age_hours (int): Maximum age in hours for a topic to be considered recent
        
    Returns:
        list: Filtered list of topics
    """
    cutoff_time = datetime.now(timezone.utc) - timedelta(hours=max_age_hours)
    filtered_topics = []
    
    for topic in topics:
        try:
            topic_date = parse_date_safely(topic.get('date_published'))
            if topic_date and topic_date >= cutoff_time:
                filtered_topics.append(topic)
        except (ValueError, TypeError) as e:
            logging.warning(f"Could not parse date for topic: {topic.get('title')}. Error: {str(e)}")
            continue
    
    return filtered_topics

async def gather_topics(
    categories: Optional[List[str]] = None,
    feed_names: Optional[List[str]] = None,
    max_age_hours: int = 72,
    min_topics: int = 50
) -> List[Dict[str, Any]]:
    """Gather topics from multiple feeds.
    
    Args:
        categories: Optional list of categories to filter feeds by
        feed_names: Optional list of feed names to filter by
        max_age_hours: Maximum age in hours for a topic
        min_topics: Minimum number of topics to gather before increasing age limit
        
    Returns:
        List of gathered topics
    """
    all_topics = []
    
    if categories:
        feeds = []
        for category in categories:
            feeds.extend(get_feeds_by_category(category))
    elif feed_names:
        feeds = [get_feed_by_name(name) for name in feed_names if get_feed_by_name(name)]
    else:
        feeds = get_all_feeds()
    
    for feed in feeds:
        try:
            feed_content = await fetch_feed_content(feed['url'], format=feed.get('format', 'xml'))
            if not feed_content:
                continue
                
            topics = await parse_feed(feed_content, feed)
            if topics:
                all_topics.extend(topics)
                
        except Exception as e:
            logging.error(f"Error gathering topics from {feed['name']}: {str(e)}")
            continue
    
    # Filter topics by age
    filtered_topics = filter_topics_by_age(all_topics, max_age_hours)
    
    # If we don't have enough topics, gradually increase the age limit
    while len(filtered_topics) < min_topics and max_age_hours < 168:  # Up to 1 week
        max_age_hours += 24
        filtered_topics = filter_topics_by_age(all_topics, max_age_hours)
    
    logging.info(f"Gathered {len(all_topics)} topics, {len(filtered_topics)} after age filtering")
    return filtered_topics

async def get_latest_topics(
    limit: int = 10,
    categories: Optional[List[str]] = None,
    feed_names: Optional[List[str]] = None,
    max_age_hours: Optional[int] = None
) -> List[Dict[str, Any]]:
    """
    Get the latest topics from specified feeds, sorted by date.
    
    Args:
        limit: Maximum number of topics to return
        categories: List of categories to gather from. If None, gather from all categories.
        feed_names: List of specific feed names to gather from. If None, gather from all feeds.
        max_age_hours: Maximum age of topics in hours. If None, defaults to 168 (1 week).
        
    Returns:
        List of topic dictionaries, sorted by date (newest first).
    """
    # Get topics from the last week by default
    topics = await gather_topics(
        categories=categories,
        feed_names=feed_names,
        max_age_hours=max_age_hours if max_age_hours is not None else 168,  # 1 week default
        min_topics=limit
    )
    
    # Sort by date and return the most recent ones
    topics.sort(
        key=lambda x: parse_date_safely(x['date_published']) or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True
    )
    
    return topics[:limit] 