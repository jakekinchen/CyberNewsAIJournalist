import openai
from dotenv import load_dotenv
import os
from supabase import create_client, Client
import json
import logging
import re
import tiktoken
import asyncio
import requests

# Load .env file
load_dotenv()
bing_api_key = os.getenv('BING_SEARCH_KEY')

# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

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

logging.basicConfig(level=logging.DEBUG, format='%(asctime)s - %(levelname)s - %(message)s')

def fetch_sources_from_query(query):
    print("Fetching sources from query: " + query)
    # Bing Search V7 endpoint
    endpoint = "https://api.bing.microsoft.com/v7.0/search"

    # Call the Bing API
    mkt = 'en-US'
    params = {'q': query, 'mkt': mkt, 'count': 3, 'responseFilter': 'webpages', 'answerCount': 1, 'safeSearch': 'strict'}
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}  # replace with your Bing API key

    logging.info(f"Querying Bing API with query: {query}")

    try:
        response = requests.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
    except requests.RequestException as e:
        logging.error(f"Failed to get response from Bing API: {str(e)}")
        return []

    try:
        search_result = response.json()
    except ValueError as e:
        logging.error(f"Failed to parse API response to JSON: {str(e)}")
        return []
    
    # Extract related sources
    related_sources = []

    if 'webPages' in search_result and 'value' in search_result['webPages']:
        #print("'webPages' in search_result and 'value' in search_result['webPages']")
        for i, result in enumerate(search_result['webPages']['value']):
            if all(key in result for key in ("name", "url")):
                source = {
                    'id': i,
                    "name": result['name'],
                    "url": result['url'],
                }
                related_sources.append(source)
    else:
        print("No 'webPages' or 'value' key in the response. No sources found.")

    return related_sources

def insert_tech_term_link(content: str, tech_term: str) -> str:
    # Construct the hyperlink
    link = generate_link_from_term(tech_term)
    hyperlink = f'<a href="{link}">{tech_term}</a>'

    if not hyperlink:
        print(f"Failed to generate hyperlink for tech term {tech_term}. Returning the original content.")
        return content
    
    # Define a flag to indicate whether the tech_term has been replaced
    replaced = False

    def repl(match):
        nonlocal replaced
        block = match.group(0)
        if not replaced and tech_term.lower() in block.lower():  # Case-insensitive search
            replaced = True
            # Replace only the first occurrence in the block, case-insensitive
            return re.sub(tech_term, hyperlink, block, flags=re.IGNORECASE, count=1)  
        return block

    # Use re.sub to find <p>...</p> blocks and apply the repl function to each block
    modified_content, _ = re.subn(r'<p>.*?</p>', repl, content, flags=re.DOTALL)

    # If no replacement has been done, log a warning and return the original content
    if not replaced:
        print(f"Tech term {tech_term} not found in the content. Returning the original content.")
    return modified_content


def generate_link_from_term(term):
    sources = fetch_sources_from_query(term)
    if not sources:
        print(f"Failed to find sources for term {term}")
        return None
    
    # Selects best source by integer id
    source_id = select_tech_term_source(sources)
    if not source_id:
        print(f"Failed to select source from sources - returning the first source's url")
        # Return the first source's url if there is at least one source, else return None
        return sources[0]['url'] if sources else None
    print(f"Selected source ID: {source_id}")

    # Select the source whose integer is equal to the id of the source that best defines the tech term
    source = next((source for source in sources if source['id'] == source_id), None)
    print(f"Selected source: {source}")

    # Return the url of the source if source is not None, else return None
    return source['url'] if source else None

def select_tech_term_source(sources):
    functions = [
            {
                "name": "TechTermSourceSelector",
                "description": "Select the source that best defines the tech term.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    'source': {
                        'type': 'integer',
                        'description': 'The id of the source that best defines the tech term.',
                        }
                    },
                    
                }
            }
        ]
    system_prompt = "You are a tech term source selector that selects the source that would be best for defining the tech term. This source should be the most relevant to the tech term and should be the most concise."
    user_prompt = f"Select the source that best defines the tech term: {sources}"
    try:
        response = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo", functions)
        source_id = response.get('source', None)
        logging.debug(f"Source ID from GPT response: {source_id}")
        if source_id is None:
            print(f"Expected key 'source' not found in data from GPT.")
            print(f"Here is the GPT response: {response}")
        return source_id
    except KeyError:
        logging.error("Expected key 'source' not found in data from GPT.")
        return None
        

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
        print (f"Failed to call function: {err}")

