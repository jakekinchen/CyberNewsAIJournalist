import openai
from dotenv import load_dotenv
import os
from supabase_utils import supabase
import logging
import re
from test import HTMLMetrics
import logging
from source_fetcher import fetch_sources_from_query
from gpt_utils import query_gpt, function_call_gpt

# Load .env file
load_dotenv()
bing_api_key = os.getenv('BING_SEARCH_KEY')
response_machine_prompt = os.getenv('RESPONSE_MACHINE_PROMPT')
tech_term_prompt = os.getenv('TECH_TERM_PROMPT')
        
def seo_optimization(content):
    print("Entering seo optimization")
    max_attempts = 3
    attempt = 0

    while attempt < max_attempts:
        needs_optimization, seo_prompt = assess_seo_needs(content)
        
        if not needs_optimization:
            if attempt == 0:
                print("Content does not need optimization")
            else:
                print("Optimization successful on attempt", attempt)
            return content
        
        print(f"Optimizing content, attempt {attempt + 1}")
        content = optimize_content(seo_prompt, content)
        attempt += 1
    print("Optimization not successful after maximum attempts.")
    return content

def assess_seo_needs(content):
    metrics = HTMLMetrics(content)
    
    seo_prompt, score = generate_seo_prompt(metrics)
    needs_optimization = score > 1

    return needs_optimization, seo_prompt

def generate_seo_prompt(metrics):
    seo_prompt = ""
    score = 0
    if metrics.subheading_distribution() > 0:
        seo_prompt += "There's a paragraph in this article that's too long. Break it up. "
        score += 1
    
    if metrics.sentence_length() > 25:
        seo_prompt += "More than a quarter of the sentences are too long. Shorten them. "
        score += 1
    
    if metrics.transition_words() < 30:
        seo_prompt += "The article lacks transition words. Add some to improve flow. "
        score += 1
    return seo_prompt, score

def optimize_content(seo_prompt, content):
    seo_prompt += "Optimize the article for SEO. Maintain the HTML structure and syntax. "
    return query_gpt(content, seo_prompt, model='gpt-4')

def prioritize_topics(topics):
    response = None
    message = f"Prioritize the following topics in order of relevance to Cybersecurity:\n\n{topics}"
    try:
        response = query_gpt(message, "You are a data computer that outputs the pure information as a list and nothing else")
    except openai.error.InvalidRequestError as e:
        if 'exceeded maximum number of tokens' in str(e):
            response = query_gpt(message, "You are a data computer that outputs the pure information as a list and nothing else", model="gpt-3.5-turbo-16k")
        else:
            raise e
    # Process the response to get a list of titles in order of relevance
    prioritized_titles = response.choices[0].message.content.split("\n")
    return prioritized_titles


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
    system_prompt = "You are a stock photo database query generator that generates queries for stock photos that are relevant to the topic yet not too similar to each other. They should be simple and convey the meaning of the topic without going for obvious keywords like 'cybersecurity' or 'hacking'."
    user_prompt = f"Generate an array image queries for the following information: {post_info['content']}"
    functions = [
            {
                "name": "ImageQueryGenerator",
                "description": "Observe the content of the post and suggest stock photo database queries.",
                "parameters": {
                    "type": "object",
                    "properties": {
                    'image_queries': {
                        'type': 'array',
                        'description': 'A list of queries to generate images for the post.',
                        'items': { 
                            "type": "string", 
                            "description": "A query to generate an image for the post. This should be a phrase that describes the contents of the image, with different words separated by space like normal. It should not be a concatenation of multiple words and should not contain a file extension." 
                            },
                        }
                    },
                    
                }
            }
        ]
    try:
        logging.info("Regenerating image queries")
        image_queries = function_call_gpt(user_prompt, system_prompt, "gpt-3.5-turbo", functions)
        image_queries = image_queries['image_queries']
        print(f"Image queries generated: {image_queries}")
        return image_queries
    except Exception as e:
        raise Exception(f"Failed to regenerate image queries: {e}")




