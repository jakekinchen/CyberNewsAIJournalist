import os
import json
import random
import requests
import hashlib
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Access your API keys
bing_api_key = os.getenv('BING_SEARCH_KEY')

def search_related_articles():
    # Constants
    DATA_PATH = os.path.join(os.getcwd(), 'data/temp')
    TOPICS_PATH = DATA_PATH
    NEWS_TOPICS_FILE = os.path.join(DATA_PATH, 'news_topics.json')
    SEARCHED_TOPICS_FILE = os.path.join(DATA_PATH, 'searched_topics.json')

    # Bing Search V7 endpoint
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"

    # Load news topics
    with open(NEWS_TOPICS_FILE, 'r') as f:
        news_topics = json.load(f)

    # Get already searched topics
    def get_searched_topics():
        if os.path.exists(SEARCHED_TOPICS_FILE):
            with open(SEARCHED_TOPICS_FILE, 'r') as file:
                return json.load(file)
        else:
            return []

    searched_topics = get_searched_topics()

    # Select a random topic that has not been searched before
    random.shuffle(news_topics)
    topic = next((t for t in news_topics if t not in searched_topics), None)

    if topic is None:
        print("All topics have been searched.")
        return None
    
    # Print the topic title
    print("Selected topic: " + topic['title'] + '\n')

    # Update the list of searched topics and write it back to the file
    searched_topics.append(topic)

    # Update the list of searched topics by writing it back to the file
    with open(SEARCHED_TOPICS_FILE, 'w') as file:
        json.dump(searched_topics, file)

    # Call the Bing API
    mkt = 'en-US'
    params = {'q': topic['title'], 'mkt': mkt, 'count': 5}
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}

    print("Querying Bing API with topic: " + str(topic))

    response = requests.get(endpoint, headers=headers, params=params)
    response.raise_for_status()

    news_result = response.json()

    # Save the response to a file in the topic's directory
    with open(os.path.join(TOPICS_PATH, 'news_result.json'), 'w') as f:
        json.dump(news_result, f, indent=4)

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
    # Create a new directory for the topic if it doesn't already exist
    # Make sure that "title" is the correct key in the topic dictionary that corresponds to the title of the topic
    title = topic['title']
    # Remove any characters from the title that are not letters, digits or underscores
    sanitized_title = ''.join(ch for ch in title if ch.isalnum() or ch == '_')
    # Use the first 16 characters of the sanitized title as the directory name
    directory_name = sanitized_title[:36]
    topic_dir = os.path.join(TOPICS_PATH, directory_name)

    os.makedirs(topic_dir, exist_ok=True)

    # Write the related articles to a file in the topic's directory
    with open(os.path.join(topic_dir, 'related_articles.json'), 'w') as f:
        json.dump(related_articles, f, indent=4)

    return topic_dir

if __name__ == "__main__":
    search_related_articles()
