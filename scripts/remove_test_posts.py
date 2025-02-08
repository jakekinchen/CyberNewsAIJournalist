import json
from wp_utils import delete_wp_post
from supabase_utils import delete_supabase_post
import asyncio

def load_test_articles():
    """Load test articles from test_articles.json"""
    try:
        with open('test_articles.json', 'r') as f:
            data = json.load(f)
            return data.get('items', [])
    except FileNotFoundError:
        print("test_articles.json not found")
        return []
    except json.JSONDecodeError:
        print("Error parsing test_articles.json")
        return []

async def remove_test_posts():
    """Remove posts that are clearly test articles"""
    articles = load_test_articles()
    removed_count = 0
    
    for article in articles:
        # Check if it's a test article by title
        title = article.get('title', {}).get('rendered', '') if isinstance(article.get('title'), dict) else str(article.get('title', ''))
        if title.lower().startswith('test article:'):
            wp_id = article['id']
            print(f"Removing test article: {title}")
            
            # Remove from WordPress
            delete_wp_post(wp_id)
            
            # If there's a topic_id associated, remove from Supabase too
            if 'topic_id' in article:
                await delete_supabase_post(article['topic_id'])
            
            removed_count += 1
    
    print(f"\nRemoved {removed_count} test articles")

def main():
    """Main function to run the removal process"""
    print("Starting test post removal process...")
    asyncio.run(remove_test_posts())
    print("Process completed!")

if __name__ == "__main__":
    main() 