def query_gpt(user_prompt, system_prompt="You are a response machine that only responds with the requested information", model='gpt-3.5-turbo'):
    context = f"{system_prompt} {user_prompt}"
    try:
        model = model_optimizer(context, model)
    except Exception as e:
        logging.error(e)
        raise Exception(e)
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            request_timeout = 150,
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
        except Exception as gpt3_error:
            print(f'Failed to synthesize facts for source {source["id"]} with model', gpt3_error)
            return None
        facts_json = json.dumps(facts)
        supabase.table('sources').update({"factsheet": facts_json}).eq('id', source['id']).execute()
        return facts
    else:
        print(f'Factsheet already exists for source {source["id"]}')
        return None

def create_factsheets_for_sources(topic):
    related_sources = get_related_sources(topic['id'])
    combined_factsheet = ""
    external_source_info = []
    for source in related_sources:
        source_factsheet = create_factsheet(source, topic['name']) if not source['factsheet'] else source['factsheet']
        if not source_factsheet:
            print(f"Failed to create factsheet for source {source['id']}")
            continue
        if source['external_source']:
            external_source_info.append({
                "id": source['id'],
                "url": source['url'],
                "factsheet": source_factsheet
            })
        else:
            combined_factsheet += str(source_factsheet)
    
    if combined_factsheet:
        combined_factsheet = aggregate_factsheets(topic, combined_factsheet)
    else:
        print(f"Sources: {related_sources}")
        print("No factsheets to aggregate")
        return None, None

    if external_source_info:
        #external_source_info = remove_unrelated_sources(topic['name'], external_source_info)
        update_external_source_info(topic['id'], external_source_info)
    
    return combined_factsheet, external_source_info

def get_related_sources(topic_id):
    try:
        response = supabase.table('sources').select('*').eq('topic_id', topic_id).execute()
        return response.data or []
    except Exception as e:
        print(f'Failed to get related sources for topic {topic_id}', e)
        return []

def update_external_source_info(topic_id, external_source_info):
    formatted_info = ",".join([f"{info['id']}:{info['url']}:[{info['factsheet']}]" for info in external_source_info])
    try:
        response = supabase.table('topics').update({"external_source_info": formatted_info}).eq('id', topic_id).execute()
    except Exception as e:
        print(f'Failed to update external source info for topic {topic_id}', e)

def remove_unrelated_sources(topic_name, external_source_info):
    unrelated_source_ids = identify_unrelated_sources(topic_name, external_source_info)

    if unrelated_source_ids:
        remove_sources_from_supabase(unrelated_source_ids)
        external_source_info = [source_info for source_info in external_source_info if source_info['id'] not in unrelated_source_ids]
    return external_source_info
    
def identify_unrelated_sources(topic_name, external_source_info):
    print(f"We have {len(external_source_info)} external sources to check for topic {topic_name}")
    formatted_sources = ",".join([f"{info['id']}:{info['url']}:[{info['factsheet']}]" for info in external_source_info])
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
        gpt_response = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo-16k", functions)
        
        # Extracting the source IDs directly from the response
        unrelated_source_ids = gpt_response.get('sources', [])
        
        return unrelated_source_ids
    except KeyError:
        print(f"Expected key 'sources' not found in data from GPT.")
        return []
    except ValueError:
        print(f"One of the source IDs from GPT is not an integer.")
        return []
    except Exception as e:
        print(f"Failed to identify unrelated sources for topic {topic_name}: {e}")
        return []
    
def delete_source(source_id):
    # Delete the topic
    try:
        response = supabase.table("sources").delete().eq("id", source_id).execute()
    except Exception as e:
        print(f"Failed to delete source: {e}")
        return
    print(f"Successfully deleted source with ID {source_id} and all related sources.")

def remove_sources_from_supabase(unrelated_source_ids):
    try:
        for source_id in unrelated_source_ids:
            # Assuming you have a function to remove a source by id from Supabase
            delete_source(source_id)
        print(f"Removed unrelated sources: {', '.join(map(str, unrelated_source_ids))}")
    except Exception as e:
        print(f"Failed to remove unrelated sources: {', '.join(map(str, unrelated_source_ids))}. Error: {e}")

def aggregate_factsheets(topic, combined_factsheet):
    try:
        if combined_factsheet:
            system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail. You utilize a lossless compression algorithm to keep the factual details together"
            user_prompt = f"When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to {topic['name']}. Now give the factsheet for the following information: {combined_factsheet} "
            facts = query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
            facts_json = json.dumps(facts)
            supabase.table('topics').update({"factsheet": facts_json}).eq('id', topic['id']).execute()
            return facts
        else:
            raise Exception("No factsheets to aggregate")
    except Exception as gpt3_error:
        logging.error(f'Failed to synthesize factsheets for topic {topic["id"]}', gpt3_error)

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
            facts_json = json.dumps(facts)
            supabase.table('topics').update({"factsheet": facts_json}).eq('id', topic['id']).execute()
            return facts
        except Exception as gpt3_error:
            logging.error(f'Failed to synthesize factsheets from topic {topic["id"]}', gpt3_error)


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
        raise Exception(f"Failed to regenerate image queries: {e}")




