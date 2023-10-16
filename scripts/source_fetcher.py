import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from extract_text import scrape_content
from content_optimization import tokenizer
import logging

# Load .env file
load_dotenv()

# Access your API keys
bing_api_key = os.getenv('BING_SEARCH_KEY')

def check_if_content_exceeds_limit(content):
    # Check if the source content exceeds the limit
    token_quantity = tokenizer(content, 'gpt-3.5-turbo-16k')
    if token_quantity >= 16384:
        logging.warning(f"Source content exceeds the limit: {token_quantity}")
        return True


def gather_and_store_sources(supabase, url, topic_id, date_accessed, depth, exclude_internal_links, existing_sources, accumulated_sources):

    content, external_links = scrape_content(url, depth=depth, exclude_internal_links=exclude_internal_links)
    # Append the current source into accumulated_sources if content is scraped successfully
    if content and not check_if_content_exceeds_limit(content):
        accumulated_sources.append({
            "url": url,
            "content": content,
            "topic_id": topic_id,
            "date_accessed": date_accessed,
            "external_source": depth < 2  # True if this source is an external link extracted from another source
        })
        existing_sources.add(url)  # Update the existing_sources set with the new URL
    
    # Recursively gather and store sources for external links found
    if depth > 1 and external_links:
        for link in external_links:
            gather_and_store_sources(supabase, link, topic_id, date_accessed, depth - 1, exclude_internal_links, existing_sources, accumulated_sources)


def gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2, exclude_internal_links=True):
    date_accessed = datetime.now().isoformat()

    response = supabase.table("sources").select("url").eq("topic_id", topic["id"]).execute()
    existing_sources = set([source['url'] for source in response.data]) if response.data else set()
    required_sources = MIN_SOURCES - len(existing_sources)

    if overload:
        required_sources += 3  # Increase the number if overloaded

    accumulated_sources = []
    if required_sources > 0:
        related_sources = search_related_sources(topic["name"], len(existing_sources))

        for source in related_sources:
            if len(accumulated_sources) >= required_sources:
                # Break once we've accumulated enough sources
                break
            
            if source['url'] == "https://thehackernews.com/search?" or "msn.com" in source['url']:  
                continue

            gather_and_store_sources(supabase, source["url"], topic["id"], date_accessed, depth, exclude_internal_links, existing_sources, accumulated_sources)

    # Batch insert the accumulated sources into Supabase
    if accumulated_sources:
        try:
            response = supabase.table("sources").insert(accumulated_sources).execute()
        except Exception as e:
            print(f"Failed to insert sources into Supabase: {e}")


def search_related_sources(query, offset=0):
    # Call the Bing API
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"
    bing_api_key = os.getenv('BING_NEWS_KEY')
    params = {"q": query, "mkt": "en-US", "count": 10, "offset": offset}
    headers = {"Ocp-Apim-Subscription-Key": bing_api_key}
    response = requests.get(endpoint, headers=headers, params=params)
    news_result = response.json()

    # Extract related sources
    related_sources = [
        {
            "topic_name": news_result["queryContext"]["originalQuery"],
            "name": result["name"],
            "url": result["url"],
            "description": result["description"],
            "date_published": result["datePublished"],
            "provider": result["provider"][0]["name"] if result["provider"] else None,
        }
        for result in news_result["value"]
    ]
    return related_sources

def search_related_articles(topic):
    # Bing Search V7 endpoint
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"

    # Call the Bing API
    mkt = 'en-US'
    params = {'q': topic['title'], 'mkt': mkt, 'count': 5}
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}

    print("Querying Bing API with topic: " + str(topic))

    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()

    news_result = response.json()

    # Extract related articles
    related_articles = []
    if news_result['value']:
        for result in news_result['value']:
            # Check if all keys exist
            if all(key in result for key in ("name", "url", "description", "datePublished", "provider")):
                article = {
                    "name": result['name'],
                    "url": result['url'],
                    "description": result['description'],
                    "date_published": result['datePublished'],
                    "provider": result['provider'][0]['name'] if result['provider'] else None  # Check if provider list is not empty
                }
                related_articles.append(article)
    return related_articles

def delete_targeted_sources(supabase, target_url):
    #find all source url's that begin with https://thehackernews.com/search? and delete them
    #remove the quotes from the beginning and end of the target_url variable
    target_url = target_url[1:-1]
    response = supabase.table("sources").select("*").like("url", f"%{target_url}%").execute()
    sources = response.data
    for source in sources:
        supabase.table("sources").delete().eq("id", source["id"]).execute()
        print(f"Deleted source from {source['url']} because it is a search query.")

def delete_duplicate_source_urls(supabase):
    #find all source's with duplicate urls and delete them
    response = supabase.table("sources").select("*").execute()
    sources = response.data
    for source in sources:
        response = supabase.table("sources").select("*").eq("url", source["url"]).execute()
        duplicate_sources = response.data
        if len(duplicate_sources) > 1:
            for duplicate_source in duplicate_sources:
                if duplicate_source["id"] != source["id"]:
                    supabase.table("sources").delete().eq("id", duplicate_source["id"]).execute()
                    print(f"Deleted duplicate source from {duplicate_source['url']}")