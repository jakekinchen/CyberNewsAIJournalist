import json
import os
import openai
from dotenv import load_dotenv
from image_fetcher import process_images  # Import the image fetching function
from supabase import create_client, Client

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

def generate_post_info(article_bodies, ext_sources):
    # Get the synthesis prompt
    synthesis_prompt = os.getenv('SYNTHESIS_PROMPT')

    # Define the system message for synthesis
    system_message_synthesis = {
        "role": "system",
        "content": synthesis_prompt
    }
    article_bodies = [str(body) for body in article_bodies]
    # Define the user messages
    user_messages = [{"role": "user", "content": body} for body in article_bodies]
    #print([system_message_synthesis] + user_messages)
    # Request a chat completion from the OpenAI API for synthesis
    response_synthesis = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",  # Use the appropriate model version
        messages=[system_message_synthesis] + user_messages,
    )

    synthesized_content = response_synthesis.choices[0].message.content

    # Get the JSON prompt
    json_prompt = os.getenv('JSON_PROMPT')

    # Define the system message for JSON formatting
    system_message_json = {
        "role": "system",
        "content": json_prompt
    }

    # Request a chat completion from the OpenAI API for JSON formatting
    response_json = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",  # Use the appropriate model version
        messages=[system_message_json, {"role": "user", "content": synthesized_content}],
        functions={
            {
            "name": "WordPress Post Field Completion",
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
                "yoast_meta": [
                    {
                        "yoast_wpseo_title": {
                        "type": "string",
                        "description": "The title of the post."
                        }
                    },
                    {
                        "yoast_wpseo_metadesc": {
                        "type": "string",
                        "description": "The excerpt of the post."
                        }
                    },
                    {
                        "yoast_wpseo_focuskw": {
                        "type": "string",
                        "description": "The focus keyword of the post."
                        }
                    }
                ]
            }
            },

        }
    )

    # Get the assistant's response and exclude the image_queries field
    post_info = {key: value for key, value in response_json.choices[0].message.items() if key != 'image_queries'}

    # Process images and replace placeholders
    image_queries = response_json.choices[0].message.content('image_queries')
    if image_queries:
        images = process_images(image_queries)
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
            images = process_images(image_queries)
            if images:  # Check if images are not empty
                for i, image in enumerate(images):
                    image_placeholder = f"[wp_get_attachment_image id=\"{image['image_id']}\" size=\"full\"] <a href=\"{image['original_image_url']}\">Photos provided by Pexels</a>"
                    post_info['content'] = post_info['content'].replace(f'[insert image {i+1}]', image_placeholder)
            else:
                print("No images received. Continuing without images.")
        else:
            print("image_queries field is missing in the response. Continuing without images.")
        return post_info

def news_synthesis(topic):
    # Read in the factsheets into an object for each source associated with the topic and keep track of the source IDs
    response = supabase.table("sources").select("*").eq("topic_id", topic["id"]).execute()
    sources = response.data
    source_ids = [source['id'] for source in sources]
    factsheets = {source['id']: source['factsheet'] for source in sources}

    #put the ids of the sources into the ext_sources array with the url of the source
    ext_sources = [{"id": source['id'], "url": source['url']} for source in sources]

    print(f"Synthesizing news for topic {topic['name']}...")
    # Generate the post information
    post_info = generate_post_info(factsheets, ext_sources)

    # Save the post information to their respective fields in Supabase in the posts table
    post_info_file = f"post_info_{topic['id']}.json"
    try:
        response = supabase.table("posts").insert([post_info]).execute()
    except Exception as e:
        print(e)
        print(f"Failed to save post information to Supabase. Saving to {post_info_file} instead...")

    print(f"Post information saved to {post_info_file}")
