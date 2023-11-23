import json
import os
from dotenv import load_dotenv
from supabase_utils import supabase
from wp_utils import fetch_categories, fetch_tags
from image_utils import ImageProcessor
from gpt_utils import query_gpt, function_call_gpt, generate_wp_field_completion_function
from content_optimization import regenerate_image_queries, insert_tech_term_link, readability_optimization, seo_optimization
from datetime import datetime
import re
from bs4 import BeautifulSoup, Tag
import math
import prompts

# Load .env file
load_dotenv()
# Get prompt from environment variables
synthesis_prompt = prompts.synthesis

def post_synthesis(token, topic, categories, tags):
    # Read in the factsheets into an object for each source associated with the topic and keep track of the source IDs
    if not topic['factsheet']:
        print(f"Topic {topic['name']} has no factsheet. Skipping...")
        return
    print("Beginning post synthesis...")
    #categories = fetch_categories(token)
    #tags = fetch_tags(token)
    factsheet = topic['factsheet']
    external_source_info = topic['external_source_info']
    print("Categories and tags fetched")
    wp_field_completion_function = generate_wp_field_completion_function(categories, tags)
    
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
        synthesized_article = readability_optimization(raw_synthesized_article)
    except Exception as e:
        print(f"Failed to optimize the article for readability: {e}")
    if not synthesized_article:
        print("Synthesized article is empty after readability optimization. Continuing...")
        synthesized_article = raw_synthesized_article
    print("Synthesized article generated")
    # Chat completion to generate other JSON fields for post
    json_dict = post_completion(synthesized_article, wp_field_completion_function)
    print("Post completion generated")
    #json_dict['content'] = ensure_focuskw_in_intro(json_dict['content'], json_dict['yoast_wpseo_focuskw'])
   # Initialize post_info
    if json_dict is None:
         print("JSON dict from post completion is None")
         return None
    post_info = {
        'topic_id': topic['id'],
        'content': synthesized_article,
        'yoast_meta': {},
    }
    

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
        
    if not post_info['yoast_meta'].get('yoast_wpseo_focuskw'):
        print("No focus keyword in yoast_meta. Generating new one.")
        
    if post_info['slug']:
        post_info['link'] = f"https://cybernow.info/{post_info['slug']}/"    
    # Handle image_queries and inject images
    try:
        print("Fetching images...")
        image_manager = ImageProcessor()
        images = image_manager.fetch_images_from_queries(post_info['image_queries'], topic['id'])
        #images = fetch_images_from_queries(post_info['image_queries'], token, topic['id'])
        if not images:
            return None
        
    except Exception as e:
        print(f"Failed to generate images: {e}")
        return None

    post_info['date_created'] = datetime.now().isoformat()
    # Save the post information to their respective fields in Supabase in the posts table
    try:
        post_info = seo_optimization(post_info, images)
    except Exception as e:
        print(f"Failed to optimize the article for SEO: {e}")

    post_info['content'] = insert_tech_term_link(post_info['content'], json_dict.get('tech_term'))
    if not prompts.end_of_article_tag in post_info['content']:
        print("End of article tag not found in content. Appending it to the end of the content.")
        post_info['content'] += prompts.end_of_article_tag

    return post_info

def post_completion(post_info, functions):
    instructions = "With this information, complete all of the missing fields in the JSON object (or optimize any that could be better for SEO) using the WordPressPostFieldCompletion function."
    # Convert the post_info dictionary to a JSON string
    json_str = json.dumps(post_info)
    model = os.getenv('FUNCTION_CALL_MODEL')
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


def sanitize_text(text):
    # Remove all spaces, newlines, and tabs from the text and make all characters lowercase
    return re.sub(r'\s', '', text).lower()

