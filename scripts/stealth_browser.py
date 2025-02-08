import asyncio
from playwright.async_api import async_playwright, TimeoutError as PlaywrightTimeoutError
from playwright_stealth import stealth_async
import logging
from bs4 import BeautifulSoup
import random

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# List of user agents to rotate through
USER_AGENTS = [
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Edge/120.0.0.0 Safari/537.36',
    'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.2 Safari/605.1.15'
]

async def scrape_with_stealth(url, max_retries=3):
    """
    Scrape a URL using playwright with stealth mode to bypass bot detection.
    
    Args:
        url (str): The URL to scrape
        max_retries (int): Maximum number of retry attempts
        
    Returns:
        str: The page content if successful, None otherwise
    """
    logging.info(f"Attempt 1: Navigating to {url}")
    try:
        async with async_playwright() as p:
            browser = await p.chromium.launch(
                args=['--disable-blink-features=AutomationControlled']
            )
            context = await browser.new_context(
                user_agent=random.choice(USER_AGENTS),
                viewport={'width': 1920, 'height': 1080},
                java_script_enabled=True
            )
            
            page = await context.new_page()
            
            try:
                # Navigate to the page and wait for content to load
                await page.goto(url, wait_until='networkidle', timeout=30000)
                
                # Wait for the page to be fully loaded
                await page.wait_for_load_state('domcontentloaded')
                await page.wait_for_timeout(2000)
                
                # Get the title
                title = await page.title()
                
                # Extract text content using JavaScript evaluation
                text = await page.evaluate("""() => {
                    // Helper function to get text content
                    function getTextContent(element) {
                        return element.textContent.trim();
                    }
                    
                    // Find the main content container
                    const selectors = [
                        'main',
                        'article',
                        '.c-wysiwyg',
                        '.content',
                        '#content',
                        '[role="main"]',
                        '.c-wysiwyg__inner',
                        '.c-field__content'
                    ];
                    
                    let mainContent = null;
                    for (const selector of selectors) {
                        const element = document.querySelector(selector);
                        if (element) {
                            mainContent = element;
                            break;
                        }
                    }
                    
                    if (!mainContent) {
                        mainContent = document.body;
                    }
                    
                    // Get all text elements
                    const textElements = mainContent.querySelectorAll('p, h1, h2, h3, h4, h5, h6');
                    
                    // Extract and join text content
                    return Array.from(textElements)
                        .map(el => getTextContent(el))
                        .filter(text => text)
                        .join('\\n\\n');
                }""")
                
                await browser.close()
                logging.info(f"Successfully scraped content from {url}")
                return title, text
                
            except Exception as page_error:
                logging.error(f"Error during page operations: {str(page_error)}")
                raise page_error
            
    except Exception as e:
        logging.error(f"Error scraping {url}: {str(e)}")
        if max_retries > 0:
            logging.info(f"Retrying... {max_retries} attempts remaining")
            return await scrape_with_stealth(url, max_retries - 1)
        else:
            raise e

# Example usage:
if __name__ == "__main__":
    url = "https://www.cisa.gov/resources-tools/services/cisa-tabletop-exercise-packages"
    content = asyncio.run(scrape_with_stealth(url))
    if content:
        print("Successfully scraped content")
        print(f"Title: {content[0]}")
        print(f"Text: {content[1][:500]}")  # Print first 500 chars of text
    else:
        print("Failed to scrape content") 