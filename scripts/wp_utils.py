import os
import json
import httpx
import csv
import base64
from bs4 import BeautifulSoup
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from scripts.table_structures import wp_post_table
from urllib.parse import urlparse
import pytz
from dateutil.parser import parse
import re
import io
import traceback

# Load .env file
load_dotenv()

# Load the post fields from the table structures
post_fields = wp_post_table

# Access WordPress credentials
wp_username = os.getenv('WP_ADMIN_USERNAME')
wp_app_password = os.getenv('WP_APPLICATION_PASSWORD')

# Base URL for WordPress REST API
BASE_URL = "https://cybernow.info/wp-json/wp/v2"

# Create Basic Auth token for WordPress
auth_token = base64.b64encode(f"{wp_username}:{wp_app_password}".encode()).decode()

# Headers for WordPress REST API
HEADERS = {
    'Authorization': f'Basic {auth_token}'
}

def get_wp_id_from_slug(slug):
    posts = fetch_from_wp_api(f"posts?slug={slug}")
    if not posts:
        print(f"No post found for slug: {slug}")
        return None
    return posts[0]["id"]

# Delete wp posts with wp

def delete_wp_post(wp_id):
    """Delete a WordPress post by ID."""
    # Convert base64 ID to numeric ID if needed
    try:
        if isinstance(wp_id, str) and wp_id.startswith('cG9zdDo'):
            # This is a base64 encoded ID, decode it
            decoded = base64.b64decode(wp_id).decode('utf-8')
            # Extract numeric ID
            numeric_id = int(''.join(filter(str.isdigit, decoded)))
        else:
            numeric_id = int(wp_id)
    except (ValueError, TypeError) as e:
        print(f"Invalid post ID format: {wp_id}")
        return None

    url = f"{BASE_URL}/posts/{numeric_id}"
    
    # Try up to 3 times with increasing timeouts
    timeouts = [10, 20, 30]  # seconds
    for timeout in timeouts:
        try:
            response = httpx.delete(url, headers=HEADERS, timeout=timeout)
            if response.status_code == 200:
                print(f"Successfully deleted post with ID {numeric_id}")
                return response.json()
            else:
                print(f"Failed to delete post: {response.text}")
                return None
        except httpx.TimeoutException:
            print(f"Timeout after {timeout}s, retrying with longer timeout...")
            continue
        except Exception as e:
            print(f"Failed to delete post: {e}")
            return None
    
    print(f"Failed to delete post {numeric_id} after all retries")
    return None

def update_wp_post(post_info):
    # Get the wordpress id from the slug
    wp_id = get_wp_id_from_slug(post_info['slug'])
    # Update the wordpress post
    headers = {
        'Authorization': f'Basic {auth_token}',
        'Content-Type': 'application/json'
    }
    url = f"{BASE_URL}/posts/{wp_id}"
    try:
        post_info = type_check_post_info(post_info)
    except Exception as e:
        print(f"Failed to type check post info: {e}")
        return
    try:
        response = httpx.post(url, json=post_info, headers=headers)
        if response.status_code != 200:
            print(f"Failed to update post: {response.text}")
            return
    except Exception as e:
        print(f"Failed to update post: {e}")
        return
    print(f"Successfully updated post with id {wp_id}.")
    return response.json()

