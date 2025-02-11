import os
import asyncio
import aiohttp
from aiofiles import open as aio_open
from urllib.parse import quote
import base64
import urllib.parse
import re
import time
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
import subprocess
import json
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
import motor.motor_asyncio

def send_email(subject, body, sender_email, sender_email_password, to_email):
    """Send an email notification."""
    try:
        sender_email = sender_email
        sender_password = sender_email_password

        #if not sender_email or not sender_password:
            #raise ValueError("Email credentials not set in environment variables.")
        
        if sender_email == "" or sender_email_password == "" or to_email == "":
            print("No email given!")
            return
        
        # Setup the MIME
        message = MIMEMultipart()
        message['From'] = sender_email
        message['To'] = to_email
        message['Subject'] = subject
        message.attach(MIMEText(body, 'plain'))

        # Connect to the SMTP server
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()  # Secure the connection
            server.login(sender_email, sender_password)
            server.send_message(message)
        print(f"Email sent to {to_email}")
    except Exception as e:
        print(f"Failed to send email: {e}")

def encode_url_component(component):
    return urllib.parse.quote(component, safe='+')

async def download_image(session, file_url, file_path, user_agent):
    """Download a single image asynchronously and add metadata."""
    try:
        async with session.get(file_url, headers={"User-Agent": user_agent}) as response:
            if response.status == 200:
                async with aio_open(file_path, "wb") as f:
                    await f.write(await response.read())
                print(f"Downloaded: {file_path}")

            else:
                print(f"Failed to download {file_url}: {response.status}")
    except Exception as e:
        print(f"Error downloading {file_url}: {e}")

from pymongo import MongoClient

# Connect to MongoDB (local instance) (CHANGE THIS TO YOUR INSTANCE IF NEEDED)
client = MongoClient("mongodb://localhost:27017")
#client = motor.motor_asyncio.AsyncIOMotorClient("mongodb://localhost:27017")
db = client["image_database"]  # Database name
collection = db["images"]  # Collection for storing posts

def insert_post_to_mongo(post, local_path, fav_tag=None):
    """Insert a post into MongoDB, ensuring no duplicates."""
    post["local_path"] = local_path  # Add local file path
    
    if fav_tag:
        post["favorite_of"] = fav_tag

    # Avoid duplicate inserts by checking post ID
    existing = collection.find_one({"id": post["id"]})
    if existing:
        print(f"Post {post['id']} already exists, skipping insert.")
        return

    collection.insert_one(post)
    print(f"Inserted post {post['id']} into MongoDB.")
    
def edit_fav_post_mongo(post, local_path, fav_tag):
    fav_post = collection.find_one({"id": post['id']})
    if fav_post is None:
        print(f"Could not find post {post['id']} for editing.")
        insert_post_to_mongo(post, local_path, fav_tag)
        return
    
    favorite_of = fav_post.get("favorite_of", "")

    if fav_tag in favorite_of:
        return
    
    # Append the fav_tag properly
    updated_favorites = f"{favorite_of}, {fav_tag}" if favorite_of else fav_tag

    # Correct update query
    collection.update_one(
        {"id": fav_post['id']},  # Filter
        {"$set": {"favorite_of": updated_favorites}}  # Update operation
    )
    
    print(f"Edited post {fav_post['id']} in MongoDB for user {fav_tag}")

def encode_url_component(component):
    return urllib.parse.quote(component, safe='+')
    
num_downloads = 0

