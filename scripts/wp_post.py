import os
import json
import requests
import csv
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load .env file
load_dotenv()


# Create a new post on WordPress
def create_wordpress_post(token, post_info, post_time):
    
    post_endpoint = "http://cybernow.info/wp-json/wp/v2/posts"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }
    post_info['status'] = 'future'  # Set status to 'future'
    post_info['date'] = post_time.strftime('%Y-%m-%dT%H:%M:%S')  # Set date and time of publishing
    post_info['date_gmt'] = (post_time - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S')  # Set GMT date and time of publishing

    response = requests.post(post_endpoint, json=post_info, headers=headers)
    if response.status_code == 201:
        print("Post created successfully.")
        return response.json()  # Return the post data
    else:
        print(f"Failed to create post: {response.text}")
        return None

def fetch_categories(token):
    # Establish headers
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the categories
    categories_endpoint = "http://cybernow.info/wp-json/wp/v2/categories"
    response = requests.get(categories_endpoint, headers=headers)
    
    if response.status_code == 200:
        categories = response.json()
        
        # Simplify the response to only include 'id' and 'name'
        simplified_categories = []
        for category in categories:
            simplified_category = {'id': category['id'], 'name': category['name']}
            simplified_categories.append(simplified_category)
        
        print(f"Successfully fetched {len(simplified_categories)} categories: {simplified_categories}")
        return simplified_categories
        
    else:
        print(f"Failed to fetch categories: {response.text}")
        return None
    
def fetch_tags(token):
    # Establish headers
    headers = {'Authorization': f'Bearer {token}'}
    
    # Fetch the tags
    tags_endpoint = "http://cybernow.info/wp-json/wp/v2/tags"
    response = requests.get(tags_endpoint, headers=headers)
    
    if response.status_code == 200:
        tags = response.json()
        
        # Simplify the response to only include 'id' and 'name'
        simplified_tags = []
        for tag in tags:
            simplified_tag = {'id': tag['id'], 'name': tag['name']}
            simplified_tags.append(simplified_tag)
        
        print(f"Successfully fetched {len(simplified_tags)} tags: {simplified_tags}")
        return simplified_tags
        
    else:
        print(f"Failed to fetch tags: {response.text}")
        return None