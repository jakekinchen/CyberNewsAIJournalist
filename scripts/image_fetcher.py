import os
import json
import requests
import pandas as pd
from dotenv import load_dotenv

# Load .env file
load_dotenv()

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

def query_images(search_queries):
    api_endpoint = "https://api.pexels.com/v1/search"
    headers = {'Authorization': pexels_api_key}
    images = []
    for query in search_queries:
        params = {'query': query, 'per_page': 1}
        response = requests.get(api_endpoint, params=params, headers=headers)
        if response.status_code == 200:
            try:
                photo = response.json()['photos'][0]
                images.append({
                    'image_url': photo['url'],
                    'original_image_id': photo['id'],
                    'original_image_url': photo['original_url']
                })
            except (json.JSONDecodeError, KeyError):
                print(f"Failed to parse image data for query: {query}, Response: {response.text}")
        else:
            print(f"Failed to retrieve image for query: {query}, Status code: {response.status_code}")

    return images

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

def process_images(search_queries):
    token = get_jwt_token()
    if not token:
        print("Failed to authenticate with WordPress.")
        return []

    images = query_images(search_queries)
    image_ids = []
    csv_entries = []
    for image in images:
        image_id = upload_image_to_wordpress(image['image_url'], token)
        if image_id:
            image_ids.append(image_id)
            csv_entries.append({
                'featured_image_id': image_id,
                'queries': search_queries,
                'original_image_ids': image['original_image_id'],
                'original_image_urls': image['original_image_url'],
                'queried': True,
                'success': True
            })

    csv_file_path = './data/images.csv'
    df = pd.DataFrame(csv_entries)
    df.to_csv(csv_file_path, mode='a', index=False)
    return image_ids
