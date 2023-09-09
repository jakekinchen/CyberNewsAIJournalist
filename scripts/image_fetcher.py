import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, Client
from pexels_api import API
from typing import List, Dict, Optional, Union

# Load .env file
load_dotenv()
# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)
# Access your API keys
pexels_api_key = os.getenv('PEXELS_API_KEY')
PEXELS_API_KEY = os.getenv('PEXELS_API_KEY')

# Initialize Pexels API
pexels_api = API(pexels_api_key)

def upload_image_to_wordpress(token, image_url, image_type, image_name):
    # Fetch the image
    image_response = requests.get(image_url)
    if image_response.status_code != 200:
        print(f"Failed to download image: {image_response.text}")
        return None
    # Prepare headers
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Disposition': f'attachment; filename="{image_name}"',
        'Content-Type': image_type  # This should be dynamic based on the image type
    }
    # Prepare files
    files = {
        'file': (image_name, image_response.content, image_type)
    }
    # Upload the image
    upload_endpoint = "http://cybernow.info/wp-json/wp/v2/media"
    response = requests.post(upload_endpoint, headers=headers, files=files)

    # Check the upload status
    if response.status_code == 201:
        return response.json().get('id')
    else:
        print(f"Failed to upload image: {response.text}")
        #Only print the first and last object in the file object
        print(f"Upload endpoint: {upload_endpoint}, headers: {headers}, files: ({files['file'][0]}, <binary data>, {files['file'][2]})")
        return None

def query_pexels_images(search_queries):
    images = []
    for query in search_queries:
        pexels_api.search(query, page=1, results_per_page=1)
        photos = pexels_api.get_entries()
        if not photos:
            print(f"Failed to find photos for query {query}")
            continue
        photo = photos[0]
        # Get the image type
        response = requests.head(photo.original)
        image_type = response.headers['Content-Type']  
        images.append({
            'origin_id': photo.id,
            'url': photo.original,
            'query': query,
            'description': photo.description,
            'photographer': photo.photographer,
            'photographer_url': photo.url,
            'type': image_type,
            'provider': 'pexels',
        })
    return images

def upload_images_to_supabase(images):
    try:
        response = supabase.table("images").insert(images).execute()
        print(f"Inserted {len(response.data)} images into Supabase")
    except Exception as e:
        print(f"Failed to insert images into Supabase: {e}")
        
def fetch_images_from_queries(search_queries, token):
    if not token:
        print("Failed to authenticate with WordPress.")
        return
    pexels_images = query_pexels_images(search_queries)
    supabase_images = []
    for image in pexels_images:
        wp_id = upload_image_to_wordpress(token, image['url'], image['type'], f"{image['origin_id']}")
        if wp_id:
            image['wp_id'] = wp_id
        supabase_images.append(image)
    upload_images_to_supabase(supabase_images)

if __name__ == '__main__':
    search_queries = ['nature', 'technology', 'space']
    fetch_images_from_queries(search_queries)

def fetch_images_from_post_of_topic(topic, token):
    #take the post associated with the topic in supabase, get the search queries from the post, and then use those in fetch_images_from_queries
    response = supabase.table("posts").select("*").eq("topic_id", topic["id"]).execute()
    #if there is no post associated with the topic, print an error message and return
    if not response.data:
        print(f"Failed to find post associated with topic {topic['name']}")
        return
    post = response.data[0]
    search_queries = post['image_queries']
    if not search_queries:
        print(f"Failed to find image queries associated with topic {topic['name']}")
        return
    images = fetch_images_from_queries(search_queries, token)
    if not images:
        print(f"Failed to fetch images from queries {search_queries}")
        return
    else:
        for image in images:
            image['topic_id'] = topic['id']
    return images
