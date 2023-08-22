import openai
from dotenv import load_dotenv
import os
from supabase import create_client, Client

# Load .env file
load_dotenv()

# Supabase configuration
supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

def token_optimizer(text):
    message = f"{text}\n\nSummarize this but don't leave out any relevant facts"
    model = "gpt-3.5-turbo-16k"
    system = "You are an information compression algorithm that outputs the most relevant information in the least amount of words without losing any relevant information"
    response = query_gpt3(message, system, model)
    print(response)
    return response.choices[0].message.content

def prioritize_topics(topics):
    response = None
    message = f"Prioritize the following topics in order of relevance to Cybersecurity:\n\n{topics}"
    try:
        response = query_gpt3(message, "You are a data computer that outputs the pure information as a list and nothing else")
    except openai.error.InvalidRequestError as e:
        if 'exceeded maximum number of tokens' in str(e):
            response = query_gpt3(message, "You are a data computer that outputs the pure information as a list and nothing else", model="gpt-3.5-turbo-16k")
        else:
            raise e
    # Process the response to get a list of titles in order of relevance
    prioritized_titles = response.choices[0].message.content.split("\n")
    return prioritized_titles

def query_gpt3(user_prompt, system_prompt, model='gpt-3.5-turbo'):
    try:
        response = openai.ChatCompletion.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content
    except Exception as err:
        print(err)
        response = openai.ChatCompletion.create(
            model='gpt-3.5-turbo-16k',
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ]
        )
        return response.choices[0].message.content

def create_factsheet(topic):
    try :
        response = supabase.table('sources').select('*').eq('topic_id', topic['id']).execute()
        related_sources = response.data or []
    except Exception as e:
        print(f'Failed to get related sources for topic {topic["id"]}', e)
        return

    combined_factsheet = {}

    for source in related_sources:
        # if source's factsheet is empty or null
        if not source['factsheet']:
            system_prompt = "You are an expert at summarizing topics while being able to maintain every single detail. You utilize a lossless compression algorithm to keep the factual details together"
            user_prompt = f'When you make a factsheet, keep each fact together in a sentence so each fact is separated by a period. Try to chunk together information that is related to {topic["name"]}. Now give the factsheet for the following information: {source["content"]}'
            try:
                facts = query_gpt3(user_prompt, system_prompt)
                supabase.table('sources').update({"factsheet": facts}).eq('id', source['id']).execute()
                combined_factsheet[source['id']] = facts
            except Exception as gpt3_error:
                print(f'Failed to synthesize facts for source {source["id"]}', gpt3_error)
                try:
                    facts = query_gpt3(user_prompt, system_prompt, model='gpt-3.5-turbo-16k')
                    supabase.table('sources').update({"factsheet": facts}).eq('id', source['id']).execute()
                    combined_factsheet[source['id']] = facts
                except Exception as gpt3_error:
                    print(f'Failed to synthesize facts for source {source["id"]}', gpt3_error)
                    continue

    try:
        supabase.table('topics').update({"factsheet": combined_factsheet}).eq('id', topic['id']).execute()
    except Exception as e:
        print(f'Failed to update topic {topic["id"]}', e)
