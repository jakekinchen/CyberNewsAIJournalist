from enhanced_scraper import EnhancedScraper
import asyncio
import argparse
from datetime import datetime
from wp_utils import create_wordpress_post, add_tag_to_wordpress
from supabase_utils import supabase

async def create_test_post(topic_id=None):
    """Create a test post using the enhanced scraper if a topic ID is provided."""
    if topic_id:
        try:
            # Get topic from Supabase
            response = supabase.table('topics').select('*').eq('id', topic_id).execute()
            if response.data:
                topic = response.data[0]
                
                # Initialize enhanced scraper
                scraper = EnhancedScraper()
                
                # Fetch content using enhanced scraper
                print(f"Fetching content from {topic['url']} using enhanced scraper...")
                content = await scraper.scrape(topic['url'])
                
                if content:
                    print(f"Successfully fetched content (length: {len(content)})")
                    # Create test post with real content
                    post_info = {
                        'title': f"Test Article: {topic['name']}",
                        'content': f"<div style='max-width:640px; margin: auto;'>{content}</div>",
                        'excerpt': topic.get('description', ''),
                        'slug': f"test-article-{topic['name'].lower().replace(' ', '-')}",
                        'status': 'publish'
                    }
                else:
                    print("Failed to fetch content, using default test content")
                    post_info = create_default_test_post()
            else:
                print(f"No topic found with ID {topic_id}")
                post_info = create_default_test_post()
        except Exception as e:
            print(f"Error creating test post from topic: {e}")
            post_info = create_default_test_post()
    else:
        post_info = create_default_test_post()
    
    # Add test tags
    test_tags = [
        'Security Testing',
        'Vulnerability Assessment',
        'Penetration Testing',
        'Security Compliance',
        'Automated Testing'
    ]
    tag_ids = []
    for tag in test_tags:
        tag_id = add_tag_to_wordpress(tag)
        if tag_id:
            tag_ids.append(tag_id)
            print(f"Created new tag '{tag}' with ID {tag_id}")
    
    # Add tags to post info
    if tag_ids:
        post_info['tags'] = tag_ids
    
    # Add to News category (ID: 42)
    post_info['categories'] = [42]
    
    # Create the post
    result = create_wordpress_post(post_info)
    if result:
        print(f"Successfully created post: {result.get('title', {}).get('rendered', 'Unknown Title')}")
        print("Post creation result:", result)
    else:
        print("Failed to create post")

def create_default_test_post():
    """Create a default test post structure."""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M")
    return {
        'title': f"Test Article: Advanced Security Testing {current_time}",
        'content': """<div style="max-width:640px; margin: auto;"><p>This is a comprehensive test article to verify all WordPress fields are operational.
        
        The article covers multiple aspects of security testing, including:
        - Automated security scanning
        - Penetration testing methodologies
        - Vulnerability assessment
        - Security compliance verification
        
        This test post ensures proper formatting, image generation, and metadata handling.</p><h2>Key Facts</h2><ul><li>Automated security testing can identify up to 80% of common vulnerabilities</li><li>Regular penetration testing is essential for maintaining strong security posture</li><li>Compliance verification should be integrated into the testing lifecycle</li><li>Modern security testing incorporates both static and dynamic analysis</li></ul></div>""",
        'excerpt': "Learn about security testing best practices including automated scanning, penetration testing, vulnerability assessment, and compliance verification.",
        'slug': f"test-article-advanced-security-testing-{datetime.now().strftime('%Y-%m-%d-%H%M')}",
        'status': 'publish'
    }

def main():
    parser = argparse.ArgumentParser(description='Create a test WordPress post')
    parser.add_argument('--topic_id', type=int, help='Topic ID to use for content')
    args = parser.parse_args()
    
    asyncio.run(create_test_post(args.topic_id))

if __name__ == "__main__":
    main() 