def type_check_post_info(post_info):
    """Ensure all post data fields are of the correct type and properly filled."""
    if not isinstance(post_info, dict):
        raise ValueError("post_info must be a dictionary")

    # Required fields check
    required_fields = ['title', 'content', 'status', 'slug']
    missing_fields = [field for field in required_fields if field not in post_info]
    if missing_fields:
        raise ValueError(f"Missing required fields: {', '.join(missing_fields)}")

    # Handle title
    if isinstance(post_info['title'], dict):
        post_info['title'] = post_info['title'].get('rendered', '')
    post_info['title'] = str(post_info['title']).strip()
    if not post_info['title']:
        raise ValueError("Title cannot be empty")

    # Handle content
    if isinstance(post_info['content'], dict):
        post_info['content'] = post_info['content'].get('rendered', '')
    post_info['content'] = str(post_info['content']).strip()
    if not post_info['content']:
        raise ValueError("Content cannot be empty")

    # Handle excerpt
    if 'excerpt' in post_info:
        if isinstance(post_info['excerpt'], dict):
            post_info['excerpt'] = post_info['excerpt'].get('rendered', '')
        post_info['excerpt'] = str(post_info['excerpt']).strip()
        if not post_info['excerpt']:
            # Generate excerpt from content if empty
            content_text = BeautifulSoup(post_info['content'], 'html.parser').get_text()
            post_info['excerpt'] = content_text[:150] + '...' if len(content_text) > 150 else content_text

    # Handle slug
    post_info['slug'] = str(post_info['slug']).strip().lower()
    if not post_info['slug']:
        raise ValueError("Slug cannot be empty")

    # Handle status
    valid_statuses = ['draft', 'publish', 'private', 'pending']
    post_info['status'] = str(post_info['status']).lower()
    if post_info['status'] not in valid_statuses:
        post_info['status'] = 'draft'  # Default to draft if invalid

    # Handle featured_media
    if 'featured_media' in post_info:
        try:
            post_info['featured_media'] = int(post_info['featured_media'])
        except (TypeError, ValueError):
            # If it's not a valid integer, remove it
            post_info.pop('featured_media')

    # Handle meta
    if 'meta' in post_info:
        if not isinstance(post_info['meta'], dict):
            post_info['meta'] = {}
        # Ensure all meta values are strings
        post_info['meta'] = {k: str(v) for k, v in post_info['meta'].items()}

    # Handle yoast_meta
    if 'yoast_meta' in post_info:
        if not isinstance(post_info['yoast_meta'], dict):
            post_info['yoast_meta'] = {}
        # Ensure all yoast_meta values are strings
        post_info['yoast_meta'] = {k: str(v) for k, v in post_info['yoast_meta'].items()}
        
        # Set default meta description if missing
        if 'yoast_wpseo_metadesc' not in post_info['yoast_meta']:
            content_text = BeautifulSoup(post_info['content'], 'html.parser').get_text()
            post_info['yoast_meta']['yoast_wpseo_metadesc'] = content_text[:150] + '...' if len(content_text) > 150 else content_text

    # Handle tags and categories
    for field in ['tags', 'categories']:
        if field in post_info:
            if not isinstance(post_info[field], list):
                post_info[field] = []
            # Ensure all IDs are integers
            post_info[field] = [int(item) for item in post_info[field] if str(item).isdigit()]

    # Handle date fields
    for date_field in ['date', 'date_gmt']:
        if date_field in post_info:
            if not isinstance(post_info[date_field], str):
                post_info.pop(date_field)
            else:
                try:
                    # Validate date format
                    datetime.strptime(post_info[date_field], "%Y-%m-%dT%H:%M:%S")
                except ValueError:
                    post_info.pop(date_field)

    return post_info

def add_tag_to_wordpress(tag):
    """Add a tag to WordPress and return its ID."""
    # Fetch the tags
    tags_endpoint = f"{BASE_URL}/tags"
    headers = {
        'Authorization': f'Basic {auth_token}',
        'Content-Type': 'application/json'
    }

    # Check if the tag already exists
    response = httpx.get(f"{tags_endpoint}?search={tag}", headers=headers)
    if response.status_code == 200:
        tags = response.json()
        for existing_tag in tags:
            if existing_tag['name'].lower() == tag.lower():
                print(f"Tag '{tag}' already exists with ID {existing_tag['id']}")
                return existing_tag['id']
    
    # Create the tag
    payload = {
        'name': tag,
        'description': f'Articles related to {tag}',
        'slug': tag.lower().replace(' ', '-')
    }
    response = httpx.post(tags_endpoint, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"Created tag '{tag}' with ID {response.json()['id']}")
        return response.json()['id']
    else:
        print(f"Failed to create tag '{tag}': {response.text}")
        return None

