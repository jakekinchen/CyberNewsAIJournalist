import os
import httpx
from dotenv import load_dotenv
from datetime import datetime
import logging
from supabase_utils import supabase
import re
import json
import asyncio
from gpt_utils import query_gpt, function_call_gpt, tokenizer, source_remover_function, generate_factsheet_user_prompt
import prompts
from google_cse import fetch_sources_from_google_cse
from enum import Enum
from openai import OpenAI
import tiktoken
from thn_scraper import scrape_thn_article
from enhanced_scraper import EnhancedScraper

# Load .env file
load_dotenv()

bing_api_key = os.getenv('BING_SEARCH_KEY')
summarization_model = os.getenv('SUMMARIZATION_MODEL', 'gpt-4o-mini-2024-07-18')

class SourceFetchStrategy(Enum):
    BING = "bing"
    GOOGLE_CSE = "google_cse"

DEFAULT_FETCH_STRATEGY = os.getenv('DEFAULT_SOURCE_FETCH_STRATEGY', SourceFetchStrategy.BING.value)

# NEW HELPER METHOD:
# -----------------------------------------------------------------
# This method fetches and merges all previous facts for the same topic,
# so we can avoid repeating them in any new factsheet.
def gather_existing_facts_for_topic(topic_id):
    try:
        response = supabase.table('sources').select('factsheet').eq('topic_id', topic_id).execute()
        previous_factsheets = response.data or []
    except Exception as e:
        print(f"Failed to gather existing facts for topic {topic_id}: {e}")
        previous_factsheets = []
    
    # Combine all existing factsheets into a single text block
    combined_facts = []
    for row in previous_factsheets:
        factsheet_text = row.get('factsheet')
        if factsheet_text:
            combined_facts.append(factsheet_text)
    return "\n".join(combined_facts)

