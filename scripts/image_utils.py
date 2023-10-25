import os
import httpx
from dotenv import load_dotenv
from supabase_utils import supabase
from wp_utils import token
from pexels_api import API
from typing import List, Dict, Optional, Union
from PIL import Image
from io import BytesIO
from collections import namedtuple
from enum import Enum

# Enum for providers
class Provider(Enum):
    UNSPLASH = "unsplash"
    PEXELS = "pexels"

# Data class for photo details
PhotoDetails = namedtuple("PhotoDetails", [
    'origin_id', 'url', 'query', 'description', 'photographer', 'photographer_url', 'type', 
    'file_name', 'provider', 'width', 'height', 'wp_id', 'wp_url', 'topic_id'
])


class ImageProcessor:

    def __init__(self):
        # Load .env file
        load_dotenv()
        # Access your API keys
        self.pexels_api_key = os.getenv('PEXELS_API_KEY')
        # Initialize Pexels API
        self.pexels_api = API(self.pexels_api_key)
        # Load WP Media endpoint
        self.wp_media_endpoint = os.getenv('WP_MEDIA_ENDPOINT')
        
        # API Configuration
        self.API_CONFIG = {
            Provider.UNSPLASH: {
                "endpoint": "https://api.unsplash.com/search/photos",
                "headers": {
                    'Accept-Version': 'v1',
                    'Authorization': f'Client-ID {os.getenv("UNSPLASH_API_KEY")}',
                }
            }
            # Add similar configuration for PEXELS if needed
        }
    
    def test_query_images(self):
            return self.query_images(
                ["Man-in-the-middle attack"], 
                self.get_list_of_supabase_images(Provider.UNSPLASH.value), 
                Provider.UNSPLASH
            )
    
    def resize_image(self, content, base_width, base_height):
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

    def upload_image_to_wordpress(self, token, image_url, image_type, origin_id):
        # Fetch the image
        image_name = self.get_file_name(origin_id, image_type)  # Assuming get_file_name is another method in the class
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
        image_binary = self.resize_image(image_response.content, 760, 340)
        
        # Upload the image
        response = httpx.post(self.wp_media_endpoint, headers=headers, data=image_binary)  # Access the class attribute with self
        
        # Check the upload status
        if response.status_code == 201:
            print(f"Successfully uploaded image {image_name}")
            return response.json().get('id'), response.json().get('source_url')
        else:
            raise Exception(f"Failed to upload image: {response.text}")
        
    def fetch_photos_from_api(self, query, page, provider):
        if provider == Provider.UNSPLASH:
            params = {
                'query': query,
                'page': page,
                'per_page': 1,
                'orientation': 'landscape',
            }
            response = httpx.get(self.API_CONFIG[Provider.UNSPLASH]["endpoint"], 
                                 headers=self.API_CONFIG[Provider.UNSPLASH]["headers"], 
                                 params=params)
            return response.json().get('results')
        elif provider == Provider.PEXELS:
            self.pexels_api.search(query, page=page, results_per_page=1)
            return self.pexels_api.get_entries()
        else:
            raise ValueError(f"Unsupported provider: {provider}")

    def fetch_images_from_queries(self, search_queries: List[str], topic_id: int, prioritize_pexels: bool = False) -> List[Dict]:
        if not token:
            print("Failed to authenticate with WordPress.")
            return []

        # Get list of images from Supabase for both providers
        list_of_supabase_images = {
            Provider.PEXELS: self.get_list_of_supabase_images(Provider.PEXELS.value),
            Provider.UNSPLASH: self.get_list_of_supabase_images(Provider.UNSPLASH.value)
        }
        print("Got list of images from Supabase")

        # Determine priority based on the flag
        primary_provider = Provider.PEXELS if prioritize_pexels else Provider.UNSPLASH
        secondary_provider = Provider.UNSPLASH if prioritize_pexels else Provider.PEXELS

        # Try to fetch image from primary provider
        image = self.query_images(search_queries, list_of_supabase_images[primary_provider], primary_provider)

        # If an error occurred or no image from primary, try the secondary
        if image is None or not image:
            print(f"Failed to find a unique photo in {primary_provider.value} for all queries or an error occurred.")
            image = self.query_images(search_queries, list_of_supabase_images[secondary_provider], secondary_provider)

            if not image:
                print(f"Failed to find a unique photo in {secondary_provider.value} for all queries.")
                return []

        # Upload the image to WordPress
        result = self.upload_image_to_wordpress(token, image.url, image.type, str(image.origin_id))
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
        
    def query_images(self, search_queries, list_of_supabase_images, provider):
        for query in search_queries:
            page = 1
            while True:
                try:
                    photos = self.fetch_photos_from_api(query, page, provider)
                    if not photos:
                        print(f"No photos found for query {query}")
                        break
                    photo = photos[0]
                    if not self.is_photo_in_supabase(photo['id'], list_of_supabase_images):
                        return self.process_photo(photo, query, provider)
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

    def process_photo(self, photo, query, provider):
        print(f"Processing photo: {photo}")
        try:
            if provider == Provider.PEXELS:
                details = {
                    'origin_id': photo.id,
                    'url': photo.landscape,
                    'query': query,
                    'description': photo.description,
                    'photographer': photo.photographer,
                    'photographer_url': photo.url,
                    'type': self.fetch_image_type(photo.original),
                    'file_name': self.get_file_name(photo.id, self.fetch_image_type(photo.original)),
                    'provider': Provider.PEXELS.value,
                    'width': photo.width,
                    'height': photo.height,
                    'wp_id': None,  # Placeholder or default value
                    'wp_url': None,  # Placeholder or default value
                    'topic_id': None  # Placeholder or default value
                }
                print(f"Details: {details}")
            elif provider == Provider.UNSPLASH:
                print(f"Processing photo: {photo}")
                details = {
                    'origin_id': photo['id'],
                    'url': photo['urls']['regular'],
                    'query': query,
                    'description': photo['description'],
                    'photographer': photo['user']['name'],
                    'photographer_url': photo['user']['links']['html'],
                    'type': self.fetch_image_type(photo['urls']['raw']),
                    'file_name': self.get_file_name(photo['id'], self.fetch_image_type(photo['urls']['raw'])),
                    'provider': Provider.UNSPLASH.value,
                    'width': photo['width'],
                    'height': photo['height'],
                    'wp_id': None,  # Placeholder or default value
                    'wp_url': None,  # Placeholder or default value
                    'topic_id': None  # Placeholder or default value
                }
                print(f"Details: {details}")
            else:
                raise ValueError(f"Unsupported provider: {provider}")
            return PhotoDetails(**details)
        except Exception as e:
            print(f"Error processing photo: {e}")
            raise e
        
    def fetch_image_type(self, image_url):
        response = httpx.head(image_url)
        return response.headers['Content-Type']

    def get_file_name(self, origin_id: Union[str, int], image_type: str) -> str:
        # Extract the extension from the image type
        extension = image_type.split('/')[-1]  # For 'image/jpeg', it will extract 'jpeg'
        file_name = f"{origin_id}.{extension}"
        return file_name

    def get_list_of_supabase_images(self, provider):
        # Get list of all supabase original image ids
        response = supabase.table("images").select("origin_id").eq("provider", provider).execute()
        if getattr(response, 'error', None):
            print(f"Failed to get list of supabase images: {response}")
            return None
        return [image['origin_id'] for image in response.data]

    def is_photo_in_supabase(self, origin_id, list_of_supabase_images):
        # Check if the photo is in supabase
        if origin_id in list_of_supabase_images:
            print(f"Image with origin ID {origin_id} is already in Supabase")
            return True
        else:
            return False