import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
import logging
import random
from bs4 import BeautifulSoup
import traceback
import aiohttp
import json
from typing import Optional, Tuple, List, Dict

# Configure logging with more detail
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# List of modern user agents
USER_AGENTS = [
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
]

async def get_free_proxies() -> List[Dict[str, str]]:
    """Fetch a list of free proxies from public proxy lists."""
    logger.info("Fetching free proxies...")
    proxies = []
    
    async with aiohttp.ClientSession() as session:
        try:
            # Try multiple proxy sources
            sources = [
                'https://proxylist.geonode.com/api/proxy-list?limit=100&page=1&sort_by=lastChecked&sort_type=desc&protocols=http%2Chttps',
                'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
                'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt'
            ]
            
            for source in sources:
                try:
                    async with session.get(source, timeout=10) as response:
                        if response.status == 200:
                            if 'api/proxy-list' in source:
                                # Handle GeoNode format
                                data = await response.json()
                                for proxy in data.get('data', []):
                                    if proxy.get('protocols') and 'http' in proxy['protocols']:
                                        proxies.append({
                                            'server': f"http://{proxy['ip']}:{proxy['port']}"
                                        })
                            else:
                                # Handle plain text format (ip:port)
                                text = await response.text()
                                for line in text.split('\n'):
                                    if line.strip():
                                        ip, port = line.strip().split(':')
                                        proxies.append({
                                            'server': f"http://{ip}:{port}"
                                        })
                except Exception as e:
                    logger.warning(f"Error fetching from {source}: {str(e)}")
                    continue
                
                if proxies:
                    break  # Stop if we have proxies from any source
                
        except Exception as e:
            logger.error(f"Error fetching proxies: {str(e)}")
    
    if not proxies:
        # Fallback to a default list if no proxies could be fetched
        default_proxies = [
            {'server': 'http://34.23.45.223:80'},
            {'server': 'http://165.227.71.60:80'},
            {'server': 'http://157.245.27.9:3128'},
            {'server': 'http://157.245.207.190:8080'}
        ]
        proxies.extend(default_proxies)
    
    logger.info(f"Found {len(proxies)} proxies")
    return proxies

async def test_proxy(session: aiohttp.ClientSession, proxy: Dict[str, str]) -> bool:
    """Test if a proxy is working by making a request to a test URL."""
    try:
        test_url = 'http://httpbin.org/ip'
        timeout = aiohttp.ClientTimeout(total=5)
        async with session.get(test_url, proxy=proxy['server'], timeout=timeout) as response:
            if response.status == 200:
                return True
    except Exception as e:
        logger.debug(f"Proxy test failed for {proxy['server']}: {str(e)}")
    return False

async def get_working_proxy() -> Optional[Dict[str, str]]:
    """Get a working proxy from the list of available proxies."""
    logger.info("Finding a working proxy...")
    
    async with aiohttp.ClientSession() as session:
        try:
            # Get list of proxies
            proxies = await get_free_proxies()
            if not proxies:
                logger.error("No proxies available")
                return None
            
            # Shuffle proxies to avoid always testing in the same order
            random.shuffle(proxies)
            
            # Test proxies in parallel (up to 10 at a time)
            tasks = []
            for proxy in proxies[:10]:  # Test first 10 proxies
                task = asyncio.create_task(test_proxy(session, proxy))
                tasks.append((proxy, task))
            
            # Wait for results
            for proxy, task in tasks:
                try:
                    is_working = await task
                    if is_working:
                        logger.info(f"Found working proxy: {proxy['server']}")
                        return proxy
                except Exception as e:
                    logger.debug(f"Error testing proxy {proxy['server']}: {str(e)}")
                    continue
            
            logger.warning("No working proxies found")
            return None
            
        except Exception as e:
            logger.error(f"Error finding working proxy: {str(e)}")
            return None

