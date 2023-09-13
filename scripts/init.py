import os
import requests
import datetime
from datetime import datetime
from generate_topics import generate_topics
from supabase import create_client, Client
from search_related_articles import search_related_sources
from content_optimization import create_factsheet
from post_synthesis import post_synthesis
from wp_post import create_wordpress_post, fetch_categories, fetch_tags
import asyncio
import httpx
from extract_text import scrape_content
from cisa import get_cisa_exploits
# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Supabase configuration
supabase_url: str = os.getenv('SUPABASE_ENDPOINT')
supabase_key: str = os.getenv('SUPABASE_KEY')
# Initialize Supabase
supabase: Client = create_client(supabase_url = supabase_url, supabase_key = supabase_key)

wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')

amount_of_topics = 1
MIN_SOURCES = 3
exploit_fetcher_activated = False
debug = False
synthesize_factsheets = True

# Access your API keys and token
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')
wp_token = os.getenv('WP_TOKEN')  # Get the token from environment variables

# Get the JWT token for WordPress
def get_jwt_token(username, password):

    if wp_token:
        print("Using existing token")
        return wp_token
    
    token_endpoint = "http://cybernow.info/wp-json/jwt-auth/v1/token"
    payload = {
        'username': username,
        'password': password
    }
    response = requests.post(token_endpoint, data=payload)
    if response.status_code == 200:
        token = response.json().get('token')  # Get token directly from JSON response
        print(f"Received token: {token}")
        return token
    else:
        print(f"Failed to get JWT token: {response.text}")
        return None


def delete_targeted_sources(target_url):
    #find all source url's that begin with https://thehackernews.com/search? and delete them
    #remove the quotes from the beginning and end of the target_url variable
    target_url = target_url[1:-1]
    response = supabase.table("sources").select("*").like("url", f"%{target_url}%").execute()
    sources = response.data
    for source in sources:
        supabase.table("sources").delete().eq("id", source["id"]).execute()
        print(f"Deleted source from {source['url']} because it is a search query.")

def rescrape_yahoo_sources():
    #find all source url's that contain yahoo.com and rescrape them
    response = supabase.table("sources").select("*").like("url", "%yahoo.com%").execute()
    sources = response.data
    for source in sources:
        print(f"Scraping source from {source['url']}...")
        content = scrape_content(source["url"])

        if content:
            print(f"Successfully scraped source from {source['url']}")
            supabase.table("sources").update({"content": content}).eq("id", source["id"]).execute()
            print(f"Source from {source['url']} saved to Supabase.")
        else:
            supabase.table("sources").delete().eq("id", source["id"]).execute()

def rescrape_thehackernews_sources():
    #find all source url's that begin with https://thehackernews.com and rescrape them
    response = supabase.table("sources").select("*").like("url", "https://thehackernews.com%").execute()
    sources = response.data
    for source in sources:
        print(f"Scraping source from {source['url']}...")
        #if url begins with https://thehackernews.com/search?, then delete it and move onto the next source
        if source['url'].startswith("https://thehackernews.com/search?"):
            supabase.table("sources").delete().eq("id", source["id"]).execute()
            print(f"Deleted source from {source['url']} because it is a search query.")
            continue
        content = scrape_content(source["url"])
        if content:
            print(f"Successfully scraped source from {source['url']}")
            supabase.table("sources").update({"content": content}).eq("id", source["id"]).execute()
            print(f"Source from {source['url']} saved to Supabase.")
        else:
            supabase.table("sources").delete().eq("id", source["id"]).execute()

async def delete_topic(topic_id):
    # Delete all related sources
    response = supabase.table("sources").delete().eq("topic_id", topic_id).execute()
    if response.error:
        print(f"Failed to delete related sources: {response.error}")
        return
    # Delete the topic
    response = supabase.table("topics").delete().eq("id", topic_id).execute()
    if response.error:
        print(f"Failed to delete topic: {response.error}")
        return
    print(f"Successfully deleted topic with ID {topic_id} and all related sources.")

def delete_duplicate_source_urls():
    #find all source's with duplicate urls and delete them
    response = supabase.table("sources").select("*").execute()
    sources = response.data
    for source in sources:
        response = supabase.table("sources").select("*").eq("url", source["url"]).execute()
        duplicate_sources = response.data
        if len(duplicate_sources) > 1:
            for duplicate_source in duplicate_sources:
                if duplicate_source["id"] != source["id"]:
                    supabase.table("sources").delete().eq("id", duplicate_source["id"]).execute()
                    print(f"Deleted duplicate source from {duplicate_source['url']}")

def gather_sources(topic, overload=False):
    date_accessed = datetime.now().isoformat()
    
    response = supabase.table("sources").select("*").eq("topic_id", topic["id"]).execute()
    existing_sources = response.data or []
    required_sources = MIN_SOURCES - len(existing_sources)
    
    if overload:
        required_sources += 3  # Increase the number if overloaded

    if required_sources > 0:
        related_sources = search_related_sources(topic["name"], len(existing_sources))
        
        for source in related_sources[:required_sources]:
            if source['url'] == "https://thehackernews.com/search?":  # Skip the URL to be deleted
                continue
            
            print(f"Scraping source from {source['url']}...")
            content = scrape_content(source["url"])
            
            if content:
                print(f"Successfully scraped source from {source['url']}")
                supabase.table("sources").insert([{
                    "url": source["url"],
                    "content": content,
                    "topic_id": topic["id"],
                    "date_accessed": date_accessed
                }]).execute()
                print(f"Source from {source['url']} saved to Supabase.")
            else:
                print(f"Failed to scrape source from {source['url']}")

def post_the_most_recent_topic(token):
    # Get the most recent topic
    response = supabase.table("topics").select("*").execute()
    topic = response.data[0]
    # Post the most recent topic
    post_info = post_synthesis(token, topic)
    # Upload post info to wordpress if post_info['complete_with_images'] is not None and post_info['complete_with_images'] == True:
    if post_info['complete_with_images'] == True:
        create_wordpress_post(post_info, datetime.now() + datetime.timedelta(days=1))
    else:
        print("Uploaded to Supabase but not to WordPress because the WP database would not allow images to be uploaded")

async def main():
    token = get_jwt_token(wp_username, wp_password)
    
    if debug:
        print("Debug mode enabled")
        return
    
    # Upload new cisa exploits
    result = await get_cisa_exploits()
    if result == False:
        print("Failed to get CISA exploits")
    else:
        print("Successfully got CISA exploits")
    
    # Generate topics
    try:
        recently_generated_topics = generate_topics(supabase, amount_of_topics)
    except Exception as e:
        print(f"Failed to generate new topics: {e}")
    
    # Iterate through each recently generated topic and gather sources and factsheets
    for topic in recently_generated_topics:
        print(f"Processing topic: {topic['name']}")
        
        # Gather Sources
        gather_sources(topic, False)
        
        # Generate Fact Sheets
        create_factsheet(topic)
        
        # Generate News
        post_info = post_synthesis(token, topic)
        
        if post_info['complete_with_images'] == True:
            create_wordpress_post(token, post_info, datetime.now() + datetime.timedelta(days=1))
        else:
            print("Uploaded to Supabase but not to WordPress because the WP database would not allow images to be uploaded")
    
    print("Scraping complete.")

if __name__ == "__main__":
    asyncio.run(main())
