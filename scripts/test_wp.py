import os
import json
import httpx
from datetime import datetime
import base64
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# WordPress GraphQL endpoint
GRAPHQL_ENDPOINT = "https://cybernow.info/graphql"

def fetch_wordpress_articles(output_path="test_articles.json"):
    """
    Fetch articles from WordPress via GraphQL and save to JSON file.
    """
    try:
        # Create Basic Auth token
        wp_username = os.getenv('WP_ADMIN_USERNAME')
        wp_app_password = os.getenv('WP_APPLICATION_PASSWORD')
        
        if not wp_username or not wp_app_password:
            print("Error: WordPress credentials not found in environment variables")
            return
            
        auth_token = base64.b64encode(f"{wp_username}:{wp_app_password}".encode()).decode()

        # GraphQL query
        query = """
        query GetArticles {
          posts(first: 100, where: { status: PUBLISH }) {
            edges {
              node {
                id
                title(format: RAW)
                slug
                date
                content(format: RAW)
                excerpt(format: RAW)
                uri
                author {
                  node {
                    name
                    id
                  }
                }
                categories {
                  edges {
                    node {
                      name
                      slug
                    }
                  }
                }
                featuredImage {
                  node {
                    sourceUrl
                    altText
                    mediaDetails {
                      width
                      height
                      file
                    }
                    mediaType
                    mimeType
                  }
                }
                tags {
                  edges {
                    node {
                      name
                    }
                  }
                }
                seo {
                  title
                  metaDesc
                  twitterDescription
                  opengraphDescription
                }
              }
            }
          }
        }
        """

        # Make the request
        print("Fetching articles from WordPress...")
        response = httpx.post(
            GRAPHQL_ENDPOINT,
            json={"query": query},
            headers={
                "Content-Type": "application/json",
                "Authorization": f"Basic {auth_token}"
            }
        )
        
        response.raise_for_status()
        data = response.json()
        
        if not data or 'data' not in data or 'posts' not in data['data']:
            print(f"Error: Unexpected response format: {data}")
            return
            
        # Extract articles from response
        articles = []
        edges = data['data']['posts'].get('edges', [])
        
        print(f"Processing {len(edges)} articles...")
        
        for edge in edges:
            if not edge or 'node' not in edge:
                continue
                
            node = edge['node']
            
            # Process categories
            categories = []
            if node.get('categories', {}) and node['categories'].get('edges'):
                categories = [
                    cat['node']['name'] 
                    for cat in node['categories']['edges']
                    if cat.get('node') and cat['node'].get('name')
                ]
            
            # Process tags
            tags = []
            if node.get('tags', {}) and node['tags'].get('edges'):
                tags = [
                    tag['node']['name'] 
                    for tag in node['tags']['edges']
                    if tag.get('node') and tag['node'].get('name')
                ]
            
            # Process featured image
            featured_image = None
            if node.get('featuredImage', {}) and node['featuredImage'].get('node'):
                img = node['featuredImage']['node']
                featured_image = {
                    'url': img.get('sourceUrl'),
                    'alt': img.get('altText'),
                    'width': img.get('mediaDetails', {}).get('width'),
                    'height': img.get('mediaDetails', {}).get('height')
                }
            
            # Create article object
            article = {
                'id': node.get('id'),
                'title': node.get('title', ''),
                'slug': node.get('slug', ''),
                'date': node.get('date', ''),
                'content': node.get('content', ''),
                'excerpt': node.get('excerpt', ''),
                'uri': node.get('uri', ''),
                'author': (node.get('author', {}).get('node', {}) or {}).get('name'),
                'categories': categories,
                'tags': tags,
                'featured_image': featured_image,
                'seo': node.get('seo', {})
            }
            articles.append(article)
        
        # Save to JSON file
        output = {
            'items': articles,
            'count': len(articles),
            'fetch_date': datetime.now().isoformat()
        }
        
        with open(output_path, 'w', encoding='utf-8') as f:
            json.dump(output, f, indent=2, ensure_ascii=False)
            
        print(f"\nSuccessfully wrote {len(articles)} articles to {output_path}")
        
        # Print summary of issues found
        print("\nArticle Analysis:")
        for article in articles:
            print(f"\nAnalyzing article: {article['title']}")
            
            # Check featured image
            if not article['featured_image']:
                print("- Missing featured image")
                
            # Check tags
            if not article['tags']:
                print("- No tags assigned")
                
            # Check SEO
            meta_desc = article['seo'].get('metaDesc', '')
            if not meta_desc:
                meta_desc = article['seo'].get('opengraphDescription', '')
            if not meta_desc and 'meta' in article:
                meta_desc = article['meta'].get('yoast_wpseo_metadesc', '')
            if not meta_desc:
                print("- Missing meta description")
            elif len(meta_desc) > 155:
                print("- Meta description too long")
                
            # Check content length
            if len(article['content']) < 100:
                print("- Content appears truncated or too short")
                
            # For CVE posts, check specific requirements
            if article['title'].startswith('CVE:'):
                if not any('CVSS Score:' in article['content'] for tag in article['tags']):
                    print("- CVE post missing CVSS score")
                if not any('vulnerability' in tag.lower() for tag in article['tags']):
                    print("- CVE post missing vulnerability tags")
        
    except httpx.HTTPError as e:
        print(f"HTTP Error: {str(e)}")
    except json.JSONDecodeError as e:
        print(f"JSON Decode Error: {str(e)}")
    except Exception as e:
        print(f"Error: {str(e)}")
        import traceback
        print(traceback.format_exc())

