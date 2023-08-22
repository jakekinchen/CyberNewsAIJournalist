import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
import random
from dotenv import load_dotenv

load_dotenv()

username = os.getenv('BRIGHTDATA_USERNAME')
password = os.getenv('BRIGHTDATA_PASSWORD')

def scrape_news(url):
    try:
        # Generate a random session ID
        session_id = random.randint(0, 1000000)
        # Set up proxy with session ID
        super_proxy = f"http://brd-customer-{username}-session-{session_id}-zone-unblocker:{password}@brd.superproxy.io:22225"
        proxies = {
            "http": super_proxy,
            "https": super_proxy
        }
        # User-Agent
        headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
        }
        # Retry mechanism
        session = requests.Session()
        retry = Retry(total=5, backoff_factor=0.1, status_forcelist=[500, 502, 503, 504])
        adapter = HTTPAdapter(max_retries=retry)
        session.mount('http://', adapter)
        session.mount('https://', adapter)
        # Make the request
        response = session.get(url, proxies=proxies, headers=headers, verify=False)
        soup = BeautifulSoup(response.text, 'html.parser')

        # If the URL is from "thehackernews.com", extract text content within <p> tags
        if 'thehackernews.com' in url:
            content = ' '.join([p.get_text().strip() for p in soup.find_all('p')])
        else:
            # Possible CSS selectors for the article body
            possible_selectors = [
                "article", ".article-content", "#content", ".post-body",
                "div.main-content", "section.article", ".entry-content",
                ".post-content", "main article", ".blog-post",
            ]
            content = None
            for selector in possible_selectors:
                selected_content = soup.select_one(selector)
                if selected_content:
                    content = selected_content.get_text().strip()
                    break

        return content
    except Exception as error:
        print(f"Failed to scrape URL: {url}. Error: {error}")
        return None

