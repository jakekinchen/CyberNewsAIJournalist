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
from openai import OpenAI
import tiktoken
from PIL import Image, ImageOps
from io import BytesIO
from pydantic import BaseModel
from typing import TypeVar, Type, Optional, Dict, Any, List, Union
from openai.types.chat import ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam


client = OpenAI(
    api_key=os.getenv('OPENAI_API_KEY'),
    organization=os.getenv('OPENAI_ORGANIZATION')
)

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_API_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

model = os.getenv('FUNCTION_CALL_MODEL')
summarization_model = os.getenv('SUMMARIZATION_MODEL')

# Define the retry behavior
@retry(
    retry=retry_if_exception_type(BaseException),
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(10)
)
def _api_call_with_backoff(*args, **kwargs):
    return client.chat.completions.create(*args, **kwargs)

def function_call_gpt(user_prompt, system_prompt, model=model, functions=[], function_call_mode="auto"):
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

def query_dalle(prompt, mode="create", size="1792x1024", image=None, mask=None, n=1):
    if mode == 'create':
        try:
            response = client.images.generate(
                model = "dall-e-3",
                prompt = prompt,
                n=n,
                size = size,
                quality="standard",
            )
            return response
        except openai.APIError as err:
            logging.error(err)
            print(f"Error: {err}")
    elif mode == 'edit':
        try:
            response = client.images.edit(
                prompt = prompt,
                image = image,
                n = n,
                mask = mask,
                size = size,
            )
            return response
        except openai.APIError as err:
            logging.error(err)
            print(f"Error: {err}")
    else:
        raise Exception('Invalid mode')
    
def list_available_models(filter_prefix=None):
    """
    List all available OpenAI models accessible to the user's API key.
    Args:
        filter_prefix (str or list, optional): Filter models by prefix(es). E.g., 'gpt' or ['gpt', 'text']
    Returns:
        list: Sorted list of model IDs
    """
    try:
        response = client.models.list()
        models = []
        
        # Convert single prefix to list for consistent handling
        if isinstance(filter_prefix, str):
            filter_prefix = [filter_prefix]
        
        for model in response.data:
            # If no filter is specified, include all models
            if not filter_prefix:
                models.append(model.id)
            # If filter is specified, only include models with matching prefixes
            elif any(prefix in model.id.lower() for prefix in filter_prefix):
                models.append(model.id)
        
        # Sort models for consistent output
        models.sort()
        
        # Print models in a formatted way
        if models:
            print("\nAvailable Models:")
            print("----------------")
            for model in models:
                print(f"- {model}")
        else:
            print("\nNo models found matching the specified criteria.")
            
        return models
    except Exception as err:
        logging.error(f"Failed to list models: {err}")
        return []

def query_gpt(user_prompt, system_prompt, model=summarization_model):
    """
    Query GPT model with the given prompts.
    
    Args:
        user_prompt (str): The user's input prompt
        system_prompt (str): The system behavior prompt
        model (str): The model to use for the query
        
    Returns:
        str: The model's response
        
    Raises:
        ValueError: If prompts are empty or None
        openai.AuthenticationError: For API key related errors
        openai.APIError: For other API-related errors
        Exception: For other unexpected errors
    """
    if not user_prompt or not system_prompt:
        raise ValueError("User prompt and system prompt cannot be empty or None")
    
    # Validate API key
    api_key = os.getenv('OPENAI_API_KEY')
    if not api_key:
        raise ValueError("OpenAI API key is not set")
    
    # Create a new client instance for each call to ensure we're using the current API key
    client = OpenAI(
        api_key=api_key,
        organization=os.getenv('OPENAI_ORGANIZATION')
    )
        
    try:
        response = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        if not response.choices:
            raise Exception("No response received from the model")
            
        return response.choices[0].message.content
    except openai.AuthenticationError as err:
        logging.error(f"Authentication error in query_gpt: {err}")
        raise
    except openai.APIError as err:
        logging.error(f"API error in query_gpt: {err}")
        raise
    except Exception as err:
        logging.error(f"Unexpected error in query_gpt: {err}")
        raise

def tokenizer(string: str, encoding_name: str) -> int:
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

def model_optimizer(text, model):
    token_quantity = tokenizer(text, model)
    if model.startswith('gpt-4'):
        if token_quantity <= 4096:
            return 'gpt-4-1106-preview'
        if token_quantity < 8096 and token_quantity > 4096:
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
                        'description': 'A list of prompt sentences to generate images for the post.',
                        'items': { 
                            "type": "string", 
                            "description": "A metaphorical sentence of imagery describing the power dynamics of the news story. Make the sentence a meta representation of what is figuratively going on." 
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
                            "description": "A query to generate an image for the post. This should be a phrase that describes the contents of the image, with different words separated by space like normal. It should not be a concatenation of multiple words and should not contain a file extension. Describe the situation happening in vivid detail, but a metaphorical personification of what is happening. Avoid the following triggers for the automatic filter system: Riot, Warrior, Battle, Fighting, Any real names, Anything that sounds like violence, Anything that can be mistaken as terrorism" 
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
        
T = TypeVar('T', bound=BaseModel)

def structured_output_gpt(prompt: str, model_class: Type[T], system_prompt: Optional[str] = None) -> Optional[T]:
    """
    Query GPT model with structured output using Pydantic models.
    
    Args:
        prompt (str): The user's input prompt
        model_class (Type[T]): The Pydantic model class to structure the output
        system_prompt (Optional[str]): Optional system behavior prompt
        
    Returns:
        Optional[T]: The structured response, or None if parsing fails
    """
    if not prompt:
        raise ValueError("Prompt cannot be empty or None")
    
    messages: List[Union[ChatCompletionSystemMessageParam, ChatCompletionUserMessageParam]] = []
    
    # Add system prompt if provided, otherwise use a default one
    if system_prompt:
        messages.append({"role": "system", "content": f"{system_prompt}\nProvide your response in JSON format."})
    else:
        messages.append({"role": "system", "content": "You are a helpful assistant that provides responses in JSON format."})
    
    # Add user prompt with explicit JSON request
    messages.append({"role": "user", "content": f"{prompt}\nPlease provide your response in JSON format that matches the expected structure."})
    
    try:
        response = client.chat.completions.create(
            model="gpt-4-1106-preview",  # Use a specific model that supports JSON output
            messages=messages,
            response_format={"type": "json_object"}
        )
        
        if not response.choices:
            print("No response received from the model")
            return None
            
        content = response.choices[0].message.content
        if not content:
            print("Empty content received from the model")
            return None
            
        try:
            # Parse the JSON string into a dictionary
            data = json.loads(content)
            # Create a Pydantic model instance from the dictionary
            return model_class(**data)
        except (json.JSONDecodeError, ValueError) as e:
            print(f"Error parsing model response: {e}")
            print(f"Raw content: {content}")
            return None
            
    except Exception as e:
        print(f"Error in API call: {e}")
        return None
        