def upload_media_to_wordpress(image_data, title=None, alt_text=None):
    """Upload media to WordPress and return the media ID."""
    media_endpoint = f"{BASE_URL}/media"
    
    try:
        # Convert base64 to bytes if needed
        if isinstance(image_data, str):
            try:
                image_data = base64.b64decode(image_data)
            except Exception as e:
                print(f"Error decoding base64 image: {e}")
                return None
        
        # Generate a unique filename
        timestamp = datetime.now().timestamp()
        filename = f"featured-image-{timestamp}.png"
        
        # Create the request with proper headers
        headers = {
            'Authorization': f'Basic {auth_token}',
            'Content-Type': 'image/png',
            'Content-Disposition': f'attachment; filename="{filename}"'
        }
        
        # Make the request with proper error handling
        try:
            response = httpx.post(
                media_endpoint,
                headers=headers,
                content=image_data,
                timeout=30.0  # Add timeout
            )
            
            if response.status_code == 201:
                media_id = response.json()['id']
                print(f"Successfully uploaded media with ID: {media_id}")
                
                # Update media metadata if provided
                if title or alt_text:
                    update_data = {}
                    if title:
                        update_data['title'] = title
                    if alt_text:
                        update_data['alt_text'] = alt_text
                        
                    if update_data:
                        update_headers = {
                            'Authorization': f'Basic {auth_token}',
                            'Content-Type': 'application/json'
                        }
                        update_response = httpx.post(
                            f"{media_endpoint}/{media_id}",
                            headers=update_headers,
                            json=update_data,
                            timeout=30.0
                        )
                        if update_response.status_code != 200:
                            print(f"Warning: Failed to update media metadata: {update_response.text}")
                
                return media_id
            else:
                print(f"Failed to upload media. Status code: {response.status_code}")
                print(f"Response: {response.text}")
                return None
                
        except httpx.TimeoutException:
            print("Timeout while uploading media")
            return None
        except httpx.RequestError as e:
            print(f"Request error while uploading media: {e}")
            return None
            
    except Exception as e:
        print(f"Error uploading media: {e}")
        print("Full traceback:")
        print(traceback.format_exc())
        return None

def validate_post_data(post_info):
    """Validate and sanitize post data before creation."""
    if post_info is None:
        raise ValueError("post_info is None")
        
    required_fields = ['title', 'content', 'status']
    for field in required_fields:
        if field not in post_info:
            raise ValueError(f"Missing required field: {field}")
            
    # Ensure title is a string
    if isinstance(post_info['title'], dict):
        post_info['title'] = post_info['title'].get('rendered', '')
    elif not isinstance(post_info['title'], str):
        post_info['title'] = str(post_info['title'])
        
    # Ensure content is a string
    if isinstance(post_info['content'], dict):
        post_info['content'] = post_info['content'].get('rendered', '')
    elif not isinstance(post_info['content'], str):
        post_info['content'] = str(post_info['content'])
        
    # Handle meta fields
    if 'meta' in post_info:
        if not isinstance(post_info['meta'], dict):
            post_info['meta'] = {}
            
    # Handle yoast_meta
    if 'yoast_meta' in post_info:
        if not isinstance(post_info['yoast_meta'], dict):
            post_info['yoast_meta'] = {}
        for key, value in post_info['yoast_meta'].items():
            if not isinstance(value, str):
                post_info['yoast_meta'][key] = str(value)
                
    # Handle featured_media
    if 'featured_media' in post_info:
        if isinstance(post_info['featured_media'], str):
            try:
                # Try to decode if it's base64
                base64.b64decode(post_info['featured_media'])
            except:
                # If it's not base64, try to convert to int
                try:
                    post_info['featured_media'] = int(post_info['featured_media'])
                except:
                    del post_info['featured_media']
                    
    return post_info