async def download_images(tags, e6_user_agent, e6_api_key, sender_email="", sender_email_password="", email="", base_dir="", refresh_mode=False, start_from=None):
    """Fetch and store images asynchronously in MongoDB."""
    global num_downloads
    start_time = time.time()
    send_email("Download Started", f"Your download for tags '{tags}' started at {time.time()}.", sender_email, sender_email_password, email)
    folder_path = Path(base_dir)
    os.makedirs(folder_path, exist_ok=True)

    user_agent = "e6ImageSaver/2.0 (by N_o_p_e on e621)"
    username = e6_user_agent
    api_key = e6_api_key
    
    fav_tag = next((word for word in tags.split() if 'fav:' in word), None)
    print(f"Found a favorite request for {fav_tag}.")

    limit = 200
    page = "first"
    urlified_tags = encode_url_component(tags.strip().replace(" ", "+"))
    base_url = f"https://e621.net/posts.json?limit={limit}&tags={urlified_tags}"

    auth_string = f"{username}:{api_key}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()
    headers = {"Authorization": f"Basic {auth_encoded}", "User-Agent": user_agent}

    async with aiohttp.ClientSession() as session:
        while True:
            print(f"\nNow on page {page}\n")

            try:
                async with session.get(base_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Error {response.status}: {await response.text()}")
                        await asyncio.sleep(30)
                        continue

                    data = await response.json()
                    if not data.get("posts"):
                        print("No more posts found.")
                        break

                    lowest_id = float('inf')
                    tasks = []

                    for post in data["posts"]:
                        file_url = post.get("file", {}).get("url")
                        if not file_url:
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
                        
                        #insert_post_to_mongo(post, str(file_path)) # GET RID OF ME

                        lowest_id = min(lowest_id, post.get('id'))
                        post_exists = os.path.exists(file_path)
                        #if post_exists and not fav_tag:
                            #continue  # Skip if file exists
                        if post_exists and fav_tag:
                            edit_fav_post_mongo(post, str(file_path), fav_tag[4:]) # Update the favorite tag of the post
                            continue
                        elif fav_tag:
                            insert_post_to_mongo(post, str(file_path), fav_tag[4:])
                        else:
                            insert_post_to_mongo(post, str(file_path))
                            
                        num_downloads += 1

                        print(f"Queueing download for {file_name}...")
                        tasks.append(download_image(session, file_url, file_path, user_agent))

                    if len(tasks) == 0 and refresh_mode:
                        #print("All files downloaded.")
                        break

                    # Download all images concurrently
                    await asyncio.gather(*tasks)

                    if page == 'first' and start_from:
                        page = start_from
                    else:
                        page = 'b' + str(lowest_id)
                    
                    base_url = f"https://e621.net/posts.json?page={page}&limit={limit}&tags={urlified_tags}"
                    await asyncio.sleep(1.05)

            except Exception as e:
                print(f"Error: {e}")
                await asyncio.sleep(60)
                #break

    elapsed_time = time.time() - start_time
    print(f"\nTotal runtime: {elapsed_time:.2f} seconds")
    print(f"\nTotal downloads: {num_downloads}")
    send_email("Download Completed", f"Your download for tags '{tags}' completed in {elapsed_time:.2f} seconds at {time.time()}.", sender_email, sender_email_password, email)

import sys

if __name__ == "__main__":
    # Parse "-r" (refresh mode)
    sender_email = ""
    sender_email_password = ""
    email = ""
    folder_path = ""
    start_from = None
    refresh_mode = False
    
    if "-r" in sys.argv:
        refresh_mode = True
        sys.argv.remove("-r")  # Remove -r to keep argument positions correct

    # Parse "-s" (start_from)
    if "-s" in sys.argv:
        s_index = sys.argv.index("-s")
        if s_index + 1 < len(sys.argv):  # Ensure an argument follows -s
            start_from = sys.argv[s_index + 1]
            del sys.argv[s_index:s_index + 2]  # Remove -s and its argument
        else:
            print("Error: '-s' option requires an argument specifying where to start from.")
            sys.exit(1)

    # Parse "-e" (email options)
    if "-e" in sys.argv:
        e_index = sys.argv.index("-e")
        if e_index + 3 < len(sys.argv):  # Ensure three arguments follow -e
            sender_email = sys.argv[e_index + 1]
            sender_email_password = sys.argv[e_index + 2]
            email = sys.argv[e_index + 3]
            del sys.argv[e_index:e_index + 4]  # Remove -e and its arguments
        else:
            print("Error: '-e' option requires three arguments: sender_email sender_email_password email.")
            sys.exit(1)

    # Parse "-f" (download folder path)
    if "-f" in sys.argv:
        f_index = sys.argv.index("-f")
        if f_index + 1 < len(sys.argv):  # Ensure an argument follows -f
            folder_path = sys.argv[f_index + 1]
            del sys.argv[f_index:f_index + 2]  # Remove -f and its argument
        else:
            print("Error: '-f' option requires an argument specifying the download folder path.")
            sys.exit(1)

    # Check the number of remaining arguments after removing -r, -s, -e, and -f
    if len(sys.argv) != 4:
        print("Usages:\n python3 async_e6_downloader.py \"<tags>\" <e6 username> <e6 api-key>\n"
              " Optional flags:\n"
              "   -r                        Enable refresh mode\n"
              "   -s <start_from>          Specify where to start from\n"
              "   -e <email> <password> <recipient>  Send email notifications\n"
              "   -f <download_folder>     Specify download folder path")
        sys.exit(1)

    # Process arguments
    tags = sys.argv[1]
    e6_agent = sys.argv[2]
    e6_key = sys.argv[3]

    # Call the function with the parsed arguments
    asyncio.run(download_images(tags, e6_agent, e6_key, sender_email, sender_email_password, email, base_dir=folder_path, refresh_mode=refresh_mode, start_from=start_from))
