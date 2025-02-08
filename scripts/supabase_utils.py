from supabase import create_client, Client
import os
from dotenv import load_dotenv
import logging
from scripts.wp_utils import get_all_images_from_wp, fetch_from_wp_api
from datetime import datetime
from scripts.table_structures import image_table, post_table
from urllib.parse import urlparse

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_URL')
supabase_service_role_key = os.getenv('SUPABASE_SERVICE_ROLE_KEY')

if not supabase_url or not supabase_service_role_key:
    raise ValueError("Missing required environment variables: SUPABASE_URL and/or SUPABASE_SERVICE_ROLE_KEY")

# Create client with service role key for server-side operations
supabase = create_client(supabase_url, supabase_service_role_key)

def upsert_supabase_image_using_origin_id(image_info):
    image_info = {k: v for k, v in image_info.items() if v is not None}
    if not validate_data_against_structure(image_info, image_table):
        print(f"Validation failed for data: {image_info}")
        return
    try:
        response = supabase.table("images").upsert(image_info).execute()
        print(f"Successfully updated image with origin_id {image_info['origin_id']}.")
    except Exception as e:
        print(f"Error: {e}")  # Print the exception
        print(f"Data: {image_info}")
    
def validate_data_against_structure(data, structure):
    for key in data.keys():
        if key not in structure:
            raise ValueError(f"Invalid field name: {key}")
        if not isinstance(data[key], structure[key]):
            raise TypeError(f"Invalid type for {key}. Expected {structure[key]}, but got {type(data[key])}.")
    return True

def update_supabase_table(data, table_name, validation_structure):
    clean_data = {k: v for k, v in data.items() if v is not None}
    if not validate_data_against_structure(clean_data, validation_structure):
        print(f"Validation failed for data: {clean_data}")
        return

    try:
        response = supabase.table(table_name).update(clean_data).eq('id', clean_data['id']).execute()
        print(f"Successfully updated {table_name} with id {clean_data['id']}.")
    except Exception as e:
        print(f"Failed to update {table_name}: {e}")
        print(f"Data: {clean_data}")
        return

def update_supabase_images_with_wp_images():
    # Assume you only have access to post URL to identify the post
    posts = get_all_posts_from_supabase()
    print(f"Found {len(posts)} posts in Supabase.")
    # Get the first 2 posts for testing purposes
    for post in posts:
        try:
            wp_post = get_post_by_url(post['link'])
            #print(f"Processing Supabase post {post['id']} with link: {post['link']}")
            #print(f"WordPress post fetched with ID: {wp_post['id']} and link: {wp_post['link']}")
            image_info = get_image_info_by_wp_post(wp_post)
            #print("Found image in WordPress.")
            # Extracting only the filename without its extension
            if image_info is None:
                print(f"Image_info is null: {image_info}")
                continue
            only_filename_without_extension = os.path.splitext(os.path.basename(image_info.get('file_name', '')))[0]
            #print(f"Extracted filename without extension: {only_filename_without_extension}")
            # Set the origin_id to the extracted filename
            image_info['origin_id'] = only_filename_without_extension
            image_info['topic_id'] = post.get('topic_id')
            image_info['post_id'] = post.get('id')
            print(f"Upserting image with id {image_info['origin_id']} in Supabase.")
            upsert_supabase_image_using_origin_id(image_info)
        except Exception as e:
            print(f"Error processing post {post['id']} with origin_id {image_info.get('origin_id', 'unknown')}: {e}")
            continue

def update_supabase_image(image_info):
    update_supabase_table(image_info, "images", image_table)

def update_supabase_post(post_info):
    update_supabase_table(post_info, "posts", post_table)

def get_all_posts_from_supabase():
    try:
        response = supabase.table("posts").select("*").execute()
        return response.data
    except Exception as e:
        print(f"Failed to get posts from Supabase: {e}")
        return None
    
