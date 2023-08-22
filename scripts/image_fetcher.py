import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv
from supabase import create_client, SupabaseClient

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Access your API keys
pexels_api_key = os.getenv('PEXELS_ACCESS_KEY')
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')

# Get the JWT token for WordPress
def get_jwt_token():
    print("Getting JWT token...")
    token_endpoint = "http://cybernow.info/wp-json/jwt-auth/v1/token"
    payload = {'username': wp_username, 'password': wp_password}
    response = requests.post(token_endpoint, data=payload)

    if response.status_code == 200:
        if response.headers['Content-Type'].startswith('application/json'):
            try:
                return response.json().get('data', {}).get('token')
            except json.JSONDecodeError:
                print(f"Failed to decode JSON: {response.text}")
        else:
            print(f"Unexpected content type: {response.headers['Content-Type']}")
    else:
        print(f"Failed to get JWT token. Status code: {response.status_code}, Response: {response.text}")

    return None

def upload_image_to_wordpress(image_url, token):
    upload_endpoint = "http://cybernow.info/wp-json/wp/v2/media"
    headers = {'Authorization': f'Bearer {token}', 'Content-Type': 'application/json'}
    image_response = requests.get(image_url)
    if image_response.status_code != 200:
        print(f"Failed to download image from {image_url}")
        return None

    files = {'file': image_response.content}
    response = requests.post(upload_endpoint, files=files, headers=headers)
    if response.status_code == 201:
        return response.json().get('id')
    else:
        print(f"Failed to upload image: {response.text}")
        return None

def query_pexels_images(search_queries):
    # Renamed to avoid confusion with Supabase query
    api_endpoint = "https://api.pexels.com/v1/search"
    headers = {'Authorization': pexels_api_key}
    images = []
    for query in search_queries:
        params = {'query': query, 'per_page': 1}
        response = requests.get(api_endpoint, params=params, headers=headers)
        if response.status_code == 200:
            try:
                photo = response.json()['photos'][0]
                # Collecting essential data for later processing
                images.append({
                    'origin_id': photo['id'],
                    'url': photo['url'],
                    'query': query
                })
            except (json.JSONDecodeError, KeyError):
                print(f"Failed to parse image data for query: {query}, Response: {response.text}")
        else:
            print(f"Failed to retrieve image for query: {query}, Status code: {response.status_code}")

    return images

def upload_images_to_supabase(images):
    try:
        response = supabase.table("images").insert(images).execute()
        print(f"Inserted {len(response.data)} images into Supabase")
    except Exception as e:
        print(f"Failed to insert images into Supabase: {e}")
    
def process_images(search_queries):
    token = get_jwt_token()
    if not token:
        print("Failed to authenticate with WordPress.")
        return []

    pexels_images = query_pexels_images(search_queries)
    supabase_images = []

    for image in pexels_images:
        wp_id = upload_image_to_wordpress(image['url'], token)
        if wp_id:
            image['wp_id'] = wp_id
            supabase_images.append(image)

    upload_images_to_supabase(supabase_images)
    return supabase_images