def create_wordpress_post(post_info, immediate_post=True, delay_hours=1):
    """Create a new WordPress post with improved error handling."""
    try:
        # Validate and sanitize post data
        post_info = validate_post_data(post_info)
        if not post_info:
            return None
            
        # Set up the endpoint and headers
        post_endpoint = f"{BASE_URL}/posts"
        headers = {
            'Authorization': f'Basic {auth_token}',
            'Content-Type': 'application/json'
        }
        
        # Handle duplicate slugs
        original_slug = post_info['slug']
        counter = 1
        while True:
            # Check if slug exists
            existing_post = fetch_from_wp_api(f"posts?slug={post_info['slug']}")
            if not existing_post:
                break
            # Append counter to slug
            post_info['slug'] = f"{original_slug}-{counter}"
            counter += 1

        # Adjust post time
        central_tz = pytz.timezone('America/Chicago')
        if immediate_post:
            post_time = datetime.now(central_tz)
        else:
            post_time = datetime.now(central_tz) + timedelta(hours=delay_hours)
            
        # Setting the date fields
        post_info['date'] = post_time.strftime("%Y-%m-%dT%H:%M:%S")
        post_info['date_gmt'] = post_time.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S")
        post_info['status'] = 'publish'
        
        # Handle meta fields
        meta_data = {}
        
        # Get meta description from various possible sources
        meta_desc = None
        if post_info.get('yoast_meta', {}).get('yoast_wpseo_metadesc'):
            meta_desc = post_info['yoast_meta']['yoast_wpseo_metadesc']
        elif post_info.get('meta', {}).get('yoast_wpseo_metadesc'):
            meta_desc = post_info['meta']['yoast_wpseo_metadesc']
        elif post_info.get('seo', {}).get('metaDesc'):
            meta_desc = post_info['seo']['metaDesc']
        elif post_info.get('excerpt'):
            meta_desc = post_info['excerpt']
            
        if meta_desc:
            # Set in yoast_meta
            if 'yoast_meta' not in post_info:
                post_info['yoast_meta'] = {}
            post_info['yoast_meta'].update({
                'yoast_wpseo_metadesc': meta_desc,
                '_yoast_wpseo_metadesc': meta_desc,
                'yoast_wpseo_opengraph-description': meta_desc,
                'yoast_wpseo_twitter-description': meta_desc
            })
            
            # Set in meta
            if 'meta' not in post_info:
                post_info['meta'] = {}
            post_info['meta'].update({
                'yoast_wpseo_metadesc': meta_desc,
                '_yoast_wpseo_metadesc': meta_desc,
                'yoast_wpseo_opengraph-description': meta_desc,
                'yoast_wpseo_twitter-description': meta_desc
            })
            
            # Set in SEO object
            if 'seo' not in post_info:
                post_info['seo'] = {}
            post_info['seo'].update({
                'metaDesc': meta_desc,
                'twitterDescription': meta_desc,
                'opengraphDescription': meta_desc
            })
            
        # Handle SEO metadata
        if post_info.get('yoast_meta'):
            for key, value in post_info['yoast_meta'].items():
                meta_data[key] = str(value)  # Ensure all meta values are strings
            
            # Add schema metadata for better SEO
            title = post_info.get('title', '')
            if isinstance(title, dict):
                title = title.get('rendered', '')
            elif not isinstance(title, str):
                title = str(title)
                
            if title.startswith('CVE:'):
                # Extract CVSS score and severity from content
                content = post_info.get('content', '')
                cvss_match = re.search(r'CVSS Score:\s*([0-9.]+|\bN/A\b)\s*\((\w+|\bN/A\b)\)', content)
                cvss_score = cvss_match.group(1) if cvss_match else 'N/A'
                severity = cvss_match.group(2) if cvss_match else 'N/A'
                
                schema = {
                    '@context': 'https://schema.org',
                    '@type': 'TechArticle',
                    'headline': title,
                    'description': meta_desc or '',
                    'keywords': meta_data.get('yoast_wpseo_focuskw', ''),
                    'datePublished': post_info.get('date_gmt', ''),
                    'dateModified': post_info.get('date_gmt', ''),
                    'author': {
                        '@type': 'Organization',
                        'name': 'CyberNow'
                    },
                    'vulnerabilityDetails': {
                        'cvssScore': cvss_score,
                        'severity': severity
                    }
                }
                meta_data['_yoast_wpseo_schema_article'] = json.dumps(schema)
                
                # Add default security tags for CVE posts if none exist
                if not post_info.get('tags'):
                    security_tags = ['Security Vulnerabilities', 'CVE']
                    if severity.lower() in ['critical', 'high']:
                        security_tags.append('High-Risk Vulnerabilities')
                    elif severity.lower() == 'medium':
                        security_tags.append('Medium-Risk Vulnerabilities')
                    
                    # Get tag IDs
                    tag_ids = []
                    for tag_name in security_tags:
                        tag_id = add_tag_to_wordpress(tag_name)
                        if tag_id:
                            tag_ids.append(tag_id)
                    post_info['tags'] = tag_ids
        
        # Update post_info with meta_data
        post_info['meta'] = meta_data
        
        # Handle featured image
        if not post_info.get('featured_media'):
            # Generate featured image for the post
            title = str(post_info.get('title', ''))
            is_cve = title.startswith('CVE:')
            try:
                from post_synthesis import generate_featured_image
                image_data = generate_featured_image(title, is_cve=is_cve)
                if image_data:
                    media_id = upload_media_to_wordpress(
                        image_data,
                        title=f"Featured Image for {title}",
                        alt_text=title
                    )
                    if media_id:
                        post_info['featured_media'] = media_id
                        print(f"Successfully generated and uploaded featured image with ID: {media_id}")
            except Exception as e:
                print(f"Warning: Failed to generate featured image: {e}")
        
        # Create the post
        print("Creating WordPress post with data:", json.dumps(post_info, indent=2))
        response = httpx.post(post_endpoint, headers=headers, json=post_info, timeout=30.0)
        
        if response.status_code == 201:
            created_post = response.json()
            print(f"Successfully created post: {post_info.get('title', '')}")
            
            # Update meta fields separately if needed
            if meta_data:
                meta_endpoint = f"{BASE_URL}/posts/{created_post['id']}"
                meta_response = httpx.post(meta_endpoint, headers=headers, json={'meta': meta_data})
                if meta_response.status_code != 200:
                    print(f"Warning: Failed to update meta fields: {meta_response.text}")
            
            return created_post
        else:
            print(f"Failed to create post. Status code: {response.status_code}")
            print(f"Response: {response.text}")
            return None
            
    except Exception as e:
        print(f"Error creating post: {str(e)}")
        print("Full traceback:")
        print(traceback.format_exc())
        return None

