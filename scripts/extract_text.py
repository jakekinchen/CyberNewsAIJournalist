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

load_dotenv()

def get_proxy_url():
    username = os.getenv(f'BRIGHTDATA_RES_USERNAME')
    password = os.getenv(f'BRIGHTDATA_RES_PASSWORD')
    port = os.getenv(f'BRIGHTDATA_RES_PORT')
    # Construct the proxy URL
    return f"https://{username}:{password}@brd.superproxy.io:{port}"

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

async def test_scraping_site():
   # Setup
    target_url = "https://www.npr.org/2023/10/17/1206450553/worlds-hottest-pepper-guinness-record-pepper-x"
    username = os.getenv('BRIGHTDATA_DC_USERNAME')
    password = os.getenv('BRIGHTDATA_DC_PASSWORD')
    port = os.getenv('BRIGHTDATA_DC_PORT')
    proxy_url = f"https://{username}:{password}@brd.superproxy.io:{port}"

    # Call the diagnostic function
    collect_diagnostic_info(target_url, proxy_url)

def scrape_content(url, depth=1, include_links=True, is_external=False):
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
        soup = establish_connection(url)
        if soup is None:
            raise ValueError("Unable to retrieve HTML")
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
            external_links = extract_external_links(soup, base_domain, depth)
            return content, external_links
    except Exception as error:
        print(f"Failed to scrape URL: {url}. Error: {error}")
        if include_links:
            return None, []  # Return empty list of links in case of error when include_links is True
        return None

def establish_connection(url):
    hostname = urlparse(url).hostname
    if '.gov' in hostname:
        return fetch_using_proxy(url, 'zu') or fetch_using_proxy(url, 'res') or fetch_using_proxy(url, 'sb') or fetch_using_proxy(url)
    else:
        return fetch_using_proxy(url, 'dc') or fetch_using_proxy(url, 'zu') or fetch_using_proxy(url, 'res') or fetch_using_proxy(url, 'sb') or fetch_using_proxy(url)

def fetch_using_proxy(url, proxy_type=None, verify_ssl=False):
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/58.0.3029.110 Safari/537.36'
    }

    if proxy_type:
        proxy_type = proxy_type.upper()
        username = os.getenv(f'BRIGHTDATA_{proxy_type}_USERNAME')
        password = os.getenv(f'BRIGHTDATA_{proxy_type}_PASSWORD')
        port = os.getenv(f'BRIGHTDATA_{proxy_type}_PORT')
        if not verify_ssl:
            super_proxy = f"http://{username}:{password}@brd.superproxy.io:{port}"
        else:
            super_proxy = f"https://{username}:{password}@brd.superproxy.io:{port}"
        proxies = {"http://": super_proxy, "https://": super_proxy}
    else:
        proxies = None
        proxy_type = 'no'
    
    print(f"Fetching {url} using {proxy_type} proxy")

    # Create SSL context with modern protocols
    ssl_context = ssl.create_default_context()
    ssl_context.set_ciphers('DEFAULT@SECLEVEL=2')
    ssl_context.set_alpn_protocols(['h2', 'http/1.1'])
    ssl_context.options |= ssl.OP_NO_TLSv1 | ssl.OP_NO_TLSv1_1

    BRIGHTDATA_CERT_PATH = '/usr/local/share/ca-certificates/CA-BrightData.crt'
    if os.path.exists(BRIGHTDATA_CERT_PATH):
        ssl_context.load_verify_locations(cafile=BRIGHTDATA_CERT_PATH)
    else:
        print("BrightData certificate not found!")

    # Decide on SSL verification
    if not verify_ssl or '.gov' in urlparse(url).netloc:
        verify = False
    else:
        verify = ssl_context
    
    try:
        response = httpx.get(url, proxies=proxies, headers=headers, verify=verify)
        response.raise_for_status()
        if response.status_code != 200:
            print(f"Response status code: {response.status_code}")
            print(f"Failed to fetch {url} using {proxy_type} proxy: {response.text}")
            print(f"proxies: {proxies}, headers: {headers}, verify: {verify}")
        else:
            return BeautifulSoup(response.text, 'html.parser')
    except httpx.RequestError as e:
        # If there's a TLS version mismatch error, you could potentially add a mechanism here to adapt and retry.
        print(f"Error with using {proxy_type} proxy for {url}: {e}")
        print(f"proxies: {proxies}, headers: {headers}, verify: {verify}")
        if verify is not False:
            for cert_details in verify.get_ca_certs():
                print(f"Cert Details: {cert_details}")
    
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