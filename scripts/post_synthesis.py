import json
import os
import openai
from dotenv import load_dotenv
from image_fetcher import fetch_images_from_queries # Import the image fetching function
from supabase import create_client, Client
from wp_post import fetch_categories, fetch_tags
from content_optimization import query_gpt
from datetime import datetime
import ast

# Load .env file
load_dotenv()
# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)
model = os.getenv('MODEL')
synthesis_prompt = os.getenv('SYNTHESIS_PROMPT')
json_prompt = os.getenv('JSON_PROMPT')
# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

json_function = [{"name": "WordPressPostFieldCompletion",
                "description": "Observe the content of the post and optimize it for SEO for a Wordpress post.",
                "parameters": {
                    "content": {
                        "type": "string",
                        "description": "The content of the post."
                    },
                    "title": {
                        "type": "string",
                        "description": "The title of the post."
                    },
                    "image_queries": {
                        "type": "array",
                        "description": "An array of image search query strings."
                    },
                    "excerpt": {
                        "type": "string",
                        "description": "The excerpt of the post."
                    },                 
                    "yoast_wpseo_title": {
                        "type": "string",
                        "description": "The title of the post."
                    },
                    "yoast_wpseo_metadesc": {
                        "type": "string",
                        "description": "The excerpt of the post."
                    },
                    "yoast_wpseo_focuskw": {
                        "type": "string",
                        "description": "The focus keyword of the post."
                    },
                    "categories": {
                        "type": "array",
                        "description": "The category id(s) of the post."
                    },
                    "tags": {
                        "type": "array",
                        "description": "The tag id(s) of the post."
                    },
                    
                }
}
]

def post_completion(token, post_info, functions):
    instructions = "With this information, complete all of the missing fields in the JSON object (or optimize any that could be better for SEO) using the WordPressPostFieldCompletion function."
    # Convert the post_info dictionary to a JSON string
    json_str = json.dumps(post_info)
    # within the first function of the json_function, within the parameters field, within the tags field, within the description field, append the result of fetch_tags(token) to the end of the string value of the description field
    functions[0]['parameters']['tags']['description'] += f" {fetch_tags(token)}"
    # within the first function of the json_function, within the parameters field, within the categories field, within the description field, append the result of fetch_categories(token) to the end of the string value of the description field
    functions[0]['parameters']['categories']['description'] += f" {fetch_categories(token)}"
    # Generate the chat completion
    response = query_gpt(json_str, instructions, model, functions)
    # Parse the JSON string into a dictionary
    json_dict = json.loads(response)
    print(f"Successfully generated post completion: {json_dict}")
    return json_dict

def insert_tags_and_categories_into_prompt(prompt, categories, tags):
    # Insert the categories into the prompt
    prompt = prompt.replace('[insert categories]', ', '.join([str(cat['id']) for cat in categories]))
    # Insert the tags into the prompt
    prompt = prompt.replace('[insert tags]', ', '.join([str(tag['id']) for tag in tags]))
    return prompt

def fill_in_field(field, post, categories, tags):
    # Mapping of field names to prompts
    switcher = {
        "title": "The title of the post should be",
        "content": "The content of the post should be",
        "excerpt": "The excerpt of the post should be",
        "yoast_wpseo_title": "The SEO title of the post should be",
        "yoast_wpseo_metadesc": "The SEO description of the post should be",
        "yoast_wpseo_focuskw": "The focus keyword of the post should be",
        "image_queries": "The image queries should be",
        "featured_media": "The featured image integer should be",
        "slug": "The slug of the post should be",
        "categories": "The category id(s) of the post should be (just give the integer id(s) of the category in a comma-separated list in an array (this should always include 19))",
        "tags": "The tag id(s) of the post should be (just give the integer id(s) of the category in a comma-separated list in an array)"
    }
    prompt = switcher.get(field, f"{field} of the post should be")  # Default prompt if field not found
    # Additional information for categories and tags
    if field == "categories":
        category_list = ', '.join([str(cat['name']) for cat in categories])
        prompt = f"Given the content of the story is {post['content']} and given that available WordPress categories are: {category_list}. {prompt}"
    elif field == "tags":
        tag_list = ', '.join([str(tag['name']) for tag in tags])
        prompt = f"Given the content of the story is {post['content']} and given that available WordPress tags are: {tag_list}. {prompt}"
    try:
        # Request a chat completion from the OpenAI API
        field_value = query_gpt(prompt)
        # Update the post object with the field value
        print(f"Successfully generated content for {field}: {field_value}")
        post[field] = field_value
    except Exception as e:
        print(f"Failed to generate content for {field}. Error: {e}")
    return post

