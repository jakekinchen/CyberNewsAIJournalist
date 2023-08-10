import openai
from dotenv import load_dotenv
import os

# Load .env file
load_dotenv()

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

def token_optimizer(text):
    response = openai.ChatCompletion.create(
        model="gpt-3.5-turbo-16k",
        messages=[
            {"role": "user", "content": f"{text}\n\nSummarize but don't leave out any relevant facts:"}
        ],
    )
    print(response)
    return response['choices'][0]['message']['content']

def prioritize_topics(topics):
    response = None
    try:
        response = openai.ChatCompletion.create(
            model="gpt-3.5-turbo",
            messages=[
                {"role": "user", "content": f"Prioritize the following topics in order of relevance to Cybersecurity:\n\n{topics}"}
            ],
            max_tokens=1000,
        )
    except openai.error.InvalidRequestError as e:
        if 'exceeded maximum number of tokens' in str(e):
            response = openai.ChatCompletion.create(
                model="gpt-3.5-turbo-16k",
                messages=[
                    {"role": "user", "content": f"Prioritize the following topics in order of relevance to Cybersecurity:\n\n{topics}"}
                ],
            )
        else:
            raise e
    # Process the response to get a list of titles in order of relevance
    prioritized_titles = response['choices'][0]['message']['content'].split("\n")
    return prioritized_titles
