import requests
import xml.etree.ElementTree as ET
from datetime import datetime
import json
import sys
from dotenv import load_dotenv
from content_optimization import query_gpt3

# Load environment variables
load_dotenv()

def generate_topics(supabase, amount_of_topics):
    # Generate XML data
    url = "https://feeds.feedburner.com/TheHackersNews"
    response = requests.get(url)
    data = response.text
    etree = ET.ElementTree(ET.fromstring(data))
    # Extract and process topics
    items = etree.findall("./channel/item")
    current_time = datetime.now().isoformat()
    topics = [{
        "name": item.find("title").text,
        "url": item.find("link").text,
        "description": item.find("description").text,
        "date_published": item.find("pubDate").text,
        "provider": "The Hacker News",
        "date_accessed": current_time,
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
    # If there are less than n new topics, throw an error
    if len(topics) < amount_of_topics:
        raise Exception('Not enough new topics')
    top_topics = topics[:amount_of_topics]  # Default to the first n topics if ordering fails
    try:
        topics_list = [topic['name'] for topic in topics]
        user_prompt = """Order the following topics by relevance to cybersecurity and expected popularity. 
                        Criteria for relevance include how closely the topic is related to security vulnerabilities, data breaches, or cyber threats. 
                        Criteria for popularity include how impactful the topic is expected to be in the cybersecurity community.
                        Format the sorted list as a JSON array:
                        """ + '\n'.join(topics_list)
        system_prompt = 'You are a data computer that formats data into JSON.'
        ordered_topics_json = query_gpt3(user_prompt, system_prompt)
        
        # Debugging: Print the raw JSON response
        print(f"Raw JSON response from GPT-3: {ordered_topics_json}")
        
        # Modified: Added a check for JSON array format in string
        if ordered_topics_json and isinstance(ordered_topics_json, str) and ordered_topics_json.startswith('[') and ordered_topics_json.endswith(']'):
            ordered_topics = json.loads(ordered_topics_json)
        else:
            raise ValueError("The GPT-3 response is not in the expected JSON array format.")
            
        # Debugging: Print the original topics and ordered topics
        print(f"Original topics: {[topic['name'] for topic in topics]}")
        print(f"Ordered topics from GPT-3: {ordered_topics}")

        top_topics = []
        for index, ordered_topic in enumerate(ordered_topics[:amount_of_topics]):
            # Debugging: Print the next() function result
            matching_topic = next((topic for topic in topics if topic['name'].strip().lower() == ordered_topic.strip().lower()), None)
            #print(f"Type of topic['name']: {type(topic['name'] for topic in topics)}, Type of ordered_topic: {type(ordered_topic)}")
            
            if matching_topic:
                top_topic = {**matching_topic, 'order_number': index + 1}
            else:
                top_topic = {'name': ordered_topic, 'order_number': index + 1}
            
            top_topics.append(top_topic)

        # Debugging: Print the ordered topics by name and order number
       # print(f"Ordered topics: {top_topics}")
    except Exception as e:
        print(f'Failed to order topics, inserting without order: {e}')
    # Insert top ten topics into Supabase
    supabase.table('topics').insert(top_topics).execute()
    # Query the topics back from Supabase to get the primary keys
    try:
        # Use the specific timestamp to filter the query
        response = supabase.table('topics').select('*').eq('date_accessed', current_time).execute()
        inserted_topics_with_keys = response.data
    except Exception as e:
        print(f'Failed to query inserted topics: {e}')
        sys.exit(1)
    # Return the top ten topics
    #print(f'Inserted {len(inserted_topics_with_keys)} topics: {inserted_topics_with_keys}')
    return inserted_topics_with_keys
    
