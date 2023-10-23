from dotenv import load_dotenv
import os
from supabase_utils import supabase, update_supabase_post
from wp_utils import update_wp_post
import logging
import re
from test import ReadabilityMetrics, SeoMetrics
import logging
from source_fetcher import fetch_sources_from_query
from gpt_utils import query_gpt, function_call_gpt, image_query_function
from bs4 import BeautifulSoup

# Load .env file
load_dotenv()
bing_api_key = os.getenv('BING_SEARCH_KEY')
response_machine_prompt = os.getenv('RESPONSE_MACHINE_PROMPT')
tech_term_prompt = os.getenv('TECH_TERM_PROMPT')

def update_post(post_info):
    update_supabase_post(post_info)
    update_wp_post(post_info)

def test_seo_and_readability_optimization():
    # Pull a post from Supabase and run it through the SEO and Readability optimization functions
    # Assert that the result is what you expect
    post_info = supabase.table('posts').select('*').eq('id', 140).execute().data
    # Pull the image row associated with the post by locating the topic_id from the post
    images = supabase.table('images').select('*').eq('topic_id', post_info[0]['topic_id']).execute().data
    #print(f"Post info: {post_info}")
    if not post_info:
        print("Failed to get post info")
        return
    post_info = post_info[0]
    print(f"Before readability optimization: {post_info['content']}")
    post_info['content'] = readability_optimization(post_info['content'])
    print(f"After readability optimization: {post_info['content']}")
    post_info = seo_optimization(post_info, images)
    print(f"After SEO optimization: {post_info['content']}")
    #print(f"SEO optimized content: {content}")
    print("Successfully optimized post.")
    update_post(post_info)
    #print("Successfully updated post.")

def readability_optimization(content):
    metrics = ReadabilityMetrics(content)
    return metrics.optimize_readability()

def seo_optimization(post_info, images):
    seo_optimizer = SeoMetrics(post_info, images)
    return seo_optimizer.optimize()

def insert_tech_term_link(content: str, tech_term: str) -> str:
    link = generate_link_from_term(tech_term)

    if not link:
        print(f"Failed to generate hyperlink for tech term {tech_term}. Returning the original content.")
        return content
    
    replaced = False

    def repl(match):
        nonlocal replaced
        word = match.group(0)  # Extract the matched word

        hyperlink = f'<a href="{link}">{word}</a>'
        if not replaced:
            replaced = True
            return hyperlink
        return word

    # Use re.sub to find all case-insensitive occurrences of the tech term and apply the repl function
    modified_content, _ = re.subn(r'\b' + re.escape(tech_term) + r'\b', repl, content, flags=re.IGNORECASE)

    if not replaced:
        print(f"Tech term {tech_term} not found in the content. Returning the original content.")
    return modified_content


def generate_link_from_term(term):
    sources = fetch_sources_from_query(term)
    if not sources:
        print(f"Failed to find sources for term {term}")
        return None
    
    # Selects best source by integer id
    source_id = select_tech_term_source(sources)
    if not source_id:
        print(f"Failed to select source from sources - returning the first source's url")
        # Return the first source's url if there is at least one source, else return None
        return sources[0]['url'] if sources else None
    print(f"Selected source ID: {source_id}")

    # Select the source whose integer is equal to the id of the source that best defines the tech term
    source = next((source for source in sources if source['id'] == source_id), None)
    print(f"Selected source: {source}")

    # Return the url of the source if source is not None, else return None
    return source['url'] if source else None

def select_tech_term_source(sources):
    functions = [
            {
                "name": "TechTermSourceSelector",
                "description": "Select the source that best defines the tech term.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    'source': {
                        'type': 'integer',
                        'description': 'The id of the source that best defines the tech term.',
                        }
                    },
                    
                }
            }
        ]
    system_prompt = tech_term_prompt
    user_prompt = f"Select the source that best defines the tech term: {sources}"
    try:
        response = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo", functions)
        source_id = response.get('source', None)
        logging.debug(f"Source ID from GPT response: {source_id}")
        if source_id is None:
            print(f"Expected key 'source' not found in data from GPT.")
            print(f"Here is the GPT response: {response}")
        return source_id
    except KeyError:
        logging.error("Expected key 'source' not found in data from GPT.")
        return None

def regenerate_image_queries(post_info):
    system_prompt = ("You are a stock photo database query generator that generates queries for stock photos that are relevant to the topic yet not too similar to each other. They should be simple and convey the meaning of the topic without going for obvious keywords like 'cybersecurity' or 'hacking'.")
    user_prompt = f"Generate an array of image queries for the following information: {post_info['content']}"
    functions = image_query_function
    
    # Attempt to generate image queries using GPT
    try:
        logging.info("Initiating image query regeneration...")
        response = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo", functions)
        
        image_queries = response.get('image_queries')
        
        if not image_queries:
            logging.warning("GPT did not provide image queries. Using focus keyword as a fallback.")
            focus_keyword = post_info.get('yoast_wpseo_focuskw')
            if not focus_keyword:
                raise ValueError("Both GPT image queries and focus keyword are absent.")
            image_queries = [focus_keyword]
        
        logging.info(f"Generated image queries: {image_queries}")
        return image_queries
        
    except Exception as e:
        logging.error(f"Error while regenerating image queries: {e}")
        raise Exception(f"Failed to regenerate image queries due to: {e}")





