import os
import json
import requests
import csv
from dotenv import load_dotenv
from datetime import datetime, timedelta

# Load .env file
load_dotenv()

# Access your API keys and token
wp_username = os.getenv('WP_USERNAME')
wp_password = os.getenv('WP_PASSWORD')
wp_token = os.getenv('WP_TOKEN')  # Get the token from environment variables


# Get the JWT token for WordPress
def get_jwt_token(username, password):
    # Use the existing token if it exists
    if wp_token:
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

# Create a new post on WordPress
def create_wordpress_post(post_info, token, post_time):
    post_endpoint = "http://cybernow.info/wp-json/wp/v2/posts"

    headers = {
        'Authorization': f'Bearer {token}',
        'Content-Type': 'application/json'
    }

    post_info['status'] = 'future'  # Set status to 'future'
    post_info['date'] = post_time.strftime('%Y-%m-%dT%H:%M:%S')  # Set date and time of publishing
    post_info['date_gmt'] = (post_time - timedelta(hours=6)).strftime('%Y-%m-%dT%H:%M:%S')  # Set GMT date and time of publishing

    response = requests.post(post_endpoint, json=post_info, headers=headers)
    if response.status_code == 201:
        print("Post created successfully.")
        return response.json()  # Return the post data
    else:
        print(f"Failed to create post: {response.text}")
        return None

def write_to_csv(post_info):
    # Define the CSV file path
    csv_file_path = './data/temp/master.csv'
    
    # Define the field names for the CSV file
    fieldnames = post_info.keys()

    # Check if file exists
    file_exists = os.path.isfile(csv_file_path)
    
    with open(csv_file_path, 'a') as csvfile:
        writer = csv.DictWriter(csvfile, fieldnames=fieldnames)
        
        # If file does not exist, write a header
        if not file_exists:
            writer.writeheader()

        # Write the post data
        writer.writerow(post_info)

def create_post_and_write_to_csv(json_file_path):
    # Get the JWT token
    token = get_jwt_token(wp_username, wp_password)
    if not token:
        return

    # Load the post information from the passed JSON file
    with open(json_file_path) as f:
        post_info = json.load(f)

    # Extract post_time from post_info
    post_time = datetime.strptime(post_info['post_time'], '%Y-%m-%dT%H:%M:%S')

    # Create the WordPress post
    post_data = create_wordpress_post(post_info, token, post_time)
    if post_data is None:  # Failed to create post
        post_info['status'] = 'failed'
        with open(json_file_path, 'w') as f:
            json.dump(post_info, f)
        return

    post_info['status'] = 'posted'
    with open(json_file_path, 'w') as f:
        json.dump(post_info, f)

    # Write the post data to the master CSV file
    write_to_csv(post_data)

