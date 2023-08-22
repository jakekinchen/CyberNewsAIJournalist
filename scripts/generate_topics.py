import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import sys
from dotenv import load_dotenv
from content_optimization import query_gpt3

# Load environment variables
load_dotenv()

def generate_topics(supabase):
    # Generate XML data
    url = "https://feeds.feedburner.com/TheHackersNews"
    response = requests.get(url)
    data = response.text
    etree = ET.ElementTree(ET.fromstring(data))

    # Extract and process topics
    items = etree.findall("./channel/item")
    topics = [{
        "name": item.find("title").text,
        "url": item.find("link").text,
        "description": item.find("description").text,
        "date_published": item.find("pubDate").text,
        "provider": "The Hacker News",
        "date_accessed": datetime.now().isoformat(),
    } for item in items]
    print(f'Extracted {len(topics)} topics')
    # Remove duplicates topics already in supabase
    try:
        response = supabase.table('topics').select('name').execute()
    except Exception as e:
        print(f'Failed to query existing topics: {e}')
        sys.exit(1)
    existing_topics = response.data
    topics = [topic for topic in topics if not any(existing_topic['name'] == topic['name'] for existing_topic in existing_topics)]

    # If there are less than 10 new topics, throw an error
    if len(topics) < 10:
        raise Exception('Not enough new topics')

    top_ten_topics = topics[:10]  # Default to the first 10 topics if ordering fails

    try:
        topics_list = [topic['name'] for topic in topics]
        user_prompt = 'Order the following topics by relevance to cybersecurity and expected popularity into a JSON:\n' + '\n'.join(topics_list)
        system_prompt = 'You are a data computer that formats data into JSON.'
        ordered_topics_json = query_gpt3(user_prompt, system_prompt)
        ordered_topics = json.loads(ordered_topics_json)

        # Map the ordered topics to their original information, if possible, and add the order number
        top_ten_topics = [{
            **next((topic for topic in topics if topic['name'] == ordered_topic['name']), {'name': ordered_topic['name']}), 
            'order_number': index + 1
        } for index, ordered_topic in enumerate(ordered_topics[:10])]
    except Exception as e:
        print(f'Failed to order topics, inserting without order: {e}')

    # Insert top ten topics into Supabase
    supabase.table('topics').insert(top_ten_topics).execute()
    