# CHANGED create_factsheet (targeted edits only):
# -----------------------------------------------------------------
async def create_factsheet(source, topic_name):
    print(f"DEBUG: Starting create_factsheet for source {source.get('id')}")
    
    # First check if this source already has a factsheet
    if source.get('factsheet'):
        print(f"Factsheet already exists for source {source['id']}")
        return source['factsheet']
        
    # Then check if any other source with the same URL has a factsheet
    try:
        response = supabase.table('sources').select('*').eq('url', source['url']).execute()
        existing_sources = response.data
        
        if existing_sources:
            for existing_source in existing_sources:
                if existing_source.get('factsheet'):
                    print(f"Reusing existing factsheet from source {existing_source['id']} for URL {source['url']}")
                    existing_factsheet = existing_source['factsheet']
                    try:
                        if isinstance(existing_factsheet, str):
                            existing_factsheet = json.loads(existing_factsheet)
                    except json.JSONDecodeError:
                        pass  # Keep original string if not valid JSON
                        
                    # Update this source's factsheet in the background
                    asyncio.create_task(
                        update_source_factsheet(source['id'], existing_factsheet)
                    )
                    return existing_factsheet
    except Exception as e:
        print(f"Error checking for existing sources: {e}")
    
    try:
        # Initialize OpenAI client
        client = OpenAI()
        
        # Prepare the prompts
        system_prompt = """You are an expert at extracting and summarizing key information from cybersecurity articles.
        Create a comprehensive factsheet that includes:
        1. The main security issue or incident
        2. Technical details and impact
        3. Affected systems or organizations
        4. Recommendations or mitigations if any
        5. Timeline of events if applicable
        Format the output as a clear, bulleted list."""
        
        # Get existing facts if any
        existing_facts = gather_existing_facts_for_topic(source['topic_id'])
        
        # Clean and prepare content
        content = source.get('content', '')
        if not content:
            print(f"Warning: No content found for source {source.get('id')}")
            return None
            
        # Remove extra whitespace but preserve paragraphs
        content = re.sub(r'\s+', ' ', content)
        content = re.sub(r'\n\s*\n', '\n\n', content)
        
        user_prompt = (
            f"Article Title: {topic_name}\n\n"
            f"Previous Facts:\n{existing_facts}\n\n"
            f"New Article Content:\n{content}\n\n"
            f"Create a factsheet with new or distinct information from this article that isn't covered in the previous facts. "
            f"Focus on technical details, impact, and actionable information. "
            f"If this is a CVE, include the CVE ID, CVSS score, affected systems, and mitigation steps if available."
        )
        
        print("DEBUG: Making API call for source", source.get('id'))
        print(f"DEBUG: Using model: {summarization_model}")
        
        # Split content if it's too long
        max_tokens = 14000  # Adjust based on your model's context window
        encoding = tiktoken.encoding_for_model("gpt-4")  # Use appropriate encoding for the model
        content_tokens = len(encoding.encode(content))
        
        if content_tokens > max_tokens:
            print(f"Warning: Content too long ({content_tokens} tokens), splitting into chunks")
            chunks = []
            current_chunk = []
            current_length = 0
            
            # Split content into sentences
            sentences = re.split(r'(?<=[.!?])\s+', content)
            current_chunk = []
            current_tokens = 0
            
            for sentence in sentences:
                sentence_tokens = len(encoding.encode(sentence))
                if current_tokens + sentence_tokens <= max_tokens:
                    current_chunk.append(sentence)
                    current_tokens += sentence_tokens
                else:
                    chunks.append(' '.join(current_chunk))
                    current_chunk = [sentence]
                    current_tokens = sentence_tokens
                    
            if current_chunk:
                chunks.append(' '.join(current_chunk))
                
            # Process each chunk
            all_facts = []
            for i, chunk in enumerate(chunks):
                chunk_prompt = f"{user_prompt}\n\nProcessing Part {i+1} of {len(chunks)}:\n{chunk}"
                response = client.chat.completions.create(
                    model=summarization_model,
                    messages=[
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": chunk_prompt}
                    ]
                )
                all_facts.append(response.choices[0].message.content)
            
            facts = "\n".join(all_facts)
        else:
            response = client.chat.completions.create(
                model=summarization_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ]
            )
            facts = response.choices[0].message.content
        
        print("DEBUG: API call completed for source", source.get('id'))
        
        if facts:
            # Update the database in the background
            asyncio.create_task(
                update_source_factsheet(source['id'], facts)
            )
            return facts
            
    except Exception as e:
        print(f"ERROR: Failed to create factsheet: {e}")
        return None

async def update_source_factsheet(source_id, facts_json):
    """Update the source's factsheet in the database."""
    try:
        await asyncio.to_thread(
            lambda: supabase.table('sources')
            .update({"factsheet": facts_json})
            .eq('id', source_id)
            .execute()
        )
    except Exception as e:
        print(f"ERROR: Failed to update factsheet in database: {e}")

# CHANGED create_factsheets_for_sources (only small changes noted):
# -----------------------------------------------------------------
async def create_factsheets_for_sources(topic):
    related_sources = get_related_sources(topic['id'])
    print(f"DEBUG: Found {len(related_sources)} related sources for topic {topic['id']}")
    combined_factsheet = ""
    external_source_info = []
    
    # Create tasks for each source's factsheet
    tasks = []
    for source in related_sources:
        if not source['factsheet']:
            tasks.append(create_factsheet(source, topic['name']))
        else:
            tasks.append(source['factsheet'])
    
    print(f"DEBUG: Created {len(tasks)} factsheet tasks")
    
    # Use asyncio.gather to run tasks concurrently and get results
    factsheets = []
    for task in tasks:
        if asyncio.iscoroutine(task):
            factsheets.append(await task)
        else:
            factsheets.append(task)
    
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
    
    if combined_factsheet:
        combined_factsheet = aggregate_factsheets(topic, combined_factsheet)
    else:
        print(f"Sources: {related_sources}")
        print("No factsheets to aggregate")
        return None, None
    
    if external_source_info:
        update_external_source_info(topic['id'], external_source_info)
    
    return combined_factsheet, external_source_info


