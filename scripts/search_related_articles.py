import os
import requests
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access your API keys
bing_api_key = os.getenv('BING_SEARCH_KEY')

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

