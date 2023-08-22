import os
import datetime
from datetime import datetime
from generate_topics import generate_topics
from supabase import create_client, Client
from search_related_articles import search_related_sources
from content_optimization import create_factsheet, query_gpt3
import asyncio
import httpx
from extract_text import scrape_news

# Load environment variables
from dotenv import load_dotenv
load_dotenv()

# Supabase configuration
supabase_url: str = os.getenv('SUPABASE_ENDPOINT')
supabase_key: str = os.getenv('SUPABASE_KEY')
# Initialize Supabase
supabase: Client = create_client(supabase_url = supabase_url, supabase_key = supabase_key)

allow_topic_regeneration = False
pause_topic_generation = False
pause_source_scraping = False

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
        content = scrape_news(source["url"])

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

def gather_sources(topic, overload=False):
    MIN_SOURCES = 3
    response = supabase.table("sources").select("*").eq("topic_id", topic["id"]).execute()
    existing_sources = response.data or []

    required_sources = MIN_SOURCES - len(existing_sources)
    if overload:
        required_sources += 3  # Increase the number if overloaded

    if required_sources > 0:
        related_sources = search_related_sources(topic["name"], len(existing_sources))
        for source in related_sources[:required_sources]:
            print(f"Scraping source from {source['url']}...")
            content = scrape_news(source["url"])  # Assuming scrape_news is defined elsewhere

            if content:
                print(f"Successfully scraped source from {source['url']}")
                supabase.table("sources").insert([{
                    "url": source["url"],
                    "content": content,
                    "topic_id": topic["id"],
                }]).execute()
                print(f"Source from {source['url']} saved to Supabase.")
            else:
                print(f"Failed to scrape source from {source['url']}")

def generate_factsheets():
    #Loop through all topics and use create_factsheet to generate factsheets for each of them
    response = supabase.table("topics").select("*").execute()
    topics = response.data
    for topic in topics:
        create_factsheet(topic)
        print(f"Successfully generated factsheet for topic {topic['name']}")

def test_query_gpt3():
    user_prompt = "When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to the topic. Now give the factsheet for the following information: This is a test."
    system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail. You utilize a lossless compression algorithm to keep the factual details together"
    print(query_gpt3(user_prompt, system_prompt))

async def main():
    # Check if topics need to be generated
    #rescrape_thehackernews_sources()
    generate_factsheets()
    test_query_gpt3()
   
    current_date = datetime.now().isoformat()[:10]
    response = supabase.table("topics").select("*").eq("date_accessed", current_date).execute()
    print(f"Response: {response}")

    topics_today = response.data
    if allow_topic_regeneration or not topics_today or len(topics_today) == 0:
        if topics_today and len(topics_today) > 0:
            # Clear existing topics for the day
            supabase.table("topics").delete().eq("date_accessed", current_date).execute()
        
        # Generate topics
        if not pause_topic_generation:
            #Trying to generate topics
            try:
                generate_topics(supabase)
            except Exception as e:
                print(f"Failed to generate new topics: {e}")

    # Iterate through each topic and gather sources and factsheets
    response = supabase.table("topics").select("*").execute()
    ordered_topics = response.data

    for topic in ordered_topics:
        print(f"Processing topic: {topic['name']}")

        # Gather Sources if needed
        if not pause_source_scraping:
            gather_sources(topic, False)

        # Generate Fact Sheets
        create_factsheet(topic)

    print("Scraping complete.")

if __name__ == "__main__":
    asyncio.run(main())
