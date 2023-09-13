import json
import os
import openai
from dotenv import load_dotenv
from image_fetcher import fetch_images_from_queries # Import the image fetching function
from supabase import create_client, Client
from wp_post import fetch_categories, fetch_tags

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

def fill_in_field(token, field, post):
    # Mapping of field names to prompts
    switcher = {
        "title": "The title of the post should be",
        "content": "The content of the post should be",
        "excerpt": "The excerpt of the post should be",
        "yoast_wpseo_title": "The SEO title of the post should be",
        "yoast_wpseo_metadesc": "The SEO description of the post should be",
        "yoast_wpseo_focuskw": "The focus keyword of the post should be",
        "image_queries": "The image queries should be",
        "featured_image": "The featured image should be",
        "slug": "The slug of the post should be",
        "categories": "The category id(s) of the post should be",
        "tags": "The tag id(s) of the post should be"
    }
    
    prompt = switcher.get(field, f"The {field} of the post should be")  # Default prompt if field not found
    
    # Additional information for categories and tags
    if field == "categories":
        categories = fetch_categories(token)
        category_list = ', '.join([str(cat['name']) for cat in categories])
        prompt = f"Given that available WordPress categories are: {category_list}. {prompt}"
        
    elif field == "tags":
        tags = fetch_tags(token)
        tag_list = ', '.join([str(tag['name']) for tag in tags])
        prompt = f"Given that available WordPress tags are: {tag_list}. {prompt}"
    
    try:
        # Request a chat completion from the OpenAI API
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=[{"role": "system", "content": prompt}],
        )
        # Extract the field value from the response
        field_value = response.choices[0].text.strip()  # Remove any extra whitespace or newline
        # Update the post object with the field value
        post[field] = field_value
    except Exception as e:
        print(f"Failed to generate content for {field}. Error: {e}")
        
    return post

def generate_post_info(token, article_bodies, ext_sources):
    system_message_synthesis = {"role": "system", "content": synthesis_prompt}
    article_bodies = [str(body) for body in article_bodies]
    user_messages = [{"role": "user", "content": body} for body in article_bodies]

    categories = fetch_categories(token)
    
    response_synthesis = openai.ChatCompletion.create(
        model=model,  # Assuming 'model' is defined elsewhere
        messages=[system_message_synthesis] + user_messages,
    )
    synthesized_content = response_synthesis.choices[0].message['content']
    
    
    system_message_json = {"role": "system", "content": json_prompt}
    
    response_json = openai.ChatCompletion.create(
        model=model,
        messages=[system_message_json, {"role": "user", "content": synthesized_content}],
    )

    # Parse the JSON string into a dictionary
    json_str = response_json.choices[0].message['content']
    try:
        json_dict = json.loads(json_str)
    except json.JSONDecodeError:
        print(json_str)
        print("Failed to decode JSON string. Please check if it's well-formed.")
        return

    # Initialize post_info as an empty dictionary
    post_info = {}
    post_info['complete_with_images'] = False

    # List of required fields
    required_fields = [
        'title', 'content', 'excerpt', 
        'yoast_wpseo_title', 'yoast_wpseo_metadesc', 'yoast_wpseo_focuskw'
    ]

    # Check and fill each required field
    for field in required_fields:
        if field in json_dict:
            post_info[field] = json_dict[field]
        else:
            print(f"{field} is missing. Filling it in...")
            post_info = fill_in_field(token, field, post_info)
    
    # Initialize image_queries as an empty list
    image_queries = []
    
    # Check if 'image_queries' exists in the JSON dictionary
    if 'image_queries' in json_dict:
        image_queries = json_dict['image_queries']
        images = fetch_images_from_queries(image_queries, token)
    else:
        print("image_queries field is missing in the response. Generating image_queries...")
        # Define a prompt to instruct the model to insert 3 strings in an array under the image_queries field
        prompt_for_image_queries = (
            "The JSON object is missing the 'image_queries' field. "
            "Please insert an array with three strings under the 'image_queries' field. "
            "Each string should correspond to an image search query. "
            "The first query should be mostly related to the title as it will be the featured image, "
            "while the 2nd and 3rd photo queries can be related to the content next to their placeholders. Recreate the JSON object with the image_queries field filled out"
        )
        # Request a chat completion from the OpenAI API
        response_image_queries = openai.ChatCompletion.create(
            model="gpt-3.5-turbo-16k",
            messages=[{"role": "system", "content": prompt_for_image_queries}],
        )
        print(response_image_queries)
        # Extract the image_queries from the response
        image_queries = response_image_queries.choices[0].message.get('image_queries')
        
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
                post_info['featured_image'] = image['wp_id']
    else:
        print("No images received. Continuing without images.")
        post_info['complete_with_images'] = False

    return post_info

def post_synthesis(token, topic):
    # Read in the factsheets into an object for each source associated with the topic and keep track of the source IDs
    response = supabase.table("sources").select("*").eq("topic_id", topic["id"]).execute()
    sources = response.data
    source_ids = [source['id'] for source in sources]
    factsheets = {source['id']: source['factsheet'] for source in sources}
    #put the ids of the sources into the ext_sources array with the url of the source
    ext_sources = [{"id": source['id'], "url": source['url']} for source in sources]
    print(f"Synthesizing news for topic {topic['name']}...")
    # Generate the post information
    post_info = generate_post_info(token, factsheets, ext_sources)
    # Save the post information to their respective fields in Supabase in the posts table
    try:
        response = supabase.table("posts").insert([post_info]).execute()
    except Exception as e:
        print(e)
        print(f"Failed to save post information to Supabase.")
    return post_info

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
                    }
                    
                }
}
]