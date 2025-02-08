import json
import httpx
from wp_utils import BASE_URL, HEADERS
import os
import time

def fetch_posts_with_retry(endpoint, max_retries=3, initial_timeout=30):
    """Fetch posts with retry logic and increasing timeouts"""
    for attempt in range(max_retries):
        timeout = initial_timeout * (attempt + 1)
        try:
            print(f"Attempt {attempt + 1} with {timeout}s timeout...")
            response = httpx.get(
                f"{BASE_URL}/{endpoint}",
                headers=HEADERS,
                timeout=timeout
            )
            if response.status_code == 200:
                return response.json()
            else:
                print(f"Failed to fetch posts: {response.text}")
        except httpx.TimeoutException:
            print(f"Timeout after {timeout}s")
            if attempt < max_retries - 1:
                time.sleep(2)  # Wait before retrying
                continue
        except Exception as e:
            print(f"Error: {e}")
            if attempt < max_retries - 1:
                time.sleep(2)
                continue
    return None

def refresh_articles_json():
    """Fetch all posts from WordPress and update test_articles.json"""
    print("Fetching posts from WordPress...")
    
    # Fetch all posts with necessary fields
    endpoint = "posts?per_page=100&_fields=id,title,content,excerpt,slug,featured_media,status,tags,categories,date,modified,link,author"
    posts = fetch_posts_with_retry(endpoint)
    
    if not posts:
        print("No posts found or error fetching posts")
        return
    
    # Create the articles data structure
    articles_data = {
        "items": posts
    }
    
    # Save to test_articles.json
    try:
        with open('test_articles.json', 'w') as f:
            json.dump(articles_data, f, indent=2)
        print(f"Successfully updated test_articles.json with {len(posts)} posts")
        
        # Print the first post's title as verification
        if posts:
            first_post = posts[0]
            if isinstance(first_post, dict):
                title = first_post.get('title', {}).get('rendered', 'No title')
                print(f"\nFirst post title: {title}")
    except Exception as e:
        print(f"Error saving to test_articles.json: {e}")

if __name__ == "__main__":
    refresh_articles_json() 