from enhanced_scraper import EnhancedScraper
import asyncio

async def test_scrape():
    scraper = EnhancedScraper()
    url = 'https://thehackernews.com/2025/02/deepseek-app-transmits-sensitive-user.html'
    print('Starting scrape attempt...')
    content = await scraper.scrape(url)
    if content:
        print(f'\nSuccessfully scraped content. Length: {len(content)}')
        print('\nFirst 500 characters of content:')
        print(content[:500])
    else:
        print('\nFailed to scrape content')

if __name__ == "__main__":
    asyncio.run(test_scrape()) 