def aggregate_factsheets(topic, combined_factsheet):
    try:
        if combined_factsheet:
            system_prompt = prompts.combined_factsheet_system_prompt
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
    try:
        response = supabase.table('sources').select('*').eq('topic_id', topic['id']).execute()
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
    formatted_info = ",".join([
        f"{info['id']}:{info['url']}:[{info['factsheet']}]"
        for info in external_source_info
    ])
    try:
        supabase.table('topics').update({"external_source_info": formatted_info}).eq('id', topic_id).execute()
    except Exception as e:
        print(f'Failed to update external source info for topic {topic_id}', e)

def remove_unrelated_sources(topic_name, external_source_info):
    unrelated_source_ids = identify_unrelated_sources(topic_name, external_source_info)
    if unrelated_source_ids:
        remove_sources_from_supabase(unrelated_source_ids)
        external_source_info = [
            source_info for source_info in external_source_info 
            if source_info['id'] not in unrelated_source_ids
        ]
    return external_source_info

def identify_unrelated_sources(topic_name, external_source_info):
    print(f"We have {len(external_source_info)} external sources to check for topic {topic_name}")
    formatted_sources = ",".join([
        f"{info['id']}:{info['url']}:[{info['factsheet']}]"
        for info in external_source_info
    ])
    system_prompt = "You are a source remover that removes sources that are not related to the topic."
    user_prompt = f"List the source id's that are not related to {topic_name} from the following list: {formatted_sources}"
    functions = source_remover_function
    try:
        gpt_response = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo-16k", functions)
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
    try:
        supabase.table("sources").delete().eq("id", source_id).execute()
    except Exception as e:
        print(f"Failed to delete source: {e}")
        return
    print(f"Successfully deleted source with ID {source_id} and all related sources.")

def remove_sources_from_supabase(unrelated_source_ids):
    try:
        for source_id in unrelated_source_ids:
            delete_source(source_id)
        print(f"Removed unrelated sources: {', '.join(map(str, unrelated_source_ids))}")
    except Exception as e:
        print(f"Failed to remove unrelated sources: {', '.join(map(str, unrelated_source_ids))}. Error: {e}")

def fetch_sources_from_query(query, strategy=None):
    """Fetch sources using the specified strategy."""
    if strategy is None:
        strategy = DEFAULT_FETCH_STRATEGY
    strategy = SourceFetchStrategy(strategy)
    
    # Add cybersecurity context to the query if needed
    if not any(term in query.lower() for term in ['cve', 'vulnerability', 'security', 'hack', 'breach', 'exploit']):
        query = f"cybersecurity {query}"
        
    if strategy == SourceFetchStrategy.GOOGLE_CSE:
        return fetch_sources_from_google_cse(query)
    else:
        return fetch_sources_from_bing(query)

def fetch_sources_from_bing(query):
    print("Fetching sources from Bing with query: " + query)
    endpoint = "https://api.bing.microsoft.com/v7.0/search"
    mkt = 'en-US'
    params = {
        'q': query, 
        'mkt': mkt, 
        'count': 3, 
        'responseFilter': 'webpages', 
        'answerCount': 1, 
        'safeSearch': 'strict'
    }
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}
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
    related_sources = []
    if 'webPages' in search_result and 'value' in search_result['webPages']:
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
    token_quantity = tokenizer(content, 'gpt-3.5-turbo-16k')
    if token_quantity >= 16384:
        logging.warning(f"Source content exceeds the limit: {token_quantity}")
        return True

