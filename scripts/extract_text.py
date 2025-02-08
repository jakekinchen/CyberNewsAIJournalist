import httpx
from bs4 import BeautifulSoup
import os
from dotenv import load_dotenv
from urllib.parse import urlparse
import certifi
import ssl
import subprocess
import socket
from OpenSSL import crypto
import pathlib
import asyncio
from playwright.async_api import async_playwright
from stealth_browser import scrape_with_stealth
import tempfile
from PyPDF2 import PdfReader
import logging
from typing import Optional, Tuple, Union
import io

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

load_dotenv()

# Get the path to the CA certificate
CA_CERT_PATH = str(pathlib.Path(__file__).parent.parent / 'ca.crt')

class PDFExtractionError(Exception):
    """Custom exception for PDF extraction errors."""
    pass

async def download_pdf(url: str, client: httpx.AsyncClient) -> Optional[bytes]:
    """
    Download a PDF file from a URL.
    
    Args:
        url (str): The URL of the PDF file
        client (httpx.AsyncClient): The HTTP client to use for the request
        
    Returns:
        Optional[bytes]: The PDF content as bytes if successful, None otherwise
    """
    try:
        response = await client.get(url)
        response.raise_for_status()
        
        # Check if the response is actually a PDF
        content_type = response.headers.get('content-type', '').lower()
        if 'application/pdf' not in content_type:
            logger.error(f"URL {url} did not return a PDF (content-type: {content_type})")
            return None
            
        return response.content
    except httpx.HTTPError as e:
        logger.error(f"HTTP error occurred while downloading PDF from {url}: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error occurred while downloading PDF from {url}: {e}")
        return None

def extract_text_from_pdf(pdf_content: bytes) -> Optional[str]:
    """
    Extract text from a PDF file.
    
    Args:
        pdf_content (bytes): The PDF content as bytes
        
    Returns:
        Optional[str]: The extracted text if successful, None otherwise
        
    Raises:
        PDFExtractionError: If there's an error processing the PDF
    """
    try:
        # Create a file-like object from the bytes
        pdf_file = io.BytesIO(pdf_content)
        
        # Create PDF reader object
        pdf_reader = PdfReader(pdf_file)
        
        # Extract text from all pages
        text = []
        for page in pdf_reader.pages:
            try:
                page_text = page.extract_text()
                if page_text:
                    text.append(page_text)
            except Exception as e:
                logger.warning(f"Failed to extract text from page: {e}")
                continue
        
        if not text:
            raise PDFExtractionError("No text could be extracted from the PDF")
            
        return "\n".join(text)
    except Exception as e:
        raise PDFExtractionError(f"Error processing PDF: {e}")

async def scrape_pdf(url: str) -> Optional[str]:
    """
    Scrape text content from a PDF URL.
    
    Args:
        url (str): The URL of the PDF to scrape
        
    Returns:
        Optional[str]: The extracted text if successful, None otherwise
    """
    async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
        try:
            # Download the PDF
            pdf_content = await download_pdf(url, client)
            if not pdf_content:
                logger.error(f"Failed to download PDF from {url}")
                return None
            
            # Extract text from the PDF
            text = extract_text_from_pdf(pdf_content)
            if not text:
                logger.error(f"Failed to extract text from PDF at {url}")
                return None
            
            return text
        except PDFExtractionError as e:
            logger.error(f"PDF extraction error for {url}: {e}")
            return None
        except Exception as e:
            logger.error(f"Unexpected error while scraping PDF from {url}: {e}")
            return None

async def fetch_with_scraping_browser(url):
    """Fetch content using Scraping Browser with Playwright."""
    username = os.getenv('BRIGHTDATA_SB_USERNAME')
    password = os.getenv('BRIGHTDATA_SB_PASSWORD')
    auth = f"{username}:{password}"
    sbr_ws_cdp = f'wss://{auth}@brd.superproxy.io:9222'

    try:
        async with async_playwright() as pw:
            print(f'Connecting to Scraping Browser for {url}...')
            browser = await pw.chromium.connect_over_cdp(sbr_ws_cdp)
            try:
                page = await browser.new_page()
                await page.goto(url, timeout=60000)  # 60 second timeout
                
                # Handle potential CAPTCHA
                client = await page.context.new_cdp_session(page)
                solve_result = await client.send('Captcha.solve', {'detectTimeout': 30000})
                print(f'Captcha solve status: {solve_result.get("status", "unknown")}')
                
                # Get the page content
                content = await page.content()
                return content
            finally:
                await browser.close()
    except Exception as e:
        print(f"Error with Scraping Browser for {url}: {e}")
        return None

