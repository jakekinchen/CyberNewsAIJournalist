import json
import os
import openai
from dotenv import load_dotenv
from image_fetcher import fetch_images_from_queries # Import the image fetching function
from supabase_utils import supabase
from wp_post import fetch_categories, fetch_tags
from content_optimization import query_gpt, function_call_gpt, regenerate_image_queries, insert_tech_term_link, seo_optimization
from datetime import datetime
import ast
import re
import logging
from bs4 import BeautifulSoup, Tag
import math

# Load .env file
load_dotenv()
# Get model and prompt from environment variables
model = os.getenv('MODEL')
synthesis_prompt = os.getenv('SYNTHESIS_PROMPT')
# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

def post_completion(post_info, functions):
    instructions = "With this information, complete all of the missing fields in the JSON object (or optimize any that could be better for SEO) using the WordPressPostFieldCompletion function."
    # Convert the post_info dictionary to a JSON string
    json_str = json.dumps(post_info)
    model = 'gpt-4'
    response = function_call_gpt(json_str, instructions, model, functions, function_call_mode={"name": "WordPressPostFieldCompletion"})
    # Parse the JSON string into a dictionary
    # Check if response is already a dictionary
    if isinstance(response, dict):
        json_dict = response
    else:
        try:
            # If response is a string, try to load it as JSON
            json_dict = json.loads(response)
        except json.JSONDecodeError as e:
            raise Exception(f"Failed to parse the response string as JSON. Error: {e}")
    return json_dict

