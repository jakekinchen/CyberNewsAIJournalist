import json
import logging
import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)
import openai
import tiktoken

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

# Define the retry behavior
@retry(
    retry=retry_if_exception_type((openai.error.APIError, 
                                  openai.error.APIConnectionError, 
                                  openai.error.RateLimitError, 
                                  openai.error.ServiceUnavailableError, 
                                  openai.error.Timeout)),
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(10)
)
def _api_call_with_backoff(*args, **kwargs):
    return openai.ChatCompletion.create(*args, **kwargs)

def function_call_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo', functions=[], function_call_mode="auto"):
    function_call_mode = {"name": f"{functions[0]['name']}"}
    try:
        response = _api_call_with_backoff(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            functions=functions,
            function_call=function_call_mode
        )
        return json.loads(response.choices[0].message.function_call.arguments)
    except Exception as err:
        logging.error(err)
        print(f"Parameters: {functions}")
        print(f"Failed to call function: {err}")

def query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo'):
    context = f"{system_prompt} {user_prompt}"
    try:
        model = model_optimizer(context, model)  # assuming model_optimizer is defined elsewhere
    except Exception as e:
        logging.error(e)
        raise Exception(e)
    try:
        response = _api_call_with_backoff(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            request_timeout=150,
        )
        return response.choices[0].message.content
    except openai.error.APIConnectionError as err:
        logging.error(err)

def tokenizer(string: str, encoding_name: str) -> int:
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

def model_optimizer(text, model):
    token_quantity = tokenizer(text, model)
    if model.startswith('gpt-4'):
        if token_quantity < 8096:
            return 'gpt-4'
        elif token_quantity >= 8096 and token_quantity <= 32768:
            return 'gpt-3.5-turbo-16k'
        else:
            raise Exception('Text is too long for GPT-4')
    elif model.startswith('gpt-3.5'):
        if token_quantity < 4096:
            return 'gpt-3.5-turbo'
        elif token_quantity >= 4096 and token_quantity < 16384:
            return 'gpt-3.5-turbo-16k'
        elif token_quantity >= 16384 and token_quantity <= 32768:
            raise Exception('Text is too long for GPT-3.5')
        else:
            raise Exception('Text is too long for GPT-3.5')
        
def generate_factsheet_user_prompt(topic_name, content):
    return f"When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to {topic_name}. Now give the factsheet for the following information: {content}"
        
def generate_wp_field_completion_function(categories, tags):
    return [
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
        
image_query_function=[
            {
                "name": "ImageQueryGenerator",
                "description": "Observe the content of the post and suggest stock photo database queries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    'image_queries': {
                        'type': 'array',
                        'description': 'A list of queries to generate images for the post.',
                        'items': { 
                            "type": "string", 
                            "description": "A query to generate an image for the post. This should be a phrase that describes the contents of the image, with different words separated by space like normal. It should not be a concatenation of multiple words and should not contain a file extension." 
                            },
                        }
                    },
                    
                }
            }
        ]

source_remover_function = [
            {
                "name": "SourceRemover",
                "description": "Remove sources that are not related to the topic.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    'sources': {
                        'type': 'array',
                        'description': 'A list of sources to remove.',
                        'items': { 
                            "type": "integer", 
                            "description": "The id of the source to remove." 
                            },
                        }
                    },
                    
                }
            }
        ]
        