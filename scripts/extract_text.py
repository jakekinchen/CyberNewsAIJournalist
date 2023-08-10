import requests
import hashlib
import json
import os
import sys 
import random
import time
from scrapingbee import ScrapingBeeClient
from bs4 import BeautifulSoup
from urllib.parse import urlparse
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Set your ScrapingBee API key
scrapingbee_api_key = os.getenv('SCRAPINGBEE_API_KEY')

# Function to get user agents
def get_user_agents():
    # List of user agents
    user_agents = [
        # List your user agents here
         'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/89.0.4389.82 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64; rv:86.0) Gecko/20100101 Firefox/86.0',
    ]
    return user_agents

def extract_text(topic_dir):
    related_articles_file = os.path.join(topic_dir, 'related_articles.json')
    with open(related_articles_file) as f:
        related_articles = json.load(f)

    # Possible CSS selectors for the article body
    possible_selectors = [
        "article", ".article-content", "#content", ".post-body", 
        "div.main-content", "section.article", ".entry-content", 
        ".post-content", "main article", ".blog-post"
    ]

    # Initialize the scraping client with your API key
    client = ScrapingBeeClient(api_key=scrapingbee_api_key)

    # Define the user agent rotation and slow crawling options
    user_agent_rotation = False
    slow_crawling = False
    user_agents = get_user_agents()  # Use the function defined earlier

    for article in related_articles:
        url = article['url']

        # Add user agent rotation if enabled
        headers = {'User-Agent': random.choice(user_agents)} if user_agent_rotation else {}

        article_body = None

        for selector in possible_selectors:
            # Create the extraction rule with the current selector
            extraction_rules = json.dumps({"article_body": selector})

            # Fetch the raw HTML content using the ScrapingBee API
            response = client.get(url, headers=headers, params={'extract_rules': extraction_rules})

            # Add slow crawling delay if enabled
            if slow_crawling:
                time.sleep(random.uniform(0.5, 3.5))

            # Check the status of the response
            if response.status_code == 200:
                extracted_data = response.json()
                if 'article_body' in extracted_data and extracted_data['article_body']:
                    article_body = extracted_data['article_body']
                    break

        if article_body is None:
            print(f"Failed to retrieve the article body for URL: {url}")
            article_body = "Could not extract text body."

        # Extract external sources (modify as needed)
        ext_sources = [] # ...

        article['article_body'] = article_body
        article['ext_sources'] = ext_sources

        print(f"Processing article: {url}")

    # Save the updated articles data
    updated_articles_file = os.path.join(topic_dir, 'updated_articles.json')
    with open(updated_articles_file, 'w') as f:
        json.dump(related_articles, f, indent=4)
        
    # Check if the file is created
    if os.path.exists(updated_articles_file):
        print(f"Updated articles file created at {updated_articles_file}")
    else:
        print(f"Failed to create updated articles file at {updated_articles_file}")
