import os
import httpx
from dotenv import load_dotenv
from supabase_utils import supabase
from pexels_api import API
from typing import List, Dict, Optional, Union
from PIL import Image
from io import BytesIO
from collections import namedtuple
from enum import Enum

# Load .env file
load_dotenv()
# Access your API keys
pexels_api_key = os.getenv('PEXELS_API_KEY')
# Initialize Pexels API
pexels_api = API(pexels_api_key)
# Load WP Media endpoint
wp_media_endpoint = os.getenv('WP_MEDIA_ENDPOINT')

# Enum for providers
class Provider(Enum):
    UNSPLASH = "unsplash"
    PEXELS = "pexels"

# Data class for photo details
PhotoDetails = namedtuple("PhotoDetails", [
    'origin_id', 'url', 'query', 'description', 'photographer', 'photographer_url', 'type', 
    'filename', 'provider', 'width', 'height', 'wp_id', 'wp_url', 'topic_id'
])

API_CONFIG = {
    Provider.UNSPLASH: {
        "endpoint": "https://api.unsplash.com/search/photos",
        "headers": {
            'Accept-Version': 'v1',
            'Authorization': f'Client-ID {os.getenv("UNSPLASH_API_KEY")}',
        }
    }
    # Add similar configuration for PEXELS if needed
}

def test_query_images():
    return query_images(["Man-in-the-middle attack"], get_list_of_supabase_images(Provider.UNSPLASH.value), Provider.UNSPLASH)

def resize_image(content, base_width, base_height):
    # Open the image from binary content
    image = Image.open(BytesIO(content))

    # Calculate aspect ratio
    original_width, original_height = image.size
    aspect_ratio = original_width / original_height

    # Calculate new dimensions to fit within specified width and height 
    # while maintaining the original aspect ratio
    if original_width > original_height:
        new_width = base_width
        new_height = int(base_width / aspect_ratio)
    else:
        new_height = base_height
        new_width = int(base_height * aspect_ratio)

    # Resize the image using the LANCZOS filter
    resized_image = image.resize((new_width, new_height), Image.Resampling.LANCZOS)

    # Save the resized image to a new binary file
    buffered = BytesIO()
    resized_image.save(buffered, format=image.format)
    return buffered.getvalue()

def upload_image_to_wordpress(token, image_url, image_type, origin_id):
    # Fetch the image
    image_name = get_filename(origin_id, image_type)
    image_response = httpx.get(image_url)
    if image_response.status_code != 200:
        print(f"Failed to download image: {image_response.text}")
        return None
    
    # Prepare headers
    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Disposition': f'attachment; filename={image_name}',
        'Content-Type': '',  
        'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/116.0.0.0 Safari/537.36 Edg/116.0.1938.81',
    }

    # Resize the image
    image_binary = resize_image(image_response.content, 760, 340)
    
    # Upload the image
    response = httpx.post(wp_media_endpoint, headers=headers, data=image_binary)  # Send image content as data
    
    # Check the upload status
    if response.status_code == 201:
        print(f"Successfully uploaded image {image_name}")
        return response.json().get('id'), response.json().get('source_url')
    else:
        raise Exception(f"Failed to upload image: {response.text}")

def fetch_photos_from_api(query, page, provider):
    if provider == Provider.UNSPLASH:
        params = {
            'query': query,
            'page': page,
            'per_page': 1,
            'orientation': 'landscape',
        }
        response = httpx.get(API_CONFIG[Provider.UNSPLASH]["endpoint"], headers=API_CONFIG[Provider.UNSPLASH]["headers"], params=params)
        return response.json().get('results')
    elif provider == Provider.PEXELS:
        pexels_api.search(query, page=page, results_per_page=1)
        return pexels_api.get_entries()
    else:
        raise ValueError(f"Unsupported provider: {provider}")
    
    