def post_synthesis(token, topic):
    # Read in the factsheets into an object for each source associated with the topic and keep track of the source IDs
    if not topic['factsheet']:
        print(f"Topic {topic['name']} has no factsheet. Skipping...")
        return
    categories = fetch_categories(token)
    tags = fetch_tags(token)
    factsheet = topic['factsheet']
    external_source_info = topic['external_source_info']
    print("Categories and tags fetched")
    json_function = [
            {
                "name": "WordPressPostFieldCompletion",
                "description": "Observe the content of the post and optimize its other fields for SEO for a Wordpress post.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    "title": {
                        "type": "string",
                        "description": "This brief post title is primarily for users, helping them understand the content and adding structure to the page. It is different from the SEO title, which appears in search results."
                    },
                    'image_queries': {
                        'type': 'array',
                        'description': 'A list of queries to generate images for the post.',
                        'items': { 
                            "type": "string", 
                            "description": "A query to generate an image for the post. This should be a phrase that describes the contents of the image, with different words separated by space like normal. It should not be a concatenation of multiple words and should not contain a file extension. Try to make it vaguely referential to the content when something specific wouldn't be expected in a stock photo database. Don't make it too obvious or too similar to other queries. Do not use super obvious queries like 'cybersecurity' or 'hacking'." 
                            },
                    },
                    "excerpt": {
                        "type": "string",
                        "description": "The excerpt of the post."
                    },
                    "slug": {
                        "type": "string",
                        "description": "The slug of the post. It is the part of the URL that comes after the domain name, and it should be short, descriptive, and include the focus keyword."
                    },                 
                    "yoast_wpseo_title": {
                        "type": "string",
                        "description": "A brief SEO title of the post, optimized to attract clicks from search engine results. It may contain elements such as the post title, site name, emojis, and should ideally include the focus keyword. This title appears in search engine snippets, browser tabs, and impacts the post's rankings. Make it brief, should be no longer than 5 words total. May also end with | CyberNow"
                    },
                    "yoast_wpseo_metadesc": {
                        "type": "string",
                        "description": "The meta description of the post, providing a very brief overview of the content. It appears below the SEO title in search engine snippets. It should include the focus keyword be less than 100 chracters."
                    },
                    "yoast_wpseo_focuskw": {
                        "type": "string",
                        "description": "The focus keyword of the post. It is a specific keyword that the post is optimized for, aiming to help the post rank higher in search engine results for that keyword. Including the focus keyword in the SEO title and meta description is crucial for SEO effectiveness."
                    },
                    "sticky": {
                        "type": "boolean",
                        "description": "Whether the post should be sticky or not. Sticky posts are displayed at the top of the blog page. Use discretion when setting this value, should only be true for the most important posts. There should be a probability of 0.1 that this value is true."
                    },
                    "categories": { 
                                    "type": "array", 
                                   "description": f"The category id(s) of the post. The existing categories are: {categories}", 
                                   "items": { 
                                            "type": "integer", 
                                            "description": "integer" 
                                            } 
                                    }, 
                    "tags": { 
                        "type": "array", 
                        "description": f"The tag id(s) of the post. The existing tags are: {tags}",
                        "items": {
                            "type": "integer",
                            "description": "Tag id of the post that would fit"
                            }
                        },
                    "tech_term": {
                        "type": "string",
                        "description": "A word found in the article that is technical jargon. This word will be linked to a definition in the article."
                        },
                    }
                }
            }
        ]
    
    print("JSON function generated")

    if not isinstance(factsheet, str):
        if isinstance(factsheet, list):
            factsheet = ' '.join(map(str, factsheet))
        else:
            factsheet = str(factsheet)

    # Sanitize factsheet by replacing newline characters and other special characters with a space
    sanitized_factsheet = re.sub(r'[\n\r]', ' ', factsheet)

    user_messages = f"{sanitized_factsheet}" + "\n\n And here are external sources you can use to add helpful information and link with an a-tag with href at the external source's url" + f"{external_source_info}: Make sure to use 'a' tags with hrefs to link to the external sources. Use the tag on the word or phrase that is most relevant to the external source."
    raw_synthesized_article = query_gpt(user_messages, synthesis_prompt, model='gpt-4')
    if not raw_synthesized_article:
        print("Synthesized article is empty. Continuing...")
        return None
    synthesized_article = None
    try:
        synthesized_article = seo_optimization(raw_synthesized_article)
    except Exception as e:
        print(f"Failed to optimize the article for SEO: {e}")
    if not synthesized_article:
        print("Synthesized article is empty after seo optimization. Continuing...")
        synthesized_article = raw_synthesized_article
    print("Synthesized article generated")
    # Chat completion to generate other JSON fields for post
    json_dict = post_completion(synthesized_article, json_function)
    print("Post completion generated")
   # Initialize post_info
    if json_dict is None:
         print("JSON dict from post completion is None")
         return None
    post_info = {
        'topic_id': topic['id'],
        'content': synthesized_article + "\n\nIf you enjoyed this article, please check out our other articles on <a href=\"https://cybernow.info\">CyberNow</a>",
        'complete_with_images': False,
        'yoast_meta': {},
    }
    post_info['content'] = insert_tech_term_link(post_info['content'], json_dict.get('tech_term'))

    def remove_newlines_before_title(html_content):
        # Find the index of the <title> tag
        title_index = html_content.find('<title>')
        
        # Ensure the <title> tag is present in the content
        if title_index != -1:
            # Replace all newline characters before the <title> tag with an empty string
            html_content = re.sub(r'\n', '', html_content[:title_index]) + html_content[title_index:]
        
        return html_content
    # Remove if there are any \n characters that appear anywhere in the section of the html before the first title <title> tag
    post_info['content'] = remove_newlines_before_title(post_info['content'])

    # Extract and validate fields from json_dict and add them to post_info
    def extract_field(field_name, default_value=None):
        if field_name.startswith('yoast_wpseo_'):
            if field_name in json_dict:
                post_info['yoast_meta'][field_name] = json_dict[field_name]
            elif default_value is not None:
                post_info['yoast_meta'][field_name] = default_value
            else:
                print(f"Failed to generate {field_name}. Continuing without {field_name}.")
        else:
            if field_name in json_dict:
                post_info[field_name] = json_dict[field_name]
            elif default_value is not None:
                post_info[field_name] = default_value
            else:
                print(f"Failed to generate {field_name}. Continuing without {field_name}.")

    # Extract fields from json_dict
    try:
        extract_field('title')
        extract_field('excerpt')
        extract_field('slug')
        extract_field('image_queries', [])
        extract_field('yoast_wpseo_metadesc')
        extract_field('yoast_wpseo_title')
        extract_field('yoast_wpseo_focuskw')
        extract_field('categories', [19])  # default category
        extract_field('tags', [20])  # default tag
        extract_field('sticky', False)
    except Exception as e:
        print(f"Failed to extract fields from json_dict: {e}")
        print(f"Post info after dictionary extraction failed: {post_info['yoast_meta']}")
        return
    
    if not post_info['image_queries']:
        print("No image queries generated. Generating new ones.")
        try:
            post_info['image_queries'] = regenerate_image_queries(post_info)
            if not post_info['image_queries']:
                raise Exception("Failed to generate image queries.")
        except Exception as e:
            print(f"Failed to regenerate image queries: {e}")
            return
        
    # Handle image_queries and inject images
    try:
        print("Fetching images...")
        images = fetch_images_from_queries(post_info['image_queries'], token, topic['id'])
        if not images:
            return None
        post_info = inject_images_into_post_info(post_info, images)
    except Exception as e:
        print(f"Failed to generate images: {e}")
        return None

    post_info['date_created'] = datetime.now().isoformat()
    # Save the post information to their respective fields in Supabase in the posts table

    return post_info