def fetch_categories():
    """Fetch all categories from WordPress."""
    try:
        categories = fetch_from_wp_api("categories")
        return categories if categories else []
    except Exception as e:
        print(f"Failed to fetch categories: {e}")
        return []

def fetch_tags():
    """Fetch all tags from WordPress."""
    try:
        tags = fetch_from_wp_api("tags")
        return tags if tags else []
    except Exception as e:
        print(f"Failed to fetch tags: {e}")
        return []

def fetch_wordpress_taxonomies():
    categories = fetch_categories()
    tags = fetch_tags()
    return categories, tags

def get_all_images_from_wp():
    images = fetch_from_wp_api("media")
    if not images:
        print("Failed to fetch images from WordPress.")
        return None
    print(f"Fetched {len(images)} images from WordPress.")
    return images

def fetch_from_wp_api(endpoint):
    """Fetch data from WordPress REST API."""
    # Add _embed parameter to get embedded data like tags and meta fields
    if '?' in endpoint:
        endpoint += '&_embed&_fields=id,title,content,excerpt,slug,featured_media,status,tags,meta&_fields[meta]=yoast_wpseo_metadesc,yoast_wpseo_title,yoast_wpseo_focuskw,_yoast_wpseo_schema_article'
    else:
        endpoint += '?_embed&_fields=id,title,content,excerpt,slug,featured_media,status,tags,meta&_fields[meta]=yoast_wpseo_metadesc,yoast_wpseo_title,yoast_wpseo_focuskw,_yoast_wpseo_schema_article'
        
    url = f"{BASE_URL}/{endpoint}"
    try:
        response = httpx.get(url, headers=HEADERS)
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to fetch from WordPress API: {response.text}")
            return None
    except Exception as e:
        print(f"Error fetching from WordPress API: {e}")
        return None