async def gather_and_store_sources(supabase, url, topic_id, date_accessed, depth, existing_sources, accumulated_sources):
    # Initialize enhanced scraper
    scraper = EnhancedScraper()
    
    # Use enhanced scraper to get content
    content = await scraper.scrape(url)
    if not content:
        print(f"Failed to fetch content from {url}")
        return accumulated_sources

    source_data = {
        "url": url,
        "content": content,
        "topic_id": topic_id,
        "date_accessed": date_accessed,
        "external_source": True if depth > 0 else False
    }

    try:
        supabase.table("sources").insert([source_data]).execute()
        print(f"Successfully stored source from {url}")
        accumulated_sources.append(source_data)
    except Exception as e:
        print(f"Failed to store source: {e}")
        return accumulated_sources

    # Note: External link gathering is now handled by the enhanced scraper
    # We'll focus on the main content for now
    return accumulated_sources

async def gather_sources(supabase, topic, MIN_SOURCES=2, overload=False, depth=2, fetch_strategy=None):
    """Gather sources for a topic."""
    print(f"Processing topic URL: {topic['url']}")
    
    try:
        # Get existing sources first
        existing_sources = get_related_sources(topic['id'])
        existing_urls = set(source['url'] for source in existing_sources)
        
        if existing_sources:
            print(f"Found {len(existing_sources)} existing sources")
            if len(existing_sources) >= MIN_SOURCES:
                return existing_sources
                
        # Initialize our enhanced scraper
        scraper = EnhancedScraper()
        
        # Create source from topic URL
        try:
            content = None
            
            # Check if it's a TheHackersNews URL
            if 'thehackernews.com' in topic['url']:
                print(f"Using specialized THN scraper for {topic['url']}")
                title, content = await scrape_thn_article(topic['url'])
            else:
                # Use our enhanced scraper
                print(f"Using enhanced scraper for {topic['url']}")
                content = await scraper.scrape(topic['url'])
                
            if not content or len(content.strip()) < 100:
                print(f"Failed to get sufficient content from {topic['url']}")
                return existing_sources

            # Clean up the content
            if content:
                # Remove excessive whitespace but preserve paragraphs
                content = re.sub(r'\s+', ' ', content)
                content = re.sub(r'\n\s*\n', '\n\n', content)
                
            # Create source record
            source_record = {
                'topic_id': topic['id'],
                'url': topic['url'],
                'content': content,
                'date_accessed': datetime.now().isoformat(),
                'external_source': False
            }
            
            # Insert into database if URL not already present
            if topic['url'] not in existing_urls:
                response = supabase.table('sources').insert(source_record).execute()
                if response.data:
                    accumulated_sources = response.data
                    existing_urls.add(topic['url'])
                    print(f"Successfully stored source from {topic['url']}")
                else:
                    print(f"Failed to store source from {topic['url']}")
                    accumulated_sources = []
            else:
                print(f"Source {topic['url']} already exists, skipping...")
                accumulated_sources = []
                
        except Exception as e:
            print(f"Error processing source {topic['url']}: {e}")
            accumulated_sources = []
            
        # Combine existing and new sources
        all_sources = existing_sources + accumulated_sources
        print(f"Total sources gathered: {len(all_sources)}")
        
        # If we don't have enough sources, try to find more using search
        if len(all_sources) < MIN_SOURCES:
            print(f"Looking for additional sources for topic: {topic['name']}")
            additional_sources = search_related_sources(topic['name'])
            if additional_sources:
                for source in additional_sources:
                    if len(all_sources) >= MIN_SOURCES:
                        break
                        
                    # Skip if URL already exists
                    if source['url'] in existing_urls:
                        print(f"Source {source['url']} already exists, skipping...")
                        continue
                        
                    try:
                        # Use enhanced scraper for additional sources
                        print(f"Using enhanced scraper for additional source: {source['url']}")
                        content = await scraper.scrape(source['url'])
                        
                        if content and len(content.strip()) >= 100:
                            source_record = {
                                'topic_id': topic['id'],
                                'url': source['url'],
                                'content': content,
                                'date_accessed': datetime.now().isoformat(),
                                'external_source': True
                            }
                            response = supabase.table('sources').insert(source_record).execute()
                            if response.data:
                                all_sources.extend(response.data)
                                existing_urls.add(source['url'])
                                print(f"Added additional source: {source['url']}")
                    except Exception as e:
                        print(f"Error adding additional source {source['url']}: {e}")
                        continue
                
        return all_sources
        
    except Exception as e:
        print(f"Error gathering sources: {e}")
        return existing_sources