def inject_images_into_post_info(post_info, images, focus_keyword=None):
    if not images:  # If images are empty or None
        post_info['complete_with_images'] = False
        raise Exception("No images to inject into post info.")
        return post_info
    
    # Initialize BeautifulSoup object with the post content
    soup = BeautifulSoup(post_info['content'], 'html.parser')
    
    # Get all the paragraphs in the body
    p_tags = soup.find_all('p')
    
    # If there is only one image, insert it under the h1 tag
    if len(images) == 1:
        img_tag = soup.new_tag("img", src=images[0]['wp_url'], alt=images[0]['description'])
        #img_tag['width'] = '600'
        #img_tag['height'] = '260'
        h1_tag = soup.find('h1')
        post_info['featured_media'] = images[0]['wp_id']
        if h1_tag:
            h1_tag.insert_after(img_tag)
    else:
        # Calculate the interval at which to insert the images
        interval = len(p_tags) / (len(images) + 1)
        for i, image in enumerate(images):
            # Calculate the index at which to insert the current image
            index = math.ceil(interval * (i + 1))
            
            # If it exceeds the last index, set it to the last index
            if index >= len(p_tags):
                index = len(p_tags) - 1
                
            # Create and insert the image tag
            img_tag = Tag(name='img', attrs={'src': image['wp_url'], 'alt': image['description']})
            img_tag['width'] = '600'
            img_tag['height'] = '260'
            p_tags[index].insert_before(img_tag)
            
            # Set the featured_media for the first image
            if i == 0:
                post_info['featured_media'] = image['wp_id']
                
            # Add focus keyword to alt attribute if not present
            if focus_keyword and focus_keyword not in img_tag['alt']:
                img_tag['alt'] += f", {focus_keyword}"
                
    post_info['content'] = str(soup)
    post_info['complete_with_images'] = True
    return post_info

def insert_post_info_into_supabase(post_info):
 try:
        response = supabase.table("posts").insert([post_info]).execute()
 except Exception as e:
        print(f"An error occurred: {e}")
        if e.code == '23505':
            print(f"Post with the slug {post_info['slug']} already exists. Continuing...")
            print("Deleting the post in Supabase...")
            try:
                response = supabase.table("posts").delete().eq('slug', post_info['slug']).execute()
                print("Post deleted.")
                # Try to insert the post again
                try:
                    response = supabase.table("posts").insert([post_info]).execute()
                    print("Post inserted.")
                except Exception as e:
                    print(f"Failed to insert the post: {e}")
                    print("Continuing...")
                    return
            except Exception as e:
                print(f"Failed to delete the post: {e}")
                print("Continuing...")
                return
        if e.code == 'PGRST102':
            print("An invalid request body was sent(e.g. an empty body or malformed JSON).")
            print("Tried to insert the following post info:")
        if e.code == '22P02':
            print("An invalid request body was sent(e.g. an empty body or malformed JSON).")
            print(f"Tried to insert the following post info:{post_info}")
        else:
            print(f"Failed to save post information to Supabase. Continuing...")
            return