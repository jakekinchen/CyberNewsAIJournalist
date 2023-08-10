import os
import sys
import datetime
import json
from datetime import timedelta
from datetime import datetime
from fetch_topics import fetch_topics
from search_related_articles import search_related_articles
from extract_text import extract_text
from news_synthesis import news_synthesis
from wp_post import create_post_and_write_to_csv


DATA_PATH = 'app/data'
TOPICS_PATH = os.path.join(DATA_PATH, 'topics')
NEWS_TOPICS_FILE = os.path.join(DATA_PATH, 'news_topics.json')
SEARCHED_TOPICS_FILE = os.path.join(DATA_PATH, 'searched_topics.json')

def has_fetch_topics_run_today():
    if os.path.exists(NEWS_TOPICS_FILE):
        file_time = datetime.datetime.fromtimestamp(os.path.getmtime(NEWS_TOPICS_FILE))
        if file_time.date() == datetime.date.today():
            return True
    return False

def get_searched_topics():
    if os.path.exists(SEARCHED_TOPICS_FILE):
        with open(SEARCHED_TOPICS_FILE, 'r') as f:
            return json.load(f)
    else:
        return []

def update_searched_topics(topics):
    with open(SEARCHED_TOPICS_FILE, 'w') as f:
        json.dump(topics, f)

def main():
    # Try to post failed articles
    for root, dirs, files in os.walk(DATA_PATH):
        for file in files:
            if file.endswith(".json"):
                json_file_path = os.path.join(root, file)
                with open(json_file_path) as f:
                    post_info = json.load(f)
                if post_info.get('status') == 'failed':
                    create_post_and_write_to_csv(json_file_path, post_info['post_time'])

    if not has_fetch_topics_run_today():
        fetch_topics()
        print ("Fetched topics")

    topic_dir = search_related_articles()
    print ("Searched related articles")
    
    if topic_dir:
        extract_text(topic_dir)
        print ("Extracted text")
        post_info = news_synthesis(topic_dir)  # Get the post information
        print ("Synthesized news")
        start_time = datetime.now().replace(hour=8, minute=0, second=0, microsecond=0)  # Set start time to 8 AM
        for i in range(10):
            post_time = start_time + timedelta(hours=i)  # Set post time
            json_file_path = os.path.join(topic_dir, f"post_{i}.json")  # Get the path to the post's JSON file
            create_post_and_write_to_csv(json_file_path)
    else:
        print("No new topics found.")

if __name__ == "__main__":
    main()

