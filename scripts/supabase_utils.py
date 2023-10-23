from supabase import create_client, Client
import os
from dotenv import load_dotenv

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def update_supabase_post(post_info):
    # Update the post
    try:
        response = supabase.table("posts").update(post_info).eq('id', post_info['id']).execute()
    except Exception as e:
        print(f"Failed to update post: {e}")
        return
    print(f"Successfully updated post with id {post_info['id']}.")

def insert_post_info_into_supabase(post_info):
 try:
        response = supabase.table("posts").insert([post_info]).execute()
 except Exception as e:
        print(f"An error occurred: {e}")
        if e.code == '23505':
            print(f"Post with the slug {post_info['slug']} already exists. Continuing...")
            print("Deleting the post in Supabase...")
            try:
                response = supabase.table("posts").delete().eq('slug', post_info['slug']).execute()
                print("Post deleted.")
                # Try to insert the post again
                try:
                    response = supabase.table("posts").insert([post_info]).execute()
                    print("Post inserted.")
                except Exception as e:
                    print(f"Failed to insert the post: {e}")
                    print("Continuing...")
                    return
            except Exception as e:
                print(f"Failed to delete the post: {e}")
                print("Continuing...")
                return
        if e.code == 'PGRST102':
            print("An invalid request body was sent(e.g. an empty body or malformed JSON).")
            print("Tried to insert the following post info:")
        if e.code == '22P02':
            print("An invalid request body was sent(e.g. an empty body or malformed JSON).")
            print(f"Tried to insert the following post info:{post_info}")
        else:
            print(f"Failed to save post information to Supabase. Continuing...")
            return

async def delete_topic(topic_id):
    # Delete the topic
    try:
        response = supabase.table("topics").delete().eq("id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete topic: {e}")
        return
    print(f"Successfully deleted topic with ID {topic_id} and all related sources.")

async def delete_supabase_post(topic_id):
    # topic_id is a foreign key in the supabase table posts
    # Delete the post
    try:
        response = supabase.table("posts").delete().eq("topic_id", topic_id).execute()
    except Exception as e:
        print(f"Failed to delete post: {e}")
        return
    print(f"Successfully deleted post with topic ID {topic_id}.")