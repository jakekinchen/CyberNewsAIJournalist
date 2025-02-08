import os
import httpx
from dotenv import load_dotenv
import logging
from datetime import datetime

# Load environment variables
load_dotenv()

# Access Google CSE API keys
google_api_key = os.getenv('GOOGLE_API_KEY')
google_cx = os.getenv('GOOGLE_CX')

# Start ID from the last used ID + 1
STARTING_ID = 5138

def fetch_sources_from_google_cse(query, num_results=10):
    """
    Fetch sources using Google Custom Search Engine API.
    
    Args:
        query (str): The search query
        num_results (int): Number of results to return (default: 10)
        
    Returns:
        list: List of dictionaries containing source information
    """
    print(f"Fetching sources from Google CSE with query: {query}")
    
    # Validate API credentials
    if not google_api_key or not google_cx:
        print("Error: Google CSE API key or CX not found in environment variables")
        return []
        
    # Google Custom Search API endpoint
    endpoint = "https://www.googleapis.com/customsearch/v1"
    
    # Try first with site restriction
    params = {
        'q': query,
        'cx': google_cx,
        'key': google_api_key,
        'num': num_results,
        'dateRestrict': 'm1',  # Restrict to last month
        'sort': 'date',  # Sort by date
        'siteSearch': 'thehackernews.com',  # Restrict to The Hacker News
        'siteSearchFilter': 'i'  # Include only pages from this site
    }
    
    related_sources = []
    
    # First attempt with site restriction
    try:
        print("Making request to Google CSE API with site restriction...")
        response = httpx.get(endpoint, params=params, timeout=30.0)
        response.raise_for_status()
        search_result = response.json()
        print(f"Search info (with site restriction): {search_result.get('searchInformation', {})}")
        related_sources.extend(process_search_results(search_result))
    except Exception as e:
        print(f"Error with site-restricted search: {e}")
    
    # If we don't have enough sources, try without site restriction
    if len(related_sources) < 3:
        print("Not enough sources found with site restriction, trying without...")
        params.pop('siteSearch')
        params.pop('siteSearchFilter')
        try:
            print("Making request to Google CSE API without site restriction...")
            response = httpx.get(endpoint, params=params, timeout=30.0)
            response.raise_for_status()
            search_result = response.json()
            print(f"Search info (without site restriction): {search_result.get('searchInformation', {})}")
            related_sources.extend(process_search_results(search_result))
        except Exception as e:
            print(f"Error with unrestricted search: {e}")
    
    print(f"Found {len(related_sources)} total valid sources")
    return related_sources

def process_search_results(search_result):
    """Process search results and extract valid sources."""
    sources = []
    if 'items' in search_result:
        current_time = datetime.now().isoformat()
        for item in search_result['items']:
            try:
                if all(key in item for key in ("title", "link")):
                    url = item['link']
                    

                    
                    # Skip category pages, search pages, and other non-article pages
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
                        print(f"Skipping non-article page: {url}")
                        continue
                        
                    # Skip social media and video platforms
                    if any(domain in url.lower() for domain in [
                        'twitter.com',
                        'facebook.com',
                        'youtube.com',
                        'linkedin.com'
                    ]):
                        print(f"Skipping social media link: {url}")
                        continue
                        
                    source = {
                        'name': item['title'],
                        'url': url,
                        'date_accessed': current_time,
                        'content': None  # Content will be fetched later
                    }
                    print(f"Found source: {item['title']} ({url})")
                    sources.append(source)
            except Exception as e:
                print(f"Error processing search result item: {e}")
                continue
    return sources 