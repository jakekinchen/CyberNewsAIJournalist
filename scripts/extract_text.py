import requests
from bs4 import BeautifulSoup
from requests.adapters import HTTPAdapter
from requests.packages.urllib3.util.retry import Retry
import os
import random
from dotenv import load_dotenv
from urllib.parse import urlparse
from playwright.async_api import async_playwright
import asyncio

load_dotenv()
brightdata_host = os.getenv('BRIGHTDATA_HOST')

dc_username = os.getenv('BRIGHTDATA_DC_USERNAME')
dc_password = os.getenv('BRIGHTDATA_DC_PASSWORD')
dc_port = os.getenv('BRIGHTDATA_DC_PORT')

res_username = os.getenv('BRIGHTDATA_RES_USERNAME')
res_password = os.getenv('BRIGHTDATA_RES_PASSWORD')
res_port = os.getenv('BRIGHTDATA_RES_PORT')

sb_username = os.getenv('BRIGHTDATA_SB_USERNAME')
sb_password = os.getenv('BRIGHTDATA_SB_PASSWORD')
sb_port = os.getenv('BRIGHTDATA_SB_PORT')

headers = {'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'}

async def test_scraping_site():
    url = 'https://nvd.nist.gov/vuln/detail/CVE-2023-20109'
    html = await scrape_content(url, depth=1, exclude_internal_links=True, include_links=True)
    print(html)

async def establish_connection(url, prioritize_res_proxy=False):
    hostname = urlparse(url).hostname

    if hostname == 'nvd.nist.gov':
        return await fetch_without_proxy(url)
    
    if prioritize_res_proxy:
        return await fetch_using_dc_proxy(url) or await fetch_using_res_proxy(url) or await fetch_using_scraping_browser(url) or await fetch_without_proxy(url)
    else:
        return await fetch_using_dc_proxy(url) or await fetch_using_scraping_browser(url) or await fetch_without_proxy(url)

async def fetch_using_dc_proxy(url):
    session_id = random.randint(0, 1000000)
    super_proxy = f"http://brd-customer-{dc_username}-session-{session_id}-zone-unblocker:{dc_password}@brd.superproxy.io:{dc_port}"
    proxies = {"http": super_proxy, "https": super_proxy}
    try:
        response = requests.get(url, proxies=proxies, headers=headers, verify=False)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error with DC proxy for {url}: {e}")
        return None

async def fetch_using_res_proxy(url):
    session_id = random.randint(0, 1000000)
    res_super_proxy = f"http://brd-customer-{res_username}-session-{session_id}-zone-unblocker:{res_password}@brd.superproxy.io:{res_port}"
    res_proxies = {"http": res_super_proxy, "https": res_super_proxy}
    try:
        res_response = requests.get(url, proxies=res_proxies, headers=headers, verify=False)
        res_response.raise_for_status()
        return res_response.text
    except requests.exceptions.RequestException as e:
        print(f"Error with RES proxy for {url}: {e}")
        return None

async def fetch_using_scraping_browser(url):
    try:
        async with async_playwright() as p:
            browser = await p.chromium.connect_over_cdp(f'wss://{sb_username}:{sb_password}@{brightdata_host}:{sb_port}')
            page = await browser.new_page()
            await page.goto(url, timeout=2 * 60 * 1000)
            html = await page.content()
            await browser.close()
            return html
    except Exception as e:
        print(f"Error with scraping browser for {url}: {e}")
        return None

async def fetch_without_proxy(url):
    try:
        response = requests.get(url, headers=headers, verify=False)
        response.raise_for_status()
        return response.text
    except requests.exceptions.RequestException as e:
        print(f"Error without proxy for {url}: {e}")
        return None

async def scrape_content(url, depth=1, exclude_internal_links=True, include_links=True):
    try:
        html = await establish_connection(url)
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
        if include_links:
            external_links = []
            if depth > 0:
                base_domain = urlparse(url).netloc
                for p in soup.find_all('p'):
                    for a in p.find_all('a', href=True):
                        href = a['href']
                        # Exclude internal links based on whether the base domain is in the href
                        # and also if they start with a "/"
                        if exclude_internal_links and (base_domain in href or href.startswith('/')):
                            continue
                        external_links.append(href)
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