def analyze_article(article):
    issues = []
    
    # Check for featured image
    if not article.get('featured_media'):
        issues.append('Missing featured image')
    
    # Check for tags
    if not article.get('tags'):
        issues.append('No tags assigned')
    
    # Check for meta description and SEO data
    meta = article.get('meta', {})
    has_meta_desc = False
    has_schema = False
    has_cvss = False
    
    # Check meta fields
    if isinstance(meta, dict):
        has_meta_desc = bool(meta.get('yoast_wpseo_metadesc'))
        has_schema = bool(meta.get('_yoast_wpseo_schema_article'))
    elif isinstance(meta, list):
        for item in meta:
            if isinstance(item, dict):
                key = item.get('key', '')
                value = item.get('value', '')
                if key == 'yoast_wpseo_metadesc' and value:
                    has_meta_desc = True
                elif key == '_yoast_wpseo_schema_article' and value:
                    has_schema = True
    
    if not has_meta_desc:
        issues.append('Missing meta description')
    
    # Special checks for CVE posts
    if article['title']['rendered'].startswith('CVE:'):
        content = article['content']['rendered']
        
        # Check for CVSS score
        if 'CVSS Score:' not in content:
            issues.append('CVE post missing CVSS score')
        
        # Check for schema markup
        if not has_schema:
            issues.append('CVE post missing schema markup')
        
        # Check for proper tag categories
        if article.get('tags'):
            tag_names = []
            if '_embedded' in article and 'wp:term' in article['_embedded']:
                for term_group in article['_embedded']['wp:term']:
                    for term in term_group:
                        if term.get('taxonomy') == 'post_tag':
                            tag_names.append(term['name'])
            
            security_tags = ['Security Vulnerabilities', 'CVE', 'Vulnerability Alert']
            if not any(tag in tag_names for tag in security_tags):
                issues.append('CVE post missing vulnerability tags')
    
    return issues

def test_articles():
    print("Fetching articles from WordPress...")
    articles = fetch_recent_articles()
    
    if not articles:
        print("No articles found.")
        return
    
    print(f"Processing {len(articles)} articles...\n")
    
    # Save articles to file for debugging
    with open('test_articles.json', 'w') as f:
        json.dump(articles, f, indent=2)
    print("\nSuccessfully wrote {} articles to test_articles.json\n".format(len(articles)))
    
    print("Article Analysis:\n")
    for article in articles:
        title = article['title']['rendered']
        print(f"Analyzing article: {title}")
        
        issues = analyze_article(article)
        if issues:
            for issue in issues:
                print(f"- {issue}")
        else:
            print("✓ No issues found")
        print()

if __name__ == "__main__":
    fetch_wordpress_articles() 