def fetch_images_from_queries(search_queries: List[str], token: str, topic_id: int, prioritize_pexels: bool = False) -> List[Dict]:
    if not token:
        print("Failed to authenticate with WordPress.")
        return []
    
    # Get list of images from Supabase for both providers
    list_of_supabase_images = {
        Provider.PEXELS: get_list_of_supabase_images(Provider.PEXELS.value),
        Provider.UNSPLASH: get_list_of_supabase_images(Provider.UNSPLASH.value)
    }
    print("Got list of images from Supabase")
    
    # Determine priority based on the flag
    primary_provider = Provider.PEXELS if prioritize_pexels else Provider.UNSPLASH
    secondary_provider = Provider.UNSPLASH if prioritize_pexels else Provider.PEXELS
    
    # Try to fetch image from primary provider
    image = query_images(search_queries, list_of_supabase_images[primary_provider], primary_provider)
    
    # Try to fetch image from primary provider
    image = query_images(search_queries, list_of_supabase_images[primary_provider], primary_provider)

    # If an error occurred or no image from primary, try the secondary
    if image is None or not image:
        print(f"Failed to find a unique photo in {primary_provider.value} for all queries or an error occurred.")
        image = query_images(search_queries, list_of_supabase_images[secondary_provider], secondary_provider)
            
        if not image:
            print(f"Failed to find a unique photo in {secondary_provider.value} for all queries.")
            return []
    
    # Upload the image to WordPress
    result = upload_image_to_wordpress(token, image.url, image.type, str(image.origin_id))
    if not result:
        print("Failed to upload image to WordPress.")
        return []
    
    wp_id, wp_url = result
    image_dict = image._asdict()
    image_dict.update({'wp_id': wp_id, 'wp_url': wp_url, 'topic_id': topic_id})
    
    try:
        supabase.table("images").insert(image_dict).execute()
        print(f"Inserted image {image.origin_id} into Supabase")
        return [image_dict]
    except Exception as e:
        print(f"Failed to insert image into Supabase: {e}")
        return []

def query_images(search_queries, list_of_supabase_images, provider):
    for query in search_queries:
        page = 1
        while True:
            try:
                photos = fetch_photos_from_api(query, page, provider)
                if not photos:
                    print(f"No photos found for query {query}")
                    break
                photo = photos[0]
                if not is_photo_in_supabase(photo['id'], list_of_supabase_images):
                    return process_photo(photo, query, provider)
                page += 1
            except (AttributeError, KeyError) as e:  # Catching specific errors related to attribute or key access
                print(f"Error querying {provider.value} for {query} on page {page}: {e}")
                print(f"Photo: {photo}")
                return None  # Return None to indicate an error occurred
            except Exception as e:  # Catch other unexpected exceptions
                print(f"Error querying {provider.value} for {query} on page {page}: {e}")
                print(f"Photo: {photo}")
                break
    raise Exception(f"Failed to find a unique photo for all queries: {search_queries}")

def process_photo(photo, query, provider):
    try:
        if provider == Provider.PEXELS:
            details = {
                'origin_id': photo.id,
                'url': photo.landscape,
                'query': query,
                'description': photo.description,
                'photographer': photo.photographer,
                'photographer_url': photo.url,
                'type': fetch_image_type(photo.original),
                'filename': get_filename(photo.id, fetch_image_type(photo.original)),
                'provider': Provider.PEXELS.value,
                'width': photo.width,
                'height': photo.height,
                'wp_id': None,  # Placeholder or default value
                'wp_url': None,  # Placeholder or default value
                'topic_id': None  # Placeholder or default value
                        }
        elif provider == Provider.UNSPLASH:
            details = {
                'origin_id': photo['id'],
                'url': photo['urls']['regular'],
                'query' : query,
                'description': photo['description'],
                'photographer': photo['user']['name'],
                'photographer_url': photo['user']['links']['html'],
                'type': fetch_image_type(photo['urls']['raw']),
                'filename': get_filename(photo['id'], fetch_image_type(photo['urls']['raw'])),
                'provider': Provider.UNSPLASH.value,
                'width': photo['width'],
                'height': photo['height'],
                'wp_id': None,  # Placeholder or default value
                'wp_url': None,  # Placeholder or default value
                'topic_id': None  # Placeholder or default value
                        }
        else:
            raise ValueError(f"Unsupported provider: {provider}")
        return PhotoDetails(**details)
    except Exception as e:
        print(f"Error processing photo: {e}")
        raise e
    
def fetch_image_type(image_url):
    response = httpx.head(image_url)
    return response.headers['Content-Type']
    
def get_filename(origin_id: Union[str, int], image_type: str) -> str:
    # Extract the extension from the image type
    extension = image_type.split('/')[-1]  # For 'image/jpeg', it will extract 'jpeg'
    filename = f"{origin_id}.{extension}"
    return filename


def get_list_of_supabase_images(provider):
    # Get list of all supabase original image ids
    response = supabase.table("images").select("origin_id").eq("provider", provider).execute()
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