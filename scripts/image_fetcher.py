import os
import requests
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
# Initialize Pexels API
pexels_api = API(pexels_api_key)
# Load WP Media endpoint
wp_media_endpoint = os.getenv('WP_MEDIA_ENDPOINT')

def upload_image_to_wordpress(token, image_url, image_type, origin_id):
    # Fetch the image
    image_name = get_filename(origin_id, image_type)
    image_response = requests.get(image_url)
    if image_response.status_code != 200:
        print(f"Failed to download image: {image_response.text}")
        return None
    
    # Prepare headers
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Disposition': f'attachment; filename={image_name}',
        #'Content-Type': '',  
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81',
    }
    
    # Upload the image
    response = requests.post(wp_media_endpoint, headers=headers, data=image_response.content)  # Send image content as data
    
    # Check the upload status
    if response.status_code == 201:
        print(f"Successfully uploaded image {image_name}")
        return response.json().get('id'), response.json().get('source_url')
    else:
        print(f"Failed to upload image: {response.text}")
        return None

def query_pexels_images(search_queries, list_of_supabase_images):
    for query in search_queries:
        page = 1
        while True:
            try:
                pexels_api.search(query, page=page, results_per_page=1)
                photos = pexels_api.get_entries()
                if not photos:
                    print(f"No photos found for query {query}")
                    break  # Move to the next query if no photos found
                
                photo = photos[0]
                if not is_photo_in_supabase(photo.id, list_of_supabase_images):
                    # Process and return the photo if it's unique
                    return process_photo(photo, query)
                
                page += 1  # If photo is in Supabase, go to the next page
            except Exception as e:
                print(f"Error querying Pexels for {query} on page {page}: {e}")
                break  # Move to the next query in case of an error
    return None  # Return None if no unique photo is found for all queries

def process_photo(photo, query):
    response = requests.head(photo.original)
    image_type = response.headers['Content-Type']
    filename = get_filename(photo.id, image_type)
    image_url = photo.landscape if photo.landscape else photo.original
    return {
        'origin_id': photo.id,
        'url': image_url,
        'query': query,
        'description': photo.description,
        'photographer': photo.photographer,
        'photographer_url': photo.url,
        'type': image_type,
        'filename': filename,
        'provider': 'pexels',
        'width': photo.width,
        'height': photo.height,
    }

def fetch_images_from_queries(search_queries, token, topic_id):
    if not token:
        print("Failed to authenticate with WordPress.")
        return []
    
    list_of_supabase_images = get_list_of_supabase_images() or []
    image = query_pexels_images(search_queries, list_of_supabase_images)
    
    if not image:
        print("Failed to find a unique photo for all queries.")
        return []
    
    result = upload_image_to_wordpress(token, image['url'], image['type'], f"{image['origin_id']}")
    if not result:
        print("Failed to upload image to WordPress.")
        return []
    
    wp_id, wp_url = result
    image.update({'wp_id': wp_id, 'wp_url': wp_url, 'topic_id': topic_id})
    try:
        supabase.table("images").insert(image).execute()
        print(f"Inserted image {image['origin_id']} into Supabase")
        return [image]
    except Exception as e:
        print(f"Failed to insert image into Supabase: {e}")
        return []

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
    images = fetch_images_from_queries(search_queries, token, topic['id'])
    if not images:
        print(f"Failed to fetch images from queries {search_queries}")
        return
    else:
        for image in images:
            image['topic_id'] = topic['id']
    return images

def get_filename(origin_id: Union[str, int], image_type: str) -> str:
    # Extract the extension from the image type
    extension = image_type.split('/')[-1]  # For 'image/jpeg', it will extract 'jpeg'
    filename = f"{origin_id}.{extension}"
    return filename


def get_list_of_supabase_images():
    # Get list of all supabase original image ids
    response = supabase.table("images").select("origin_id").execute()
    if getattr(response, 'error', None):
        print(f"Failed to get list of supabase images: {response}")
        return None
    return [image['origin_id'] for image in response.data]

def is_photo_in_supabase(origin_id, list_of_supabase_images):
    # Check if the photo is in supabase
    if origin_id in list_of_supabase_images:
        print(f"Image with origin ID {origin_id} is already in Supabase")
        return True
    else:
        return False