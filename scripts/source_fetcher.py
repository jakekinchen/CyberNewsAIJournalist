import os
import requests
from dotenv import load_dotenv
from datetime import datetime
from extract_text import scrape_content

# Load .env file
load_dotenv()

# Access your API keys
bing_api_key = os.getenv('BING_SEARCH_KEY')

def gather_sources(supabase, topic, MIN_SOURCES=2, overload=False):
    date_accessed = datetime.now().isoformat()
    
    response = supabase.table("sources").select("*").eq("topic_id", topic["id"]).execute()
    existing_sources = response.data or []
    required_sources = MIN_SOURCES - len(existing_sources)
    
    if overload:
        required_sources += 3  # Increase the number if overloaded

    if required_sources > 0:
        related_sources = search_related_sources(topic["name"], len(existing_sources))
        
        for source in related_sources[:required_sources]:
            if source['url'] == "https://thehackernews.com/search?":  # Skip the URL to be deleted
                continue
            
           # print(f"Scraping source from {source['url']}...")
            content = scrape_content(source["url"])
            
            if content:
               # print(f"Successfully scraped source from {source['url']}")
                supabase.table("sources").insert([{
                    "url": source["url"],
                    "content": content,
                    "topic_id": topic["id"],
                    "date_accessed": date_accessed
                }]).execute()
               # print(f"Source from {source['url']} saved to Supabase.")
            else:
                print(f"Failed to scrape source from {source['url']}")

def search_related_sources(query, offset=0):
    # Call the Bing API
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"
    bing_api_key = os.getenv('BING_NEWS_KEY')
    params = {"q": query, "mkt": "en-US", "count": 5, "offset": offset}
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