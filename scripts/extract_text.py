import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
import random
from dotenv import load_dotenv
from urllib.parse import urlparse
import certifi

load_dotenv()

async def test_scraping_site():
    url = 'https://nvd.nist.gov/vuln/detail/CVE-2023-20109'
    html = scrape_content(url, depth=1, exclude_internal_links=True, include_links=True)
    print(html)

def establish_connection(url):
    hostname = urlparse(url).hostname
    if '.gov' in hostname:
        fetch_using_proxy(url, 'zu') or fetch_using_proxy(url, 'res') or fetch_using_proxy(url, 'sb') or fetch_using_proxy(url)
    else:
        return fetch_using_proxy(url, 'dc') or fetch_using_proxy(url, 'zu') or fetch_using_proxy(url, 'res') or fetch_using_proxy(url, 'sb') or fetch_using_proxy(url)

def fetch_using_proxy(url, proxy_type=None):
    ca_bundle_path = '/usr/local/share/ca-certificates/CA-BrightData.crt'

    headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}
    
    # Check if proxy_type is not None and not an empty string
    if proxy_type:
        # Convert proxy type to uppercase
        proxy_type = proxy_type.upper()
        # Get the proxy credentials and port from environment variables
        username = os.getenv(f'BRIGHTDATA_{proxy_type}_USERNAME')
        password = os.getenv(f'BRIGHTDATA_{proxy_type}_PASSWORD')
        port = os.getenv(f'BRIGHTDATA_{proxy_type}_PORT')
        # Construct the proxy URL
        super_proxy = f"http://{username}:{password}@brd.superproxy.io:{port}"
        proxies = {"http": super_proxy, "https": super_proxy}
    else:
        proxies = None
        proxy_type = 'no'
    
    # Try to fetch the URL using the proxy (if specified)
    try:
        response = requests.get(url, proxies=proxies, headers=headers, verify=ca_bundle_path) 
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error with using {proxy_type} proxy for {url}: {e}")
        return None
    
def is_valid_http_url(url):
    try:
        parsed_url = urlparse(url)
        return all([parsed_url.scheme, parsed_url.netloc, parsed_url.scheme in ['http', 'https']])
    except ValueError:
        return False

def extract_external_links(soup, base_domain, depth, exclude_internal_links):
    external_links = []
    if depth > 0:
        for p in soup.find_all('p'):
            for a in p.find_all('a', href=True):
                href = a['href']
                # Validate URL and exclude internal links based on the provided conditions
                if is_valid_http_url(href) and not (
                    exclude_internal_links and (base_domain in href or href.startswith('/'))
                ):
                    external_links.append(href)
    return external_links

def scrape_content(url, depth=1, exclude_internal_links=True, include_links=True, is_external=False):
    try:
        # Check if the URL points to a PDF
        if url.lower().endswith('.pdf'):
            if is_external:
                # If it's an external link, don't scrape it but include it in the external links
                return None, [url]
            else:
                # If it's a main source, skip over it
                print(f"Skipping main PDF source: {url}")
                return None, []
        
        # The rest of your scraping logic remains the same
        html = establish_connection(url)
        if html is None:
            raise ValueError("Unable to retrieve HTML")

        soup = BeautifulSoup(html, 'html.parser')
        content = None

        # Specific handling for certain websites
        if 'thehackernews.com' in url or 'yahoo.com' in url:
            content = ' '.join([p.get_text().strip() for p in soup.find_all('p')])
        elif 'wsj.com' in url:
            content = ' '.join([p.get_text().strip() for p in soup.find_all('p', attrs={'data-type': 'paragraph'})])
        elif 'exploit-db.com' in url:
            return exploit_db_content(soup)

        # Generic handling for other websites
        else:
            possible_selectors = [
                "article", ".article-content", "#content", ".post-body",
                "div.main-content", "section.article", ".entry-content",
                ".post-content", "main article", ".blog-post",
            ]
            for selector in possible_selectors:
                selected_content = soup.select_one(selector)
                if selected_content:
                    content = selected_content.get_text().strip()
                    break
        
        # Fallback to using <p> tag text if no content found using selectors
        if not content:
            content = ' '.join([p.get_text().strip() for p in soup.find_all('p')])

        # Extract links if needed
        external_links = []
        if include_links:
            base_domain = urlparse(url).netloc
            external_links = extract_external_links(soup, base_domain, depth, exclude_internal_links)
            return content, external_links

    except Exception as error:
        print(f"Failed to scrape URL: {url}. Error: {error}")
        if include_links:
            return None, []  # Return empty list of links in case of error when include_links is True
        return None

def exploit_db_content(soup):
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

    links = soup.select('td[data-testid^="vuln-hyperlinks-link-"] a')
    # Extract href attributes from the selected links
    links = [link['href'] for link in links]

    #put the title, edbid, author, type, platform, date, and code variables into a json structured object named content
    content = {
        "title": title,
        "edb_id": edb_id,
        "author": author,
        "type": type,
        "platform": platform,
        "date": date,
        "cve": cve,
        "code": code,
        "hyperlinks": links,
    }
    return content