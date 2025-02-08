"""
Enhanced scraping module that combines multiple scraping methods with intelligent fallbacks.
"""

import os
import logging
import asyncio
from typing import Optional, Tuple, Dict, Any
from bs4 import BeautifulSoup
import httpx
from playwright.async_api import async_playwright
from urllib.parse import urlparse
import aiohttp
from dotenv import load_dotenv
import re
import traceback
from bs4.element import Tag

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Load environment variables
load_dotenv()

class ScrapingMethod:
    DIRECT = "direct"
    RESIDENTIAL_PROXY = "residential"
    DATACENTER_PROXY = "datacenter"
    SCRAPING_BROWSER = "browser"
    STEALTH_BROWSER = "stealth"

class EnhancedScraper:
    def __init__(self):
        """Initialize the enhanced scraper with proxy configurations."""
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        # Add handler if not already added
        if not self.logger.handlers:
            handler = logging.StreamHandler()
            handler.setFormatter(logging.Formatter('%(levelname)s:%(name)s:%(message)s'))
            self.logger.addHandler(handler)

        # Initialize proxy credentials
        self.proxy_configs = {
            ScrapingMethod.RESIDENTIAL_PROXY: {
                'username': os.getenv('BRIGHTDATA_RES_USERNAME'),
                'password': os.getenv('BRIGHTDATA_RES_PASSWORD'),
                'port': os.getenv('BRIGHTDATA_RES_PORT'),
            },
            ScrapingMethod.DATACENTER_PROXY: {
                'username': os.getenv('BRIGHTDATA_DC_USERNAME'),
                'password': os.getenv('BRIGHTDATA_DC_PASSWORD'),
                'port': os.getenv('BRIGHTDATA_DC_PORT'),
            },
            ScrapingMethod.SCRAPING_BROWSER: {
                'username': os.getenv('BRIGHTDATA_SB_USERNAME'),
                'password': os.getenv('BRIGHTDATA_SB_PASSWORD'),
                'port': os.getenv('BRIGHTDATA_SB_PORT'),
            }
        }
        
        # Log proxy configuration status
        for method, config in self.proxy_configs.items():
            if all(config.values()):
                self.logger.info(f"{method} proxy configuration loaded successfully")
            else:
                self.logger.warning(f"{method} proxy configuration is incomplete")
        
        # Modern user agents
        self.user_agents = [
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15',
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
            'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
        ]

    def get_proxy_url(self, proxy_type: str) -> str:
        """Get proxy URL for the specified proxy type."""
        config = self.proxy_configs.get(proxy_type)
        if not config:
            raise ValueError(f"Invalid proxy type: {proxy_type}")
        
        # Verify all required fields are present
        if not all(config.values()):
            missing = [k for k, v in config.items() if not v]
            raise ValueError(f"Missing proxy configuration for {proxy_type}: {missing}")
            
        return f"http://{config['username']}:{config['password']}@brd.superproxy.io:{config['port']}"

    async def direct_scrape(self, url: str) -> Optional[str]:
        """Attempt direct scraping without proxy."""
        try:
            async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
                headers = {
                    'User-Agent': self.user_agents[0],
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                    'Accept-Language': 'en-US,en;q=0.5',
                }
                self.logger.info(f"Attempting direct scrape of {url}")
                response = await client.get(url, headers=headers)
                self.logger.info(f"Direct scrape status code: {response.status_code}")
                
                if response.status_code == 200:
                    content = self._clean_content(response.text)
                    if content:
                        self.logger.info(f"Direct scrape successful, content length: {len(content)}")
                        return content
                    else:
                        self.logger.warning("Direct scrape returned empty content after cleaning")
                else:
                    self.logger.warning(f"Direct scrape failed with status code: {response.status_code}")
                    
        except Exception as e:
            self.logger.error(f"Direct scraping failed: {str(e)}\n{traceback.format_exc()}")
        return None

    async def proxy_scrape(self, url: str, proxy_type: str) -> Optional[str]:
        """Attempt scraping using specified proxy type."""
        try:
            proxy_url = self.get_proxy_url(proxy_type)
            self.logger.info(f"Attempting {proxy_type} proxy scrape of {url}")
            
            # Create client with proxy configuration
            async with httpx.AsyncClient(
                verify=False, 
                timeout=30.0,
                proxies=proxy_url
            ) as client:
                headers = {
                    'User-Agent': self.user_agents[1],
                    'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                }
                response = await client.get(url, headers=headers)
                self.logger.info(f"{proxy_type} proxy scrape status code: {response.status_code}")
                
                if response.status_code == 200:
                    content = self._clean_content(response.text)
                    if content:
                        self.logger.info(f"{proxy_type} proxy scrape successful, content length: {len(content)}")
                        return content
                    else:
                        self.logger.warning(f"{proxy_type} proxy scrape returned empty content after cleaning")
                else:
                    self.logger.warning(f"{proxy_type} proxy scrape failed with status code: {response.status_code}")
                    
        except Exception as e:
            self.logger.error(f"{proxy_type} proxy scraping failed: {str(e)}\n{traceback.format_exc()}")
        return None

    async def browser_scrape(self, url: str) -> Optional[str]:
        """Scrape content using Playwright browser."""
        try:
            self.logger.info("Attempting browser scrape with Playwright")
            
            # Launch browser with stealth mode
            browser = await self.get_browser()
            context = await browser.new_context(
                viewport={'width': 1920, 'height': 1080},
                user_agent='Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
            )
            
            # Add extra headers
            await context.set_extra_http_headers({
                'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8',
                'Accept-Language': 'en-US,en;q=0.5',
                'Accept-Encoding': 'gzip, deflate, br',
                'DNT': '1',
                'Connection': 'keep-alive',
                'Upgrade-Insecure-Requests': '1',
                'Sec-Fetch-Dest': 'document',
                'Sec-Fetch-Mode': 'navigate',
                'Sec-Fetch-Site': 'none',
                'Sec-Fetch-User': '?1',
                'Pragma': 'no-cache',
                'Cache-Control': 'no-cache',
            })

            page = await context.new_page()
            
            # Enable request interception
            await page.route("**/*", lambda route: route.continue_())
            
            try:
                # Navigate with longer timeout and wait for network idle
                self.logger.info("Navigating to page and waiting for load")
                await page.goto(url, wait_until='networkidle', timeout=60000)
                
                # Wait for content to load
                self.logger.info("Waiting for content selectors")
                await page.wait_for_selector('article, .post-content, .articlebody', timeout=10000)
                
                # Take screenshot for debugging
                await page.screenshot(path='debug_screenshot.png')
                
                # Save page source for debugging
                content = await page.content()
                with open('debug_page.html', 'w', encoding='utf-8') as f:
                    f.write(content)
                    
                # Extract content using JavaScript evaluation
                article_content = await page.evaluate('''() => {
                    const article = document.querySelector('article') || 
                                  document.querySelector('.post-content') || 
                                  document.querySelector('.articlebody');
                    return article ? article.innerHTML : null;
                }''')
                
                if not article_content:
                    self.logger.warning("No article content found after JavaScript execution")
                    return None
                    
                self.logger.info(f"Successfully extracted content with length: {len(article_content)}")
                return article_content

            except Exception as e:
                self.logger.error(f"Error during page navigation/content extraction: {str(e)}")
                return None
                
            finally:
                await page.close()
                await context.close()
                await browser.close()
                
        except Exception as e:
            self.logger.error(f"Browser scraping failed: {str(e)}")
            return None

    def _clean_content(self, content: str) -> str:
        """Clean and normalize scraped content."""
        if not content:
            self.logger.warning("Received empty content for cleaning")
            return ""
            
        try:
            soup = BeautifulSoup(content, 'html.parser')
            
            # Remove unwanted elements
            for element in soup.find_all(['script', 'style', 'nav', 'footer', 'iframe', 'header', 'aside', 'form']):
                element.decompose()
            
            # Try multiple approaches to find the main content
            main_content = None
            
            # 1. Try article-specific elements first
            for selector in ['article', '.post-content', '.article-content', '.entry-content', '#content', '.blog-post', '.post']:
                if selector.startswith('.'):
                    main_content = soup.find(class_=selector[1:])
                elif selector.startswith('#'):
                    main_content = soup.find(id=selector[1:])
                else:
                    main_content = soup.find(selector)
                    
                if main_content:
                    self.logger.info(f"Found main content using selector: {selector}")
                    break
            
            # 2. If no specific article element found, try the largest text container
            if not main_content:
                # Find all potential content divs
                content_divs = soup.find_all(['div', 'section', 'main'])
                if content_divs:
                    # Get the div with the most text content
                    main_content = max(content_divs, key=lambda div: len(div.get_text(strip=True)))
                    self.logger.info("Using largest text container as main content")
            
            # 3. If still no content, use the body
            if not main_content:
                main_content = soup.find('body') or soup
                self.logger.info("Using body/entire document as main content")
            
            if main_content:
                # Extract text with better formatting preservation
                paragraphs = []
                if isinstance(main_content, Tag):  # Only process Tag objects, not NavigableString
                    for elem in main_content.find_all(['p', 'h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'li']):
                        text = elem.get_text(strip=True)
                        if text:  # Only add non-empty paragraphs
                            paragraphs.append(text)
                else:
                    # Handle NavigableString directly
                    text = str(main_content).strip()
                    if text:
                        paragraphs.append(text)
                
                # Join paragraphs with proper spacing
                text = '\n\n'.join(paragraphs)
                
                # Clean up whitespace while preserving paragraph breaks
                text = re.sub(r'\s+', ' ', text)  # Replace multiple spaces with single space
                text = re.sub(r'\n\s*\n', '\n\n', text)  # Normalize paragraph breaks
                text = text.strip()
                
                if text:
                    self.logger.info(f"Successfully cleaned content, length: {len(text)}")
                    self.logger.debug("First 200 characters of cleaned content:")
                    self.logger.debug(text[:200] + "...")
                    return text
                else:
                    self.logger.warning("Cleaning resulted in empty content")
                    return ""
            else:
                self.logger.warning("No content elements found")
                return ""
                
        except Exception as e:
            self.logger.error(f"Content cleaning failed: {str(e)}\n{traceback.format_exc()}")
            return ""

    async def scrape(self, url: str, max_retries: int = 3) -> Optional[str]:
        """
        Main scraping method that tries different approaches in sequence.
        Returns the first successful result.
        """
        for attempt in range(max_retries):
            self.logger.info(f"Starting scraping attempt {attempt + 1} of {max_retries} for {url}")
            
            # Try browser scraping first for JavaScript-heavy sites
            content = await self.browser_scrape(url)
            if content and len(content.strip()) >= 100:
                self.logger.info("Browser scraping successful")
                return content
            
            # Try direct scraping
            content = await self.direct_scrape(url)
            if content and len(content.strip()) >= 100:
                self.logger.info("Direct scraping successful")
                return content
                
            # Try residential proxy
            content = await self.proxy_scrape(url, ScrapingMethod.RESIDENTIAL_PROXY)
            if content and len(content.strip()) >= 100:
                self.logger.info("Residential proxy scraping successful")
                return content
                
            # Try datacenter proxy
            content = await self.proxy_scrape(url, ScrapingMethod.DATACENTER_PROXY)
            if content and len(content.strip()) >= 100:
                self.logger.info("Datacenter proxy scraping successful")
                return content
                
            self.logger.warning(f"All scraping methods failed on attempt {attempt + 1}")
            if attempt < max_retries - 1:
                delay = 2 ** attempt
                self.logger.info(f"Waiting {delay} seconds before next attempt")
                await asyncio.sleep(delay)  # Exponential backoff
                
        self.logger.error(f"Failed to scrape {url} after {max_retries} attempts")
        return None

    async def get_browser(self):
        """Get a configured browser instance."""
        try:
            browser = await async_playwright().chromium.launch(
                headless=True,
                args=[
                    '--no-sandbox',
                    '--disable-setuid-sandbox',
                    '--disable-dev-shm-usage',
                    '--disable-accelerated-2d-canvas',
                    '--disable-gpu',
                    '--window-size=1920,1080',
                ]
            )
            return browser
        except Exception as e:
            self.logger.error(f"Failed to launch browser: {str(e)}")
            raise

# Example usage
async def main():
    scraper = EnhancedScraper()
    url = "https://example.com"
    content = await scraper.scrape(url)
    if content:
        print("Successfully scraped content")
        print(f"Content length: {len(content)}")
    else:
        print("Failed to scrape content")

if __name__ == "__main__":
    asyncio.run(main()) 