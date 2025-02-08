"""
text-search-babbage-doc-001
gpt-3.5-turbo-16k-0613
curie-search-query
gpt-3.5-turbo-16k
text-search-babbage-query-001
babbage
babbage-search-query
text-babbage-001
whisper-1
text-similarity-davinci-001
davinci-similarity
code-davinci-edit-001
curie-similarity
babbage-search-document
curie-instruct-beta
text-search-ada-doc-001
davinci-instruct-beta
gpt-4
text-similarity-babbage-001
text-search-davinci-doc-001
babbage-similarity
text-embedding-ada-002
davinci-search-query
text-similarity-curie-001
text-davinci-001
text-search-davinci-query-001
ada-search-document
ada-code-search-code
babbage-002
davinci-002
davinci-search-document
curie-search-document
babbage-code-search-code
text-search-ada-query-001
code-search-ada-text-001
babbage-code-search-text
code-search-babbage-code-001
ada-search-query
ada-code-search-text
text-search-curie-query-001
text-davinci-002
text-davinci-edit-001
code-search-babbage-text-001
gpt-3.5-turbo
gpt-3.5-turbo-instruct-0914
ada
text-ada-001
ada-similarity
code-search-ada-code-001
text-similarity-ada-001
gpt-3.5-turbo-0301
gpt-3.5-turbo-instruct
text-search-curie-doc-001
text-davinci-003
gpt-4-0613
text-curie-001
curie
gpt-4-0314
davinci
dall-e-2
gpt-3.5-turbo-0613
gpt-4o
gpt-4o-2024-08-06
chatgpt-4o-latest
gpt-4o-mini
gpt-4o-mini-2024-07-18
o1
o1-2024-12-17
o1-mini
o1-mini-2024-09-12
o3-mini
o3-mini-2025-01-31
o1-preview
o1-preview-2024-09-12
gpt-4o-realtime-preview
gpt-4o-realtime-preview-2024-12-17
gpt-4o-mini-realtime-preview
gpt-4o-mini-realtime-preview-2024-12-17
gpt-4o-audio-preview
gpt-4o-audio-preview-2024-12-17
"""

import asyncio
import sys
from supabase_utils import supabase

async def delete_topic_and_related(topic_id):
    """Delete a topic and all its related data."""
    print(f"Deleting topic {topic_id} and related data...")
    
    # First delete related sources
    try:
        sources = supabase.table("sources").select("*").eq("topic_id", topic_id).execute()
        if sources.data:
            print(f"Found {len(sources.data)} related sources")
            supabase.table("sources").delete().eq("topic_id", topic_id).execute()
            print(f"Deleted {len(sources.data)} sources")
    except Exception as e:
        print(f"Error deleting sources: {e}")
    
    # Then delete the topic itself
    try:
        topic = supabase.table("topics").select("*").eq("id", topic_id).execute()
        if topic.data:
            supabase.table("topics").delete().eq("id", topic_id).execute()
            print(f"Deleted topic {topic_id}")
        else:
            print(f"Topic {topic_id} not found")
    except Exception as e:
        print(f"Error deleting topic: {e}")

if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python remove.py <topic_id>")
        sys.exit(1)
        
    try:
        topic_id = int(sys.argv[1])
    except ValueError:
        print("Error: topic_id must be a number")
        sys.exit(1)
        
    asyncio.run(delete_topic_and_related(topic_id))