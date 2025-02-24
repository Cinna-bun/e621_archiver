import os
import requests
import base64
import urllib.parse
import time
import json
from datetime import datetime
from pathlib import Path
from pymongo import MongoClient

"""
THIS FILE IS FOR IF YOUR MONGODB IS HAVING TROUBLE PUTTING EVERY FILE INTO THE COLLECTION. 
RUN THIS IN ORDER TO FIX IT AND ENSURE ALL FILES ARE PRESENT.
"""

# MongoDB setup
client = MongoClient("mongodb://localhost:27017")
db = client["image_database"]  # Database name
collection = db["images"]  # Collection for storing posts

def encode_url_component(component):
    return urllib.parse.quote(component, safe='+')

def insert_post_to_mongo(post, local_path, fav_tag=None):
    """Insert a post into MongoDB, ensuring no duplicates."""
    post["local_path"] = local_path  # Add local file path
    
    if fav_tag:
        post["favorite_of"] = fav_tag

    # Avoid duplicate inserts by checking post ID
    if collection.find_one({"id": post["id"]}):
        print(f"Post {post['id']} already exists, skipping insert.")
        return

    collection.insert_one(post)
    print(f"Inserted post {post['id']} into MongoDB.")

def download_images():
    user_agent = "e6ImageSaver/2.0 (by N_o_p_e on e621)"
    username = 'N_o_p_e'
    api_key = 'eAhg2kLZKrbzraJUokFdJUf9'
    
    folder_path = Path('/media/misu/Elements/Archive/Mongo_e6_Archive')
    limit = 320
    page = "first"
    tags = "score:>49"
    urlified_tags = encode_url_component(tags.strip().replace(" ", "+"))
    base_url = f"https://e621.net/posts.json?limit={limit}&tags={urlified_tags}"

    auth_string = f"{username}:{api_key}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()
    headers = {"Authorization": f"Basic {auth_encoded}", "User-Agent": user_agent}

    while True:
        print(f"\nNow on page {page}\n")
        try:
            response = requests.get(base_url, headers=headers)
            if response.status_code != 200:
                print(f"Error {response.status_code}: {response.text}")
                time.sleep(30)
                continue

            data = response.json()
            if not data.get("posts"):
                print("No more posts found.")
                break

            lowest_id = float('inf')

            for post in data["posts"]:
                file_url = post.get("file", {}).get("url")
                if not file_url:
                    print('File with no URL!')
                    continue
                
                # Extract post date
                dt = datetime.strptime(post.get("created_at", ""), "%Y-%m-%dT%H:%M:%S.%f%z")
                year, month, day = str(dt.year), str(dt.month).zfill(2), str(dt.day).zfill(2)

                # Organize by date
                specific_folder_path = Path(folder_path) / year / month / day
                specific_folder_path.mkdir(parents=True, exist_ok=True)

                # Construct file path
                file_name = file_url.split("/")[-1]
                file_path = specific_folder_path / file_name
                        
                lowest_id = min(lowest_id, post.get('id'))
                if os.path.exists(file_path):
                    insert_post_to_mongo(post, str(file_path))
            
            if page == 'first' and False:
                page = 'b4141764'
            else:
                page = 'b' + str(lowest_id)
            
            base_url = f"https://e621.net/posts.json?page={page}&limit={limit}&tags={urlified_tags}"
            time.sleep(1)
            
        except Exception as e:
            print(f"Error: {e}")
            time.sleep(60)

if __name__ == "__main__":
    download_images()
