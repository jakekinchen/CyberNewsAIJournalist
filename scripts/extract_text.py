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

def scrape_content(url):
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

        # If the URL is from "thehackernews.com" or yahoo.com, extract text content within <p> tags
        if 'thehackernews.com' or 'yahoo.com' in url:
            content = ' '.join([p.get_text().strip() for p in soup.find_all('p')])
        # else if statement in python for exploit-db.com
        elif 'exploit-db.com' in url:
            content = ' '.join([p.get_text().strip() for p in soup.find_all('p')])
            # take the text inside the code class tag and add it to a variable named code
            code = soup.find_all('code')
            #remove the first double quote and space from the beginning of the code variable and from the end of the code variable
            code = str(code)[2:-2]
            # take the text from the h1 tag and add it to a variable named title
            title = soup.find_all('h1')
            #remove the first double quote and space from the beginning of the title variable and from the end of the title variable
            title = str(title)[2:-2]
            # find the position of the h4 tag whose text contains edb-id and select the next sibling tag's text and add it to a variable named edbid
            edb_id = soup.find('h4', text=lambda t: t and 'EDB-ID' in t).find_next_sibling('p').text
            # find the position of the h4 tag whose text contains author and select the next sibling tag's text and add it to a variable named author
            author = soup.find('h4', text=lambda t: t and 'Author' in t).find_next_sibling('p').text
            # find the position of the h4 tag whose text contains type and select the next sibling tag's text and add it to a variable named type
            type = soup.find('h4', text=lambda t: t and 'Type' in t).find_next_sibling('p').text
            # find the position of the h4 tag whose text contains platform and select the next sibling tag's text and add it to a variable named platform
            platform = soup.find('h4', text=lambda t: t and 'Platform' in t).find_next_sibling('p').text
            # find the position of the h4 tag whose text contains date and select the next sibling tag's text and add it to a variable named date
            date = soup.find('h4', text=lambda t: t and 'Date' in t).find_next_sibling('p').text
            cve = soup.find('h4', text=lambda t: t and 'CVE' in t).find_next_sibling('p').text
            #remove the first double quote and space from the beginning of the edb_id variable and from the end of the edb_id variable
            edb_id = str(edb_id)[2:-2]
            #remove the first double quote and space from the beginning of the author variable and from the end of the author variable
            author = str(author)[2:-2]
            #remove the first double quote and space from the beginning of the type variable and from the end of the type variable
            type = str(type)[2:-2]
            #remove the first double quote and space from the beginning of the platform variable and from the end of the platform variable
            platform = str(platform)[2:-2]
            #remove the first double quote and space from the beginning of the date variable and from the end of the date variable
            date = str(date)[2:-2]
            #remove the first double quote and space from the beginning of the cve variable and from the end of the cve variable
            cve = str(cve)[2:-2]
            #put the title, edbid, author, type, platform, date, and code variables into a json structured object named content
            content = {
                "title": title,
                "edb_id": edb_id,
                "author": author,
                "type": type,
                "platform": platform,
                "date": date,
                "cve": cve,
                "code": code
            }
            return content

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

