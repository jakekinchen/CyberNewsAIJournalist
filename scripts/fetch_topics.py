import requests
import pip._vendor.requests as requests
from xml.etree import ElementTree as ET
import json
import os
from content_optimization import prioritize_topics

def fetch_topics():
    def fetch_and_parse_xml(url):
        # Fetch XML data
        response = requests.get(url)
        # Parse XML data into an ElementTree object
        tree = ET.fromstring(response.content)
        return tree

    def process_items(tree):
        # Extract items and process each one
        items = tree.findall("./channel/item")
        processed_items = []
        for item in items:
            # Create a dictionary for each item
            item_dict = {
                "title": item.find("title").text,
                "description": ET.tostring(item.find("description"), encoding='unicode', method='xml'),
                "link": item.find("link").text,
                "guid": item.find("guid").text,
                "pubDate": item.find("pubDate").text,
                "author": item.find("author").text
            }
            processed_items.append(item_dict)
        return processed_items

    def create_json_file(data, filename):
        with open(filename, 'w') as f:
            json.dump(data, f, ensure_ascii=False, indent=4)

    # Fetch and parse XML data
    url = "https://feeds.feedburner.com/TheHackersNews"
    tree = fetch_and_parse_xml(url)

     # Process items and create JSON file
    processed_items = process_items(tree)

    # Extract the titles from the processed items
    titles = [item['title'] for item in processed_items]

    # Prioritize the titles
    prioritized_titles = prioritize_topics(titles)

    # Create a new list of processed items in the order of prioritized titles
    prioritized_items = sorted(processed_items, key=lambda item: prioritized_titles.index(item['title']) if item['title'] in prioritized_titles else len(processed_items))

    # Create temp directory inside data folder if it doesn't exist
    temp_dir = os.path.join('data', 'temp')
    os.makedirs(temp_dir, exist_ok=True)

    # Create full path to the file
    news_topics_file = os.path.join(temp_dir, "news_topics.json")

    create_json_file(prioritized_items, news_topics_file)

    # Confirm the file is successfully created
    if os.path.isfile(news_topics_file):
        print("JSON file created successfully in {}".format(news_topics_file))
    else:
        print("Failed to create JSON file")