def search_related_sources(query, offset=0, fetch_strategy=None):
    """Search for related sources, filtering out irrelevant ones."""
    # Clean up the query
    query = re.sub(r'[^\w\s-]', '', query)  # Remove special characters
    query = query.strip()
    
    # Check if this is a CVE query
    is_cve = bool(re.match(r'^CVE\s*[-:]\s*CVE-\d{4}-\d+', query, re.IGNORECASE))
    
    # Add cybersecurity context to the query
    if not is_cve and not any(term in query.lower() for term in ['cve', 'vulnerability', 'security', 'hack', 'breach', 'exploit']):
        query = f"cybersecurity {query}"
    
    # Get initial sources
    sources = fetch_sources_from_query(query, fetch_strategy)
    
    # Filter out irrelevant sources
    filtered_sources = []
    for source in sources:
        url = source.get('url', '').lower()
        
        # Skip if URL is from unwanted domains or sections
        if any(pattern in url for pattern in [
            '/search/', 
            '/category/',
            '/tag/',
            '/archive/',
            '/author/',
            '/feed/',
            '/rss/',
            'index.html',
            '/section/',
            '/topic/',
            'google.com',
            'facebook.com',
            'twitter.com',
            'linkedin.com',
            'instagram.com',
            'youtube.com'
        ]):
            print(f"Skipping non-article URL: {url}")
            continue
        
        # For CVE topics, prioritize official sources
        if is_cve:
            if any(domain in url for domain in [
                'nvd.nist.gov/vuln/detail',
                'cve.mitre.org',
                'cisa.gov/known-exploited-vulnerabilities',
                'msrc.microsoft.com/update-guide/vulnerability',
                'security.snyk.io',
                'vuldb.com',
                'rapid7.com/db',
                'tenable.com/cve'
            ]):
                filtered_sources.append(source)
                print(f"Added official CVE source: {url}")
                continue
                
        # For non-CVE topics or if we need more sources, check reputable security news sources
        if not is_cve or len(filtered_sources) < 3:
            if any(domain in url for domain in [
                'krebsonsecurity.com',
                'thehackernews.com',
                'bleepingcomputer.com',
                'securityweek.com',
                'darkreading.com',
                'threatpost.com',
                'zdnet.com/security',
                'techcrunch.com/security',
                'arstechnica.com/security',
                'cyberscoop.com',
                'theregister.com/security',
                'infosecurity-magazine.com',
                'scmagazine.com',
                'cso.com',
                'helpnetsecurity.com',
                'cisomag.com',
                'cybersecuritynews.com',
                'securitymagazine.com',
                'techradar.com/security',
                'microsoft.com/security',
                'security.googleblog.com',
                'nvd.nist.gov',
                'cisa.gov'
            ]):
                filtered_sources.append(source)
                print(f"Added security news source: {url}")
                continue
        
    return filtered_sources[:3]  # Limit to top 3 most relevant sources

def search_related_articles(topic):
    endpoint = "https://api.bing.microsoft.com/v7.0/news/search"
    mkt = 'en-US'
    params = {'q': topic['title'], 'mkt': mkt, 'count': 5}
    headers = {'Ocp-Apim-Subscription-Key': bing_api_key}
    print("Querying Bing API with topic: " + str(topic))
    response = httpx.get(endpoint, headers=headers, params=params)
    response.raise_for_status()
    news_result = response.json()
    
    related_articles = []
    if news_result['value']:
        for result in news_result['value']:
            if all(key in result for key in ("name", "url", "description", "datePublished", "provider")):
                article = {
                    "name": result['name'],
                    "url": result['url'],
                    "description": result['description'],
                    "date_published": result['datePublished'],
                    "provider": result['provider'][0]['name'] if result['provider'] else None
                }
                related_articles.append(article)
    return related_articles