def get_post_by_url(url):
    # Remove trailing slash if it exists
    cleaned_url = url.rstrip('/')
    slug = urlparse(cleaned_url).path.split('/')[-1]
    posts = fetch_from_wp_api(f"posts?slug={slug}&_embed")
    print(f"Fetched WordPress post with slug: {slug}, ID: {posts[0]['id']}, and link: {posts[0]['link']}")
    if not posts:
        print(f"No post found for the URL: {url}")
        return None
    print(f"Extracted slug from URL {url}: {slug}")
    return posts[0]

def get_image_info_by_wp_post(wp_post):
    if not wp_post['featured_media']:
        print(f"No featured media for post ID: {wp_post['id']}")
        return None
    media_endpoint = f"media/{wp_post['featured_media']}"
    print(f"Fetching media from WordPress endpoint: {media_endpoint}")
    media_response = fetch_from_wp_api(media_endpoint)
    content_parameters = [key for key in media_response]
    #print(f"Type of media_response: {type(media_response)}, Content parameters: {content_parameters}")
    
    # Check if media_response is a list and has content
    if isinstance(media_response, list) and len(media_response) > 0:
        media = media_response[0]
    elif isinstance(media_response, dict):
        media = media_response
    else:
        print(f"Unexpected media_response format: {type(media_response)}, Content parameters: {content_parameters}")
        return None

    if not media:
        print(f"Failed to fetch media for post ID: {wp_post['id']}")
        return None

    # Check if 'media_details' has the 'file' key
     # Extract only the filename from the 'media_details'
    file_name = os.path.basename(media.get('media_details', {}).get('file', ''))
    if not file_name:
        print(f"'media_details' does not contain a 'file' key for post ID: {wp_post['id']}")
        return None

    return {
        'alt_text': media.get('alt_text'),
        'wp_url': media.get('source_url'),
        'wp_id': media.get('id'),
        'is_featured_media': True,
        'file_name': file_name,
        'width': media.get('media_details', {}).get('width'),
        'height': media.get('media_details', {}).get('height'),
    }



# Go through every post in the posts table in Supabase and if there is a slug, then concatenate the slug with the URL https://cybernow.info/ and update the post field 'link' with the new URL
# This is a one time script to update the links in the posts table
def update_links():
    BASE_URL = 'https://cybernow.info/'
    try:
        posts = supabase.table('posts').select('id, slug, link').execute()
        posts = posts.data
        
        # Filter out posts without slugs or with already correct links
        posts_to_update = [
            post for post in posts 
            if post['slug'] and post.get('link') != f"{BASE_URL}{post['slug']}/"
        ]

        if not posts_to_update:
            logging.info("No posts need link updates.")
            return
        
        # Prepare data for bulk upsert
        bulk_data = [
            {'id': post['id'], 'link': f"{BASE_URL}{post['slug']}/"} 
            for post in posts_to_update
        ]

        # Perform the bulk upsert
        for data in bulk_data:
            supabase.table('posts').update(data).eq('id', data['id']).execute()

        logging.info(f"Updated links for {len(bulk_data)} posts.")

    except Exception as e:
        logging.error(f"Failed to update links: {e}")