def get_proxy_url(proxy_type='RES'):
    """Get proxy URL for the specified proxy type."""
    username = os.getenv(f'BRIGHTDATA_{proxy_type}_USERNAME')
    password = os.getenv(f'BRIGHTDATA_{proxy_type}_PASSWORD')
    port = '33335'  # Using the new port for the updated certificate
    return f"https://{username}:{password}@brd.superproxy.io:{port}"

async def fetch_using_proxy(url):
    """
    Fetch content using a proxy service
    """
    try:
        title, text = await scrape_with_stealth(url)
        if text:
            return text
        return None
    except Exception as e:
        print(f"Error using proxy: {str(e)}")
        return None

def collect_diagnostic_info(url, proxy_url):
    print("=== Diagnostic Information ===")
    
    hostname = urlparse(url).hostname

    # 1. Basic Connection Information
    print("\n[1. Basic Connection Information]")
    print(f"Target URL: {url}")
    print(f"Proxy URL: {proxy_url}")

    # 2. DNS Resolution
    print("\n[2. DNS Resolution]")
    try:
        ip_address = socket.gethostbyname(hostname)
        print(f"IP Address of {hostname}: {ip_address}")
    except Exception as e:
        print(f"Error during DNS resolution: {e}")

    # 3. SSL/TLS Information
    print("\n[3. SSL/TLS Information]")
    try:
        context = ssl.create_default_context()
        with socket.create_connection((hostname, 443)) as sock:
            with context.wrap_socket(sock, server_hostname=hostname) as ssock:
                print("SSL/TLS Version:", ssock.version())
                print("Cipher:", ssock.cipher())
                print("SSL/TLS Cert:", ssock.getpeercert())
    except Exception as e:
        print(f"Error during SSL/TLS handshake: {e}")

    # 4. Direct Connection without Proxy
    print("\n[4. Direct Connection without Proxy]")
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    try:
        response = httpx.get(url, headers=headers, timeout=10)
        print(f"Status Code: {response.status_code}")
        print("Response Headers:", response.headers)
    except httpx.RequestError as e:
        print(f"Error during direct connection: {e}")

    # 5. Connection through Proxy
    print("\n[5. Connection through Proxy]")
    context = ssl.create_default_context()
    BRIGHTDATA_CERT_PATH = '/usr/local/share/ca-certificates/CA-BrightData.crt'
    
    context.load_cert_chain(certfile=BRIGHTDATA_CERT_PATH)
    if proxy_url:
        proxies = {
            "http://": proxy_url,
            "https://": proxy_url
        }
        try:
            response = httpx.get(url, headers=headers, proxies=proxies, timeout=10)
            print(f"Status Code: {response.status_code}")
            print("Response Headers:", response.headers)
        except httpx.RequestError as e:
            print(f"Error during connection through proxy: {e}")
    else:
        print("No proxy URL provided.")

    print("\n=== End of Diagnostic Information ===")

def test_connection_without_ssl_verification(url):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }
    try:
        response = httpx.get(url, headers=headers, verify=False)
        response.raise_for_status()
        print(f"Successfully fetched {url} without SSL verification.")
    except httpx.RequestError as e:
        print(f"Error while connecting to {url} without SSL verification: {e}")