def fetch_posts_since_date(date_str):
    posts = []
    page = 1
    while True:
        params = {'per_page': 100, 'page': page, 'after': date_str}
        response = httpx.get(f"{BASE_URL}/posts", headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Failed to fetch posts on page {page}: {response.text}")
            break
        data = response.json()
        if not data:
            break
        posts.extend(data)
        page += 1
    return posts

def edit_post_html(html_content):
    soup = BeautifulSoup(html_content, 'html.parser')

    # Update the first div
    first_div = soup.find('div')
    if first_div:
        first_div['style'] = "max-width:640px; margin: auto;"

    # Update the first img tag
    first_img = soup.find('img')
    if first_img:
        first_img['style'] = "width:100%; height:auto;"

    # Make sure the last paragraph tag is within the last div and there is a new line before it
    last_div = soup.find_all('div')[-1]
    last_paragraph = soup.find_all('p')[-1]
    if last_div and last_paragraph:
        if last_paragraph.parent != last_div:
            last_div.append(last_paragraph)
        if last_div.text[-1] != '\n':
            last_div.append(BeautifulSoup('\n', 'html.parser'))
     
    # Make sure the last paragraph tag has a new line before it
    last_paragraph = soup.find_all('p')[-1]
    if last_paragraph:
        if last_paragraph.text[-1] != '\n':
            last_paragraph.append(BeautifulSoup('\n', 'html.parser'))
            


    return str(soup)

def update_posts_with_new_html(start_date):
    posts = fetch_posts_since_date(start_date)
    for post in posts:
        try:
            original_html = post['content']['rendered']
            updated_html = edit_post_html(original_html)
            post_info = {
                'slug': post['slug'],
                'content': updated_html
            }
            update_wp_post(post_info)
        except Exception as e:
            print(f"Failed to update post {post['id']}: {e}")

class MultipartEncoder:
    """A simple multipart form-data encoder."""
    def __init__(self, fields):
        self.boundary = f'----WebKitFormBoundary{os.urandom(16).hex()}'
        self.content_type = f'multipart/form-data; boundary={self.boundary}'
        self.fields = fields
        self._buffer = None
        self._prepare_data()

    def _prepare_data(self):
        """Prepare the multipart form data."""
        lines = []
        for name, value in self.fields.items():
            if isinstance(value, tuple):
                filename, fileobj, content_type = value
                lines.extend([
                    f'--{self.boundary}',
                    f'Content-Disposition: form-data; name="{name}"; filename="{filename}"',
                    f'Content-Type: {content_type}',
                    '',
                    fileobj.read() if isinstance(fileobj, io.IOBase) else fileobj,
                ])
            else:
                lines.extend([
                    f'--{self.boundary}',
                    f'Content-Disposition: form-data; name="{name}"',
                    '',
                    str(value),
                ])
        lines.extend([
            f'--{self.boundary}--',
            '',
        ])
        self._buffer = '\r\n'.join(lines).encode('utf-8')

    def read(self):
        """Read the prepared data."""
        return self._buffer

    @property
    def len(self):
        """Get the length of the data."""
        return len(self._buffer)

def store_post_info(post_info, topic_id, supabase_client):
    """
    Store post information in Supabase, ensuring proper handling of featured media.
    Handles type conversion and foreign key constraints.
    """
    try:
        # Handle featured media
        featured_media_id = None
        if 'featured_media' in post_info:
            try:
                # Check if it's binary data (PNG image)
                if isinstance(post_info['featured_media'], bytes):
                    # Upload to WordPress first
                    media_id = upload_media_to_wordpress(
                        post_info['featured_media'],
                        title=f"Featured Image for {post_info.get('title', '')}",
                        alt_text=post_info.get('title', '')
                    )
                    if media_id:
                        featured_media_id = media_id
                        
                        # Create image data with string ID (as required by images table)
                        image_data = {
                            'id': str(featured_media_id),
                            'origin_id': str(featured_media_id),
                            'url': f"wp-content/uploads/featured-image-{featured_media_id}.png",
                            'type': 'image/png',
                            'topic_id': topic_id
                        }
                        
                        # First check if image exists
                        existing_image = supabase_client.table('images').select('*').eq('id', image_data['id']).execute()
                        
                        if not existing_image.data:
                            # Insert new image if it doesn't exist
                            supabase_client.table('images').insert(image_data).execute()
                            print(f"Successfully stored image data for media ID: {featured_media_id}")
                else:
                    # If it's already an ID, use it as is
                    featured_media_id = int(post_info['featured_media'])
            except (TypeError, ValueError) as e:
                print(f"Warning: Could not process featured media: {e}")
                featured_media_id = None
            except Exception as e:
                print(f"Warning: Failed to store image data: {e}")
                featured_media_id = None

        # Prepare post data
        post_data = {
            'title': post_info.get('title'),
            'content': post_info.get('content'),
            'excerpt': post_info.get('excerpt'),
            'slug': post_info.get('slug'),
            'status': post_info.get('status', 'draft'),
            'topic_id': topic_id,
            'date_created': datetime.datetime.now().isoformat()
        }

        # Only add featured_media if we have a valid ID
        if featured_media_id is not None:
            post_data['featured_media'] = featured_media_id

        # Handle duplicate slugs
        original_slug = post_data['slug']
        counter = 1
        while True:
            try:
                # Try to insert the post
                result = supabase_client.table('posts').insert(post_data).execute()
                print("Successfully stored post info in Supabase")
                return result.data
            except Exception as e:
                if 'duplicate key value violates unique constraint' in str(e) and 'posts_slug_key' in str(e):
                    # Append counter to slug and try again
                    post_data['slug'] = f"{original_slug}-{counter}"
                    counter += 1
                else:
                    raise e

    except Exception as e:
        print(f"Failed to store post info: {e}")
        return None




