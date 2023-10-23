import os
import httpx
from dotenv import load_dotenv
from datetime import datetime
from extract_text import scrape_content
import logging
from supabase_utils import supabase
import re
import json
import asyncio
from gpt_utils import query_gpt, function_call_gpt, tokenizer, source_remover_function, generate_factsheet_user_prompt

# Load .env file
load_dotenv()

# Access your API keys
bing_api_key = os.getenv('BING_SEARCH_KEY')

async def create_factsheet(source, topic_name):
    # if source's factsheet is empty or null
    if not source['factsheet']:
        # Sanitize content by replacing newline characters with a space
        sanitized_content = re.sub(r'[\n\r]', ' ', source['content'])
        system_prompt = os.getenv('FACTSHEET_SYSTEM_PROMPT')
        user_prompt = generate_factsheet_user_prompt(sanitized_content, topic_name)
        try:
            loop = asyncio.get_event_loop()
            facts = await loop.run_in_executor(None, query_gpt, user_prompt, system_prompt, 'gpt-3.5-turbo-16k')
        except Exception as gpt3_error:
            print(f'Failed to synthesize facts for source {source["id"]} with model', gpt3_error)
            return None
        facts_json = json.dumps(facts) 
        # Assuming supabase update is also async, if not wrap it in run_in_executor
        loop = asyncio.get_event_loop()
        await loop.run_in_executor(None, supabase.table('sources').update({"factsheet": facts_json}).eq('id', source['id']).execute)
        return facts
    else:
        print(f'Factsheet already exists for source {source["id"]}')
        return None

async def create_factsheets_for_sources(topic):
    related_sources = get_related_sources(topic['id'])
    combined_factsheet = ""
    external_source_info = []
    # Create tasks for each source's factsheet
    tasks = []
    for source in related_sources:
        if not source['factsheet']:
            tasks.append(create_factsheet(source, topic['name']))
        else:
            tasks.append(source['factsheet'])
    # Use asyncio.gather to run tasks concurrently and get results
    factsheets = await asyncio.gather(*tasks)
    # Process the results
    for idx, source_factsheet in enumerate(factsheets):
        source = related_sources[idx]
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
    # Rest of your method remains largely unchanged
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

def aggregate_factsheets(topic, combined_factsheet):
    try:
        if combined_factsheet:
            system_prompt = os.getenv('COMBINED_FACTSHEET_SYSTEM_PROMPT')
            user_prompt = generate_factsheet_user_prompt(topic['name'], combined_factsheet)
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
    functions = source_remover_function
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

def fetch_sources_from_query(query):
    print("Fetching sources from query: " + query)
    # Bing Search V7 endpoint
    endpoint = os.getenv('BING_SEARCH_ENDPOINT')
    # Call the Bing API
    mkt = 'en-US'
    params = {'q': query, 'mkt': mkt, 'count': 3, 'responseFilter': 'webpages', 'answerCount': 1, 'safeSearch': 'strict'}
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}  # replace with your Bing API key
    logging.info(f"Querying Bing API with query: {query}")
    try:
        response = httpx.get(endpoint, headers=headers, params=params)
        response.raise_for_status()
    except httpx.RequestError as e:
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

def check_if_content_exceeds_limit(content):
    # Check if the source content exceeds the limit
    token_quantity = tokenizer(content, 'gpt-3.5-turbo-16k')
    if token_quantity >= 16384:
        logging.warning(f"Source content exceeds the limit: {token_quantity}")
        return True

def gather_and_store_sources(supabase, url, topic_id, date_accessed, depth, existing_sources, accumulated_sources):
    content, external_links = scrape_content(url, depth=depth)
    # Append the current source into accumulated_sources if content is scraped successfully
    if content and not check_if_content_exceeds_limit(content):
        accumulated_sources.append({
            "url": url,
            "content": content,
            "topic_id": topic_id,
            "date_accessed": date_accessed,
            "external_source": depth < 2  # True if this source is an external link extracted from another source
        })
        existing_sources.add(url)  # Update the existing_sources set with the new URL
    
    # Recursively gather and store sources for external links found
    if depth > 1 and external_links:
        for link in external_links:
            gather_and_store_sources(supabase, link, topic_id, date_accessed, depth - 1, existing_sources, accumulated_sources)

def gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2):
    date_accessed = datetime.now().isoformat()

    response = supabase.table("sources").select("url").eq("topic_id", topic["id"]).execute()
    existing_sources = set([source['url'] for source in response.data]) if response.data else set()
    required_sources = MIN_SOURCES - len(existing_sources)

    if overload:
        required_sources += 3  # Increase the number if overloaded

    accumulated_sources = []
    if required_sources > 0:
        related_sources = search_related_sources(topic["name"], len(existing_sources))

        for source in related_sources:
            if len(accumulated_sources) >= required_sources:
                # Break once we've accumulated enough sources
                break
            
            if source['url'] == "https://thehackernews.com/search?" or "msn.com" in source['url'] or "twitter.com" in source['url']:  
                continue

            gather_and_store_sources(supabase, source["url"], topic["id"], date_accessed, depth, existing_sources, accumulated_sources)

    # Batch insert the accumulated sources into Supabase
    if accumulated_sources:
        try:
            response = supabase.table("sources").insert(accumulated_sources).execute()
        except Exception as e:
            print(f"Failed to insert sources into Supabase: {e}")

def search_related_sources(query, offset=0):
    # Call the Bing API
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"
    bing_api_key = os.getenv('BING_NEWS_KEY')
    params = {"q": query, "mkt": "en-US", "count": 10, "offset": offset}
    headers = {"Ocp-Apim-Subscription-Key": bing_api_key}
    response = httpx.get(endpoint, headers=headers, params=params)
    news_result = response.json()
    # Extract related sources
    related_sources = [
        {
            "topic_name": news_result["queryContext"]["originalQuery"],
            "name": result["name"],
            "url": result["url"],
            "description": result["description"],
            "date_published": result["datePublished"],
            "provider": result["provider"][0]["name"] if result["provider"] else None,
        }
        for result in news_result["value"]
    ]
    return related_sources

def search_related_articles(topic):
    # Bing Search V7 endpoint
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"
    # Call the Bing API
    mkt = 'en-US'
    params = {'q': topic['title'], 'mkt': mkt, 'count': 5}
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}
    print("Querying Bing API with topic: " + str(topic))
    response = httpx.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    news_result = response.json()
    # Extract related articles
    related_articles = []
    if news_result['value']:
        for result in news_result['value']:
            # Check if all keys exist
            if all(key in result for key in ("name", "url", "description", "datePublished", "provider")):
                article = {
                    "name": result['name'],
                    "url": result['url'],
                    "description": result['description'],
                    "date_published": result['datePublished'],
                    "provider": result['provider'][0]['name'] if result['provider'] else None  # Check if provider list is not empty
                }
                related_articles.append(article)
    return related_articles