def test_ssl_handshake(url, proxy_url=None):
    if proxy_url:
        # Use proxy hostname and port for testing
        hostname = urlparse(proxy_url).hostname
        port = urlparse(proxy_url).port
    else:
        # Use original URL's hostname
        hostname = urlparse(url).hostname
        port = 443  # default for HTTPS
    
    command = ["openssl", "s_client", "-connect", f"{hostname}:{port}", "-prexit"]
    
    try:
        result = subprocess.run(command, capture_output=True, text=True, timeout=10)
        print("=== SSL Handshake Output ===")
        print(result.stdout)
        print("============================")
    except subprocess.TimeoutExpired:
        print("The openssl command timed out.")
    except Exception as e:
        print(f"Error executing openssl command: {e}")

async def test_scraping_site(url):
   # Setup
    target_url = url
    username = os.getenv('BRIGHTDATA_DC_USERNAME')
    password = os.getenv('BRIGHTDATA_DC_PASSWORD')
    port = os.getenv('BRIGHTDATA_DC_PORT')
    proxy_url = f"https://{username}:{password}@brd.superproxy.io:{port}"

    # Call the diagnostic function
    #collect_diagnostic_info(target_url, proxy_url)
    # Scrape content
    content, external_links = await scrape_content(target_url, depth=1, include_links=True, is_external=False)
    print(f"Content: {content}")    

async def scrape_content(url: str, depth: int = 1, include_links: bool = True, is_external: bool = False) -> Optional[str]:
    """
    Scrape content from a URL with improved error handling and fallback mechanisms.
    
    Args:
        url (str): The URL to scrape
        depth (int): How deep to follow links (default: 1)
        include_links (bool): Whether to include links in the output (default: True)
        is_external (bool): Whether this is an external source (default: False)
        
    Returns:
        Optional[str]: The scraped content if successful, None otherwise
    """
    if not url or not isinstance(url, str):
        print(f"Invalid URL provided: {url}")
        return None
        
    # Clean and validate URL
    url = url.strip()
    if not url.startswith(('http://', 'https://')):
        url = 'https://' + url
        
    try:
        # First try direct connection with a short timeout
        async with httpx.AsyncClient(verify=False, timeout=10.0) as client:
            try:
                response = await client.get(url)
                if response.status_code == 200:
                    soup = BeautifulSoup(response.text, 'html.parser')
                    # Remove script and style elements
                    for script in soup(["script", "style"]):
                        script.decompose()
                    text = soup.get_text()
                    # Clean up text
                    lines = (line.strip() for line in text.splitlines())
                    chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
                    text = ' '.join(chunk for chunk in chunks if chunk)
                    return text
            except Exception as e:
                print(f"Direct connection failed: {e}")
                
        # If direct connection fails, try with proxy
        content = await fetch_using_proxy(url)
        if content:
            soup = BeautifulSoup(content, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text
            
        # If both methods fail, try scraping browser as last resort
        content = await fetch_with_scraping_browser(url)
        if content:
            soup = BeautifulSoup(content, 'html.parser')
            # Remove script and style elements
            for script in soup(["script", "style"]):
                script.decompose()
            text = soup.get_text()
            # Clean up text
            lines = (line.strip() for line in text.splitlines())
            chunks = (phrase.strip() for line in lines for phrase in line.split("  "))
            text = ' '.join(chunk for chunk in chunks if chunk)
            return text
            
        print(f"Failed to fetch content from {url} using all available methods")
        return None
        
    except Exception as e:
        print(f"Error scraping content from {url}: {e}")
        return None

async def establish_connection(url):
    hostname = urlparse(url).hostname
    if '.gov' in hostname or 'nytimes.com':
        content = await fetch_using_proxy(url, 'RES')
        if content:
            return content
        content = await fetch_using_proxy(url, 'DC')
        if content:
            return content
        content = await fetch_using_proxy(url)  # Try Scraping Browser
        return content
    else:
        content = await fetch_using_proxy(url, 'DC')
        if content:
            return content
        content = await fetch_using_proxy(url, 'RES')
        if content:
            return content
        content = await fetch_using_proxy(url)  # Try Scraping Browser
        return content

def is_valid_http_url(url):
    try:
        parsed_url = urlparse(url)
        return all([parsed_url.scheme, parsed_url.netloc, parsed_url.scheme in ['http', 'https']])
    except ValueError:
        return False

def extract_external_links(soup, base_domain, depth):
    external_links = []
    exclude_internal_links = True
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