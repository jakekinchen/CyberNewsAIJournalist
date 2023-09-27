import openai
from dotenv import load_dotenv
import os
from supabase import create_client, Client
import json
import logging
import re

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

def token_optimizer(text):
    message = f"{text}\n\nSummarize this but don't leave out any relevant facts"
    model = "gpt-3.5-turbo-16k"
    system = "You are an information compression algorithm that outputs the most relevant information in the least amount of words without losing any relevant information"
    response = query_gpt(message, system, model)
    logging.info(f"Token optimizer response: {response}")
    return response.choices[0].message.content

def prioritize_topics(topics):
    response = None
    message = f"Prioritize the following topics in order of relevance to Cybersecurity:\n\n{topics}"
    try:
        response = query_gpt(message, "You are a data computer that outputs the pure information as a list and nothing else")
    except openai.error.InvalidRequestError as e:
        if 'exceeded maximum number of tokens' in str(e):
            response = query_gpt(message, "You are a data computer that outputs the pure information as a list and nothing else", model="gpt-3.5-turbo-16k")
        else:
            raise e
    # Process the response to get a list of titles in order of relevance
    prioritized_titles = response.choices[0].message.content.split("\n")
    return prioritized_titles

def function_call_gpt(user_prompt, system_prompt, model, functions, function_call_mode='auto'):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            functions = functions, 
            function_call = function_call_mode
        )
        # If functions is not a null array then return response.choices[0].message.function_call.arguments then use json loads on it
        return json.loads(response.choices[0].message.function_call.arguments)
    except Exception as err:
        logging.error(err)

def query_gpt(user_prompt, system_prompt="You are a response machine that only responds with the requested information", model='gpt-3.5-turbo'):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
        )
        
        # If functions is not a null array then return response.choices[0].message.function_call.arguments then use json loads on it
        return response.choices[0].message.content
    except openai.error.APIConnectionError as err:
        logging.error(err)
    
def create_factsheet(source, topic_name):
    # if source's factsheet is empty or null
    if not source['factsheet']:
        # Sanitize content by replacing newline characters with a space
        sanitized_content = re.sub(r'[\n\r]', ' ', source['content'])
        
        system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail. You utilize a lossless compression algorithm to keep the factual details together"
        user_prompt = f"When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to {topic_name}. Now give the factsheet for the following information: {sanitized_content}"
        
        try:
            facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
            facts_json = json.dumps(facts)
            supabase.table('sources').update({"factsheet": facts_json}).eq('id', source['id']).execute()
            return facts
        except Exception as gpt3_error:
            print(f'Failed to synthesize facts for source {source["id"]}', gpt3_error)
    else:
        print(f'Factsheet already exists for source {source["id"]}')
        return None

def create_factsheet_for_topic(topic):
    try:
        response = supabase.table('sources').select('*').eq('topic_id', topic['id']).execute()
        #print(f"Sources queried:{response.data}") functions properly
        related_sources = response.data or []
    except Exception as e:
        print(f'Failed to get related sources for topic {topic["id"]}', e)
        return
    print("Initializing factsheets")
    combined_factsheet = ""
    for source in related_sources:
        if not source['factsheet']:
            combined_factsheet = combined_factsheet + str(create_factsheet(source, topic['name']))
            print(f"Added factsheet for source {source['id']}")
    return combined_factsheet

def regenerate_image_queries(post_info):
    system_prompt = "You are a stock photo database query generator that generates queries for stock photos that are relevant to the topic yet not too similar to each other. They should be simple and convey the meaning of the topic without going for obvious keywords like 'cybersecurity' or 'hacking'."
    user_prompt = f"Generate an array image queries for the following information: {post_info['content']}"
    functions = [
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
    try:
        logging.info("Regenerating image queries")
        image_queries = function_call_gpt(user_prompt, system_prompt, "gpt-3.5", functions)
        print(f"Image queries generated: {image_queries}")
        return image_queries
    except Exception as e:
        print(f"Failed to regenerate image queries: {e}")
        return None