async def scrape_thn_article(url, max_retries=3, current_retry=0):
    """
    Specialized scraper for TheHackersNews articles with improved handling of their site structure.
    """
    if current_retry >= max_retries:
        logger.error(f"Max retries ({max_retries}) reached for {url}")
        return None, None

    logger.info(f"Attempting to scrape THN article (attempt {current_retry + 1}): {url}")
    
    try:
        async with async_playwright() as p:
            # Try without proxy first
            try:
                browser = await p.firefox.launch(  # Use Firefox instead of Chrome
                    headless=True,
                    firefox_user_prefs={
                        'general.useragent.override': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:122.0) Gecko/20100101 Firefox/122.0',
                        'privacy.trackingprotection.enabled': False,
                        'network.http.referer.spoofSource': True,
                        'network.cookie.cookieBehavior': 0,
                        'permissions.default.image': 2  # Disable images for faster loading
                    },
                    args=[
                        '--disable-blink-features=AutomationControlled',
                        '--disable-dev-shm-usage',
                        '--no-sandbox',
                        '--disable-setuid-sandbox'
                    ]
                )
                logger.info("Browser launched successfully without proxy")
            except Exception as e:
                logger.error(f"Failed to launch browser without proxy: {e}")
                return None, None

            # Create a context with specific viewport and user agent
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                extra_http_headers={
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                    'Accept-Encoding': 'gzip, deflate, br',
                    'DNT': '1',
                    'Connection': 'keep-alive',
                    'Upgrade-Insecure-Requests': '1',
                    'Sec-Fetch-Dest': 'document',
                    'Sec-Fetch-Mode': 'navigate',
                    'Sec-Fetch-Site': 'none',
                    'Sec-Fetch-User': '?1'
                }
            )
            logger.info("Browser context created successfully")

            # Create a new page
            page = await context.new_page()
            logger.info("New page created")

            # Add script to modify navigator.webdriver
            await page.add_init_script("""
                Object.defineProperty(navigator, 'webdriver', {
                    get: () => undefined
                });
                Object.defineProperty(navigator, 'plugins', {
                    get: () => [1, 2, 3, 4, 5]
                });
                Object.defineProperty(navigator, 'languages', {
                    get: () => ['en-US', 'en']
                });
                Object.defineProperty(screen, 'colorDepth', {
                    get: () => 24
                });
            """)

            # Navigate to the URL with a less strict wait strategy
            logger.info(f"Navigating to {url}")
            try:
                response = await page.goto(url, wait_until='domcontentloaded', timeout=60000)  # Increased timeout
                if not response:
                    logger.error("No response received from the server")
                    return None, None
                if response.status >= 400:
                    logger.error(f"Received error status code: {response.status}")
                    return None, None
                logger.info("Initial page load complete")
            except Exception as e:
                logger.error(f"Error during navigation: {str(e)}")
                return None, None

            # Wait for content to be loaded with increased timeout
            try:
                await page.wait_for_load_state('domcontentloaded', timeout=60000)
                # Take a screenshot for debugging
                await page.screenshot(path='debug_screenshot.png')
                logger.info("Saved debug screenshot")
                
                # Get the page content
                html_content = await page.content()
                logger.info(f"Page HTML length: {len(html_content)}")
                
                # Save HTML for debugging
                with open('debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(html_content)
                logger.info("Saved debug HTML")
                
                # Parse with BeautifulSoup
                soup = BeautifulSoup(html_content, 'html.parser')
                
                # Log available classes in the HTML
                all_classes = set()
                for tag in soup.find_all(class_=True):
                    all_classes.update(tag.get('class', []))
                logger.info(f"Available classes in HTML: {sorted(all_classes)}")
                
                # Try to find the article content with broader selectors
                article = soup.find('article') or \
                         soup.find('div', class_='post-container') or \
                         soup.find('div', class_='blog-post') or \
                         soup.find('div', class_='post') or \
                         soup.find('div', {'id': 'articlebody'})
                
                if article:
                    logger.info(f"Found article element with classes: {article.get('class', [])}")
                    
                    # Get title
                    title_elem = article.find('h1') or \
                                soup.find('h1')  # Try finding h1 anywhere if not in article
                    title = title_elem.get_text(strip=True) if title_elem else ''
                    
                    if title:
                        logger.info(f"Found title: {title[:50]}...")
                    
                    # Get content - try multiple approaches
                    content = ''
                    
                    # First try: specific content divs
                    content_elem = article.find('div', class_=['articlebody', 'article-content', 'post-content', 'entry-content'])
                    if content_elem:
                        content = content_elem.get_text(strip=True)
                        logger.info("Found content using specific div classes")
                    
                    # Second try: all paragraphs in article
                    if not content or len(content) < 100:
                        paragraphs = article.find_all('p')
                        content = '\n\n'.join(p.get_text(strip=True) for p in paragraphs if p.get_text(strip=True))
                        if content:
                            logger.info("Found content using paragraphs")
                    
                    # Third try: all text in article
                    if not content or len(content) < 100:
                        content = article.get_text(strip=True)
                        logger.info("Using all text in article")
                    
                    if content and len(content) >= 100:
                        logger.info(f"Successfully scraped article. Title length: {len(title)}, Content length: {len(content)}")
                        return title, content
                    else:
                        logger.warning(f"Retrieved content too short (length: {len(content) if content else 0})")
                else:
                    logger.warning("Could not find article element")
                    # Log the first level of HTML structure
                    body = soup.find('body')
                    if body:
                        first_level = [f"{tag.name}({','.join(tag.get('class', []))}" for tag in body.find_all(recursive=False)]
                        logger.info(f"First level HTML structure: {first_level}")
                
                return None, None
                
            except Exception as e:
                logger.error(f"Error extracting content: {str(e)}")
                return None, None
                
    except Exception as e:
        logger.error(f"Critical error: {str(e)}")
        logger.error(traceback.format_exc())
        return None, None

# Example usage
if __name__ == "__main__":
    test_url = "https://thehackernews.com/2025/02/ai-powered-social-engineering.html"
    title, content = asyncio.run(scrape_thn_article(test_url))
    if content:
        print("Successfully scraped THN article")
        print(f"Title: {title}")
        print(f"Content preview: {content[:500]}")
    else:
        print("Failed to scrape THN article") 