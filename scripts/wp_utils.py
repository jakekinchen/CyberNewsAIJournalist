import os
import json
import httpx
import csv
from dotenv import load_dotenv
from datetime import datetime, timedelta
import logging
from table_structures import wp_post_table
from urllib.parse import urlparse
import pytz

# Load .env file
load_dotenv()

# Load the post fields from the table structures
post_fields = wp_post_table

# Access your API keys and token
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')
#wp_token = os.getenv('WP_TOKEN')

# Get the JWT token for WordPress
def get_jwt_token(username, password):

    # if wp_token:
    #     logging.info("Using existing token")
    #     return wp_token
    
    token_endpoint = "http://cybernow.info/wp-json/jwt-auth/v1/token"
    payload = {
        'username': username,
        'password': password
    }
    response = httpx.post(token_endpoint, data=payload)
    if response.status_code == 200:
        token = response.json().get('token')  # Get token directly from JSON response
        #logging.info(f"Received token: {token}")
        return token
    else:
        logging.info(f"Failed to get JWT token: {response.text}")
        raise Exception(f"Failed to get JWT token: {response.text}")

# Get the JWT token for WordPress
token = get_jwt_token(wp_username, wp_password)

# Base URL for WordPress REST API
BASE_URL = "https://cybernow.info/wp-json/wp/v2"
# Headers for WordPress REST API
HEADERS = {
    'Authorization': f'Bearer {token}'
}

# Delete wp posts with wp

def delete_wp_post(wp_id):
    headers = {'Authorization': f'Bearer {token}'}
    url = f"{BASE_URL}/posts/{wp_id}"
    try:
        response = httpx.delete(url, headers=headers)
        if response.status_code != 200:
            print(f"Failed to delete post: {response.text}")
            return
    except Exception as e:
        print(f"Failed to delete post: {e}")
        return
    print(f"Successfully deleted post with id {wp_id}.")
    return response.json()

def update_wp_post(post_info):
    # Get the wordpress id from the slug
    wp_id = get_wp_id_from_slug(post_info['slug'])
    # Update the wordpress post
    headers = {
        'Authorization': f'Bearer {token}',
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
    print("Entered type check function")
    sanitized_post_info = {}
    for key, value in post_info.items():
        #print("Entered type check for loop")
        if key == 'yoast_meta' and isinstance(value, dict):
            sanitized_yoast_meta = {}
            for sub_key, sub_value in value.items():
                #print("Entered yoast_meta type check for loop")
                if isinstance(sub_value, str):  # since all the yoast_meta sub fields are string type
                    sanitized_yoast_meta[sub_key] = sub_value
                else:
                    print(f"Skipping invalid field in yoast_meta: {sub_key}, expected type str but got {type(sub_value)}")
            sanitized_post_info[key] = sanitized_yoast_meta
        elif key in post_fields and isinstance(value, post_fields[key]):
            sanitized_post_info[key] = value
    return sanitized_post_info

def add_tag_to_wordpress(token, tag):
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the tags
    tags_endpoint = f"{BASE_URL}/tags"

    # Check if the tag already exists
    response = httpx.get(tags_endpoint, headers=headers)
    if response.status_code == 200:
        tags = response.json()
        for existing_tag in tags:
            if existing_tag['name'] == tag:
                print(f"Tag '{tag}' already exists")
                return existing_tag['id']
    else:
        print(f"Failed to fetch tags: {response.text}")
        return None
    
    # Create the tag
    payload = {
        'name': tag
    }
    response = httpx.post(tags_endpoint, headers=headers, json=payload)
    if response.status_code == 201:
        print(f"Created tag '{tag}'")
        return response.json().get('id')
    else:
        print(f"Failed to create tag '{tag}': {response.text}")
        return None
    
# Create a new post on WordPress
def create_wordpress_post(token, post_info, immediate_post=True, delay_hours=1):
    if post_info is None:
        logging.error("Error: post_info is None")
        raise ValueError("post_info is None")

    post_endpoint = f"{BASE_URL}/posts"
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    # Adjust post time
    central_tz = pytz.timezone('America/Chicago')  # Assuming Central Time as mentioned
    if immediate_post:
        post_time = datetime.now(central_tz)
    else:
        post_time = datetime.now(central_tz) + timedelta(hours=delay_hours)

    # Setting the date field in the site's timezone and date_gmt field in UTC
    post_info['date'] = post_time.strftime("%Y-%m-%dT%H:%M:%S")
    post_info['date_gmt'] = post_time.astimezone(pytz.utc).strftime("%Y-%m-%dT%H:%M:%S")
    post_info['status'] = 'publish'

    sanitized_post_info = type_check_post_info(post_info)
    response = httpx.post(post_endpoint, json=sanitized_post_info, headers=headers)
    
    if response.status_code == 201:
        print("Post created successfully.")
        return response.json()
    else:
        print(sanitized_post_info)
        raise Exception(f"Failed to create post: {response.text}")


def fetch_categories(token):
    # Establish headers
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the categories
    categories_endpoint = f"{BASE_URL}/categories"
    response = httpx.get(categories_endpoint, headers=headers)
    
    if response.status_code == 200:
        categories = response.json()
        
        # Simplify the response to only include 'id' and 'name'
        simplified_categories = []
        for category in categories:
            simplified_category = {'id': category['id'], 'name': category['name']}
            # If category name is 'Uncategorized' or 'C-Suite Articles', skip it
            if simplified_category['name'] == 'Uncategorized' or simplified_category['name'] == 'C-Suite Articles':
                continue
            simplified_categories.append(simplified_category)
        return simplified_categories
    else:
        print(f"Failed to fetch categories: {response.text}")
        return None
    
def fetch_tags(token):
    # Establish headers
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the tags
    tags_endpoint = f"{BASE_URL}/tags"
    response = httpx.get(tags_endpoint, headers=headers)
    
    if response.status_code == 200:
        tags = response.json()
        
        # Simplify the response to only include 'id' and 'name'
        simplified_tags = []
        for tag in tags:
            simplified_tag = {'id': tag['id'], 'name': tag['name']}
            simplified_tags.append(simplified_tag)
        
        return simplified_tags
        
    else:
        print(f"Failed to fetch tags: {response.text}")
        return None
    
def fetch_wordpress_taxonomies(token):
    categories = fetch_categories(token)
    tags = fetch_tags(token)
    return categories, tags

def get_all_images_from_wp():
    images = fetch_from_wp_api("media")
    if not images:
        print("Failed to fetch images from WordPress.")
        return None
    print(f"Fetched {len(images)} images from WordPress.")
    return images

def fetch_from_wp_api(endpoint):
    """Utility function to fetch data from WordPress API."""
    results = []
    page = 1
    while True:
        params = {'per_page': 100, 'page': page}
        response = httpx.get(f"{BASE_URL}/{endpoint}", headers=HEADERS, params=params)
        if response.status_code != 200:
            print(f"Failed to fetch data from {endpoint} on page {page}: {response.text}")
            break
        data = response.json()
        
        # If data isn't a list, return it directly
        if not isinstance(data, list):
            return data
        
        print(f"Type of data: {type(data)}")
        results.extend(data)
        if len(data) < 100:  # Less than the maximum, so it's the last page.
            break
        page += 1
    print(f"Fetched {len(results)} results from WordPress API endpoint: {endpoint}")
    return results