def store_post_info(supabase, post_info):
    """Store post information in Supabase."""
    try:
        now = datetime.now()
        
        # First, handle the featured media if present
        featured_media_id = None
        if 'featured_media' in post_info:
            try:
                # Check if it's binary data (PNG image)
                if isinstance(post_info['featured_media'], bytes):
                    # Generate a new unique ID for the image
                    featured_media_id = int(now.timestamp())
                    
                    # Create image data
                    image_data = {
                        'id': str(featured_media_id),  # Keep as string for images table
                        'origin_id': str(featured_media_id),  # Keep as string for images table
                        'url': f"https://cybernow.info/wp-content/uploads/{now.year}/{now.month:02d}/featured-image-{featured_media_id}.png",
                        'type': 'image/png',
                        'topic_id': post_info.get('topic_id'),
                        'content': post_info['featured_media']  # Store the binary data
                    }
                    
                    # Check if image exists first
                    existing_image = supabase.table('images').select('*').eq('id', image_data['id']).execute()
                    if not existing_image.data:
                        # Insert new image
                        supabase.table('images').insert(image_data).execute()
                        print(f"Successfully inserted image with ID {image_data['id']}")
                else:
                    # If it's already an ID, use it as is
                    featured_media_id = int(post_info['featured_media'])
            except (TypeError, ValueError) as e:
                print(f"Warning: Could not process featured media: {e}")
                featured_media_id = None
        
        # Then create post record
        post_data = {
            'title': post_info['title'],
            'content': post_info['content'],
            'excerpt': post_info['excerpt'],
            'slug': post_info['slug'],
            'date_created': now.isoformat(),
            'status': post_info['status'],
            'topic_id': post_info.get('topic_id')
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
                response = supabase.table('posts').insert(post_data).execute()
                print("Successfully stored post info in Supabase")
                return response.data
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

async def delete_topic(topic_id):
    # Delete the topic
    try:
        response = supabase.table("topics").delete().eq("id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete topic: {e}")
        return
    print(f"Successfully deleted topic with ID {topic_id} and all related sources.")

def get_a_source_from_supabase(id):
    try: 
        source = supabase.table('sources').select('*').eq('id', id).limit(1).execute()
        source = source.data[0]
    except Exception as e:
        print(f"Failed to get a source from Supabase: {e}")
        return None
    return source

async def delete_supabase_post(topic_id):
    # topic_id is a foreign key in the supabase table posts
    # Delete the post
    try:
        response = supabase.table("posts").delete().eq("topic_id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete post: {e}")
        return
    print(f"Successfully deleted post with topic ID {topic_id}.")

def delete_supabase_images_not_in_wp():
    # Get all image file_names from WordPress
    wp_images = get_all_images_from_wp()
    # Print first object in list
    
    wp_image_file_names = []
    
    for image in wp_images:
        if 'media_details' in image and 'file' in image['media_details']:
            file_name = image['media_details']['file'].split('/')[-1]
            wp_image_file_names.append(file_name)
        #else:
            #print(f"Image object missing 'file' key: {image}")
    print(f"Found {len(wp_image_file_names)} images in WordPress.")
    #print(f"wp_image_file_names: {wp_image_file_names}")
    # Delete all images in Supabase that are not in WordPress
    supabase_images = supabase.table("images").select("*").execute()
    supabase_images = supabase_images.data
    #print(f"supabase_images: {supabase_images}")
    delete_supabase_images_not_in_file_name_list(supabase_images, wp_image_file_names)
    
def delete_supabase_images_not_in_file_name_list(supabase_images, wp_image_file_names):
    for image in supabase_images:
        if image['file_name'] not in wp_image_file_names:
            print(f"Deleting image with id {image['id']} from Supabase...")
            try:
                response = supabase.table("images").delete().eq('id', image['id']).execute()
                print(f"Successfully deleted image with id {image['id']} from Supabase.")
            except Exception as e:
                print(f"Failed to delete image with id {image['id']} from Supabase: {e}")
                continue
        else:
            print(f"Image with id {image['id']} is in WordPress. Continuing...")
            continue

def get_topics_without_posts():
    """Get topics that don't have associated posts in the posts table."""
    try:
        # Using a left join to find topics without posts
        response = supabase.table("topics") \
            .select("*, posts!left(id)") \
            .is_("posts.id", "null") \
            .order("id", desc=True) \
            .execute()
        
        # Filter out the join data and return just the topics
        topics = []
        for item in response.data:
            topic = {k: v for k, v in item.items() if k != "posts"}
            topics.append(topic)
            
        print(f"Found {len(topics)} topics without posts")
        return topics
    except Exception as e:
        print(f"Failed to get topics without posts: {e}")
        return []