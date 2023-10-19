import json
import logging
import os
from tenacity import (
    retry,
    stop_after_attempt,
    wait_random_exponential,
    retry_if_exception_type
)
import openai
import tiktoken

# Set your OpenAI API key and organization
openai.api_key = os.getenv('OPENAI_KEY')
openai.organization = os.getenv('OPENAI_ORGANIZATION')

# Define the retry behavior
@retry(
    retry=retry_if_exception_type((openai.error.APIError, 
                                  openai.error.APIConnectionError, 
                                  openai.error.RateLimitError, 
                                  openai.error.ServiceUnavailableError, 
                                  openai.error.Timeout)),
    wait=wait_random_exponential(multiplier=1, max=60),
    stop=stop_after_attempt(10)
)
def _api_call_with_backoff(*args, **kwargs):
    return openai.ChatCompletion.create(*args, **kwargs)

def function_call_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo', functions=[], function_call_mode="auto"):
    function_call_mode = {"name": f"{functions[0]['name']}"}
    try:
        response = _api_call_with_backoff(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            functions=functions,
            function_call=function_call_mode
        )
        return json.loads(response.choices[0].message.function_call.arguments)
    except Exception as err:
        logging.error(err)
        print(f"Parameters: {functions}")
        print(f"Failed to call function: {err}")

def query_gpt(user_prompt, system_prompt, model='gpt-3.5-turbo'):
    context = f"{system_prompt} {user_prompt}"
    try:
        model = model_optimizer(context, model)  # assuming model_optimizer is defined elsewhere
    except Exception as e:
        logging.error(e)
        raise Exception(e)
    try:
        response = _api_call_with_backoff(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt}
            ],
            request_timeout=150,
        )
        return response.choices[0].message.content
    except openai.error.APIConnectionError as err:
        logging.error(err)

def tokenizer(string: str, encoding_name: str) -> int:
    encoding = tiktoken.encoding_for_model(encoding_name)
    num_tokens = len(encoding.encode(string))
    return num_tokens

def model_optimizer(text, model):
    token_quantity = tokenizer(text, model)
    if model.startswith('gpt-4'):
        if token_quantity < 8096:
            return 'gpt-4'
        elif token_quantity >= 8096 and token_quantity <= 32768:
            return 'gpt-3.5-turbo-16k'
        else:
            raise Exception('Text is too long for GPT-4')
    elif model.startswith('gpt-3.5'):
        if token_quantity < 4096:
            return 'gpt-3.5-turbo'
        elif token_quantity >= 4096 and token_quantity < 16384:
            return 'gpt-3.5-turbo-16k'
        elif token_quantity >= 16384 and token_quantity <= 32768:
            raise Exception('Text is too long for GPT-3.5')
        else:
            raise Exception('Text is too long for GPT-3.5')
        