def generate_post_info(token, factsheet, topic):
    user_messages = [str(factsheet)]
    categories = fetch_categories(token)
    tags = fetch_tags(token)
    # Chat completion to synthesize article information
    synthesized_article = query_gpt(user_messages, synthesis_prompt, model='gpt-4')
    # Chat completion to generate other JSON fields for post
    response_json = post_completion(token, synthesized_article, json_function)
    # Parse the JSON string into a dictionary
    json_str = response_json

    # Initialize post_info as an empty dictionary
    post_info = {}
    post_info['topic_id'] = topic['id']
    post_info['content'] = synthesized_article
    post_info['complete_with_images'] = False
    #post_info['categories'] = [19]
    #post_info['tags'] = [20]

    try:
        json_dict = json.loads(json_str)
    except json.JSONDecodeError:
        try:
            json_dict = ast.literal_eval(json_str)
        except (ValueError, SyntaxError):
            print("Failed to parse the string as either JSON or a Python dictionary.")
            return
        

    # List of required fields
    required_fields = [
        'title', 'excerpt', 
        'yoast_wpseo_title', 'yoast_wpseo_metadesc', 'yoast_wpseo_focuskw', 'slug',
    ]
    # Check and fill each required field
    for field in required_fields:
        if field in json_dict and not post_info[field]:
            post_info[field] = json_dict[field]
        else:
            post_info = fill_in_field(field, post_info, categories, tags)

    # Initialize image_queries as an empty list
    image_queries = []

    # Check if 'image_queries' exists in the JSON dictionary
    if 'image_queries' in json_dict:
        image_queries = json_dict['image_queries']
        print(f"image_queries: {image_queries}")
        images = fetch_images_from_queries(image_queries, token)
    else:
        print("image_queries field is missing in the response. Generating image_queries...")
        # Define a prompt to instruct the model to insert 3 strings in an array under the image_queries field
        prompt_for_image_queries = (
            "The JSON object is missing the 'image_queries' field. "
            "Please insert an array with three strings under the 'image_queries' field. "
            "Each string should correspond to an image search query. "
            "The first query should be mostly related to the title as it will be the featured image, "
            "while the 2nd and 3rd photo queries can be related to the adjacent content next to their placeholders in the content field. Recreate the JSON object with the image_queries field filled out"
        )
        # Request a chat completion from the OpenAI API
        response_image_queries = query_gpt(prompt_for_image_queries, model="gpt-3.5-turbo")
        print(response_image_queries)
        # Extract the image_queries from the response
        image_queries = response_image_queries.get('image_queries')
        
        if image_queries:
            images = fetch_images_from_queries(image_queries, token)
        else:
            print("image_queries field is missing in the response. Continuing without images.")
            images = []
    if images:  # Check if images are not empty
        for i, image in enumerate(images):
            if not image['wp_id']:
                print(f"Failed to upload image {i+1} to WordPress. Continuing without images.")
                post_info['complete_with_images'] = False
                continue
            image_placeholder = f"[wp_get_attachment_image id=\"{image['wp_id']}\" size=\"full\"] <a href=\"{image['url']}\">Photos provided by Pexels</a>"
            post_info['content'] = post_info['content'].replace(f'[insert image {i+1}]', image_placeholder)
            post_info['complete_with_images'] = True
            if i == 0:
                post_info['featured_media'] = image['wp_id']
    else:
        print("No images received. Continuing without images.")
        post_info['complete_with_images'] = False

    # Check if 'categories' and 'tags' exist in post_info
    try:
        if 'categories' not in post_info:
            # Query GPT-3 to fill in the categories
            post_info['categories'] = query_gpt(f"Given that available WordPress categories are: {', '.join([str(cat['name']) for cat in categories])}. The category id(s) of the post should be (just give the integer id(s) of the category in a comma-separated list)", model="gpt-3.5-turbo")
        if 'tags' not in post_info:
            post_info['tags'] = query_gpt(f"Given that available WordPress tags are: {', '.join([str(tag['name']) for tag in tags])}. The category id(s) of the post should be (just give the integer id(s) of the category in a comma-separated list)", model="gpt-3.5-turbo")
    except Exception as e:
        print(f"Failed to generate categories and tags: {e}")
    
    if 'title' in post_info:
        if not post_info['slug']:
            post_info['slug'] = post_info['title'].lower().replace(' ', '-')
        if not post_info['yoast_wpseo_title'] or "[title]" in post_info['yoast_wpseo_title']:
            post_info['yoast_wpseo_title'] = post_info['title']
        post_info['yoast_wpseo_title'] = f"{post_info['title']} | CyberNow "

    # IF post_info['categories'] is a string, convert it to an array, then remove all non-numeric characters and put a comma between each number
    if isinstance(post_info['categories'], str):
        post_info['categories'] = [int(s) for s in post_info['categories'].split(',') if s.isdigit()]
    # IF post_info['tags'] is a string, convert it to an array, then remove all non-numeric characters so our final result is an array of integers
    if isinstance(post_info['tags'], str):
        post_info['tags'] = [int(s) for s in post_info['tags'].split(',') if s.isdigit()]
    print(f"Tags: {post_info['tags']}")
    print(f"Categories: {post_info['categories']}")
    # Add the date_created field
    post_info['date_created'] = datetime.now().isoformat()
    return post_info

def post_synthesis(token, topic):
    # Read in the factsheets into an object for each source associated with the topic and keep track of the source IDs
    factsheets = topic['factsheet']

    #put the ids of the sources into the ext_sources array with the url of the source
    #ext_sources = [{"id": source['id'], "url": source['url']} for source in sources]
    print(f"Synthesizing news for topic {topic['name']}...")
    # Generate the post information
    post_info = generate_post_info(token, factsheets, topic)
    # Save the post information to their respective fields in Supabase in the posts table
    
    try:
        response = supabase.table("posts").insert([post_info]).execute()
    except Exception as e:
        print(f"An error occurred: {e}")
        print(f"Failed to save post information to Supabase.")
    return post_info




