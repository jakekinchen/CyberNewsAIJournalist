import requests
import xml.etree.ElementTree as ET
import json
import logging
from datetime import datetime
from content_optimization import query_gpt
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

def fetch_and_process_xml(url):
    response = requests.get(url)
    data = response.text
    etree = ET.ElementTree(ET.fromstring(data))
    return etree.findall("./channel/item")

def filter_new_topics(topics, existing_topics):
    return [topic for topic in topics if not any(existing_topic['name'] == topic['name'] for existing_topic in existing_topics)]

def get_ordered_topics(topics, amount_of_topics):
    topics_list = [topic['name'] for topic in topics]
    user_prompt = f"""Order the following topics by relevance to cybersecurity and expected popularity...{topics_list}"""
    system_prompt = 'You are a data computer that formats data into JSON.'
    ordered_topics_json = query_gpt(user_prompt, system_prompt)

    if ordered_topics_json and ordered_topics_json.startswith('[') and ordered_topics_json.endswith(']'):
        return json.loads(ordered_topics_json)[:amount_of_topics]
    else:
        raise ValueError("The GPT-3 response is not in the expected JSON array format.")

def generate_topics(supabase, amount_of_topics, gpt_ordering=False):
    url = "https://feeds.feedburner.com/TheHackersNews"
    items = fetch_and_process_xml(url)
    current_time = datetime.now().isoformat()

    topics = [{
        "name": item.find("title").text,
        "url": item.find("link").text,
        "description": item.find("description").text,
        "date_published": item.find("pubDate").text,
        "provider": "The Hacker News",
        "date_accessed": current_time,
    } for item in items]

    logging.info(f'Extracted {len(topics)} topics')

    try:
        existing_topics = supabase.table('topics').select('name').execute().data
    except Exception as e:
        logging.error(f'Failed to query existing topics: {e}')
        return []

    new_topics = filter_new_topics(topics, existing_topics)

    # Restricting the number of new topics to the amount requested.
    new_topics = new_topics[:amount_of_topics]

    if len(new_topics) < amount_of_topics:
        logging.warning(f'Found only {len(new_topics)} new topics.')
        
    if gpt_ordering:
        try:
            ordered_topics = get_ordered_topics(new_topics, min(len(new_topics), amount_of_topics))
            new_topics = [topic for topic in new_topics if topic['name'] in ordered_topics]
        except Exception as e:
            logging.error(f'Failed to order topics: {e}')
            
    supabase.table('topics').insert(new_topics).execute()

    try:
        inserted_topics = supabase.table('topics').select('*').eq('date_accessed', current_time).execute().data
    except Exception as e:
        logging.error(f'Failed to query inserted topics: {e}')
        return []

    logging.info(f'Inserted {len(inserted_topics)} new topics.')
    return inserted_topics

