import json
import os
import openai
from dotenv import load_dotenv
from image_fetcher import process_images  # Import the image fetching function

# Load .env file
load_dotenv()

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

    # Define the user messages
    user_messages = [{"role": "user", "content": body} for body in article_bodies]
    print([system_message_synthesis] + user_messages)
    # Request a chat completion from the OpenAI API for synthesis
    response_synthesis = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",  # Use the appropriate model version
        messages=[system_message_synthesis] + user_messages,
    )

    synthesized_content = response_synthesis.choices[0].message['content']

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
    )

    # Get the assistant's response and exclude the image_queries field
    post_info = {key: value for key, value in response_json.choices[0].message.items() if key != 'image_queries'}

    # Process images and replace placeholders
    image_queries = response_json.choices[0].message.get('image_queries')
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

def news_synthesis(topic_dir):
    # Read in the articles data
    updated_articles_file = os.path.join(topic_dir, 'updated_articles.json')
    with open(updated_articles_file, 'r') as f:
        articles = json.load(f)

    # Aggregate all article bodies and external sources
    article_bodies = [article['article_body'] for article in articles]
    ext_sources = [source for article in articles for source in article['ext_sources']]

    # Generate the post information
    post_info = generate_post_info(article_bodies, ext_sources)

    # Save the post information to a JSON file
    post_info_file = os.path.join(topic_dir, 'post_info.json')
    with open(post_info_file, 'w') as f:
        json.dump(post_info, f)

    print(f"Post information saved to {post_info_file}")
