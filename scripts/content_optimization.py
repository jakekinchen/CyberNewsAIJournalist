import openai
from dotenv import load_dotenv
import os
from supabase import create_client, Client
import json
import logging
import re
import asyncio

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
            facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo')
        except Exception as gpt3_error:
            print(f'Failed to synthesize facts for source {source["id"]} with base model', gpt3_error)
            try: 
                facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
            except Exception as gpt3_error:
                print(f'Failed to synthesize facts for source {source["id"]} with 16k model', gpt3_error)
                return None
            facts_json = json.dumps(facts)
            supabase.table('sources').update({"factsheet": facts_json}).eq('id', source['id']).execute()
            return facts
        facts_json = json.dumps(facts)
        supabase.table('sources').update({"factsheet": facts_json}).eq('id', source['id']).execute()
        return facts
    else:
        print(f'Factsheet already exists for source {source["id"]}')
        return None

def create_factsheets_for_sources(topic):
    related_sources = get_related_sources(topic['id'])
    combined_factsheet = ""
    external_sources_info = []

    for source in related_sources:
        source_factsheet = create_factsheet(source, topic['name']) if not source['factsheet'] else source['factsheet']

        if source['external_source']:
            external_sources_info.append({
                "id": source['id'],
                "url": source['url'],
                "factsheet": source_factsheet
            })
        else:
            combined_factsheet += str(source_factsheet)
    
    combined_factsheet = aggregate_factsheets(topic, combined_factsheet)

    if external_sources_info:
        external_sources_info = remove_unrelated_sources(topic['name'], external_sources_info)
        update_external_source_info(topic['id'], external_sources_info)
    
    return combined_factsheet, external_sources_info

def get_related_sources(topic_id):
    try:
        response = supabase.table('sources').select('*').eq('topic_id', topic_id).execute()
        return response.data or []
    except Exception as e:
        print(f'Failed to get related sources for topic {topic_id}', e)
        return []

def update_external_source_info(topic_id, external_sources_info):
    formatted_info = ",".join([f"{info['id']}:{info['url']}:[{info['factsheet']}]" for info in external_sources_info])
    try:
        response = supabase.table('topics').update({"external_source_info": formatted_info}).eq('id', topic_id).execute()
    except Exception as e:
        print(f'Failed to update external source info for topic {topic_id}', e)

def remove_unrelated_sources(topic_name, external_sources_info):
    unrelated_source_ids = identify_unrelated_sources(topic_name, external_sources_info)

    if unrelated_source_ids:
        asyncio.run(remove_sources_from_supabase(unrelated_source_ids))
        external_sources_info = [source_info for source_info in external_sources_info if source_info['id'] not in unrelated_source_ids]
    return external_sources_info
    
def identify_unrelated_sources(topic_name, external_sources_info):
    formatted_sources = ",".join([f"{info['id']}:{info['url']}:[{info['factsheet']}]" for info in external_sources_info])
    system_prompt = "You are a source remover that removes sources that are not related to the topic."
    user_prompt = f"List the source id's that are not related to {topic_name} from the following list: {formatted_sources}"
    functions = [
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

    try:
        # Assuming function_call_gpt returns a list of unrelated source ids
        unrelated_source_ids = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo-16k", functions)
        return unrelated_source_ids
    except Exception as e:
        print(f"Failed to identify unrelated sources for topic {topic_name}: {e}")
        return []
    
async def delete_source(source_id):
    # Delete the topic
    try:
        response = supabase.table("sources").delete().eq("id", source_id).execute()
    except Exception as e:
        print(f"Failed to delete topic: {e}")
        return
    print(f"Successfully deleted topic with ID {source_id} and all related sources.")

async def remove_sources_from_supabase(unrelated_source_ids):
    try:
        for source_id in unrelated_source_ids:
            # Assuming you have a function to remove a source by id from Supabase
            await delete_source(source_id)
        print(f"Removed unrelated sources: {', '.join(map(str, unrelated_source_ids))}")
    except Exception as e:
        print(f"Failed to remove unrelated sources: {', '.join(map(str, unrelated_source_ids))}. Error: {e}")

def aggregate_factsheets(topic, combined_factsheet):
    try:
        if combined_factsheet:
            system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail. You utilize a lossless compression algorithm to keep the factual details together"
            user_prompt = f"When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to {topic['name']}. Now give the factsheet for the following information: {combined_factsheet} "
            facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
            print(f"Aggregated factsheet: {facts}")
            facts_json = json.dumps(facts)
            supabase.table('topics').update({"factsheet": facts_json}).eq('id', topic['id']).execute()
            return facts
        else:
            logging.error("No factsheets to aggregate")
            return None
    except Exception as gpt3_error:
        logging.error(f'Failed to synthesize facts for topic {topic["id"]}', gpt3_error)

def aggregate_factsheets_from_topic(topic):
    # Get all of the factsheets for the topic, and query gpt to aggregate them into a single factsheet
    # Then update the topic's factsheet in supabase
    try:
        response = supabase.table('sources').select('*').eq('topic_id', topic['id']).execute()
        #print(f"Sources queried:{response.data}") functions properly
        related_sources = response.data or []
    except Exception as e:
        print(f'Failed to get related sources for topic {topic["id"]}', e)
        return
    if related_sources:
        system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail. You utilize a lossless compression algorithm to keep the factual details together"
        user_prompt = f"When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to {topic['name']}. Now give the factsheet for the following information: {related_sources} "
        try:
            facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
            print(f"Aggregated factsheet: {facts}")
            facts_json = json.dumps(facts)
            supabase.table('topics').update({"factsheet": facts_json}).eq('id', topic['id']).execute()
            return facts
        except Exception as gpt3_error:
            logging.error(f'Failed to synthesize facts for topic {topic["id"]}', gpt3_error)


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




