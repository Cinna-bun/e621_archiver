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

# API URL for tags
BASE_URL = "https://e621.net/tags.json?search[order]=count&limit=320&page={}"
HEADERS = {"User-Agent": "e621TagScraper/1.4 (by N_o_p_e)"}
OUTPUT_FILE = "e621_tags.json"

tag_list_abbreviated = []

async def fetch_tags(session, page):
    """Fetch a page of tags from e621."""
    url = BASE_URL.format(page)
    async with session.get(url, headers=HEADERS) as response:
        if response.status != 200:
            print(f"Failed to fetch page {page}: {response.status}")
            return []

        data = await response.json()
        
        if isinstance(data, list):  # Ensure data is a list (API returns a list of tags)
            return data
        else:
            print(f"Unexpected response format on page {page}: {data}")
            return []



async def scrape_all_tags():
    """Scrape all tags from e621 asynchronously."""
    all_tags = []
    page = 1
    
    if os.path.exists("e621_tags.json"):
        return

    async with aiohttp.ClientSession() as session:
        while page <= 175:
            print(f"Fetching page {page}...")
            tags = await fetch_tags(session, page)
            #print(tags)
            #print(tags[0]['name'])
            #print(''.join(word[0] for word in re.split(r'[/_]', tags[0]['name'])))
            
            all_tags.extend(tags)
            page += 1
            await asyncio.sleep(1.05)  # Rate limit (1 request/sec)

    # Save to a JSON file
    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:
        json.dump(all_tags, f, indent=2)

    print(f"? Scraped {len(all_tags)} tags and saved to {OUTPUT_FILE}")
    
INPUT_FILE = "e621_tags.json"
OUTPUT_FILE_ABBREV = "e6_tags_abbreviated.json"

def generate_unique_abbreviations(tags):
    """Generate unique abbreviations for tags and add them to each tag dictionary."""
    abbreviations = set()  # Store unique abbreviations

    for tag in tags:
        name = tag["name"]

        # Extract initials from the tag name, ensuring no empty parts
        #print(name)
        abbr = ''.join(word[0] for word in re.split(r'[/_]', name) if word)
        unique_abbr = abbr  # Start with the basic abbreviation

        # Ensure uniqueness by adding extra letters if needed
        extra_index = 1
        while unique_abbr in abbreviations:
            if extra_index < len(name):  # Append more characters if needed
                unique_abbr = abbr + name[extra_index]
                extra_index += 1
            else:
                break  # Stop if no more characters are available

        # Store abbreviation and mark it as used
        abbreviations.add(unique_abbr)
        tag["abbreviation"] = unique_abbr  # Add abbreviation to the dictionary

    return tags  # Return modified list with abbreviations

def abbreviator_main():
    """Load e621_tags.json, add abbreviations, and save to e6_tags_abbreviated.json."""
    # Load tags from the JSON file
    with open(INPUT_FILE, "r", encoding="utf-8") as f:
        tags = json.load(f)

    # Generate abbreviations
    updated_tags = generate_unique_abbreviations(tags)
    abbreviated_count = sum(1 for tag in updated_tags if (tag.get("abbreviation") and tag.get("abbreviation") != ""))
    print(f"Finished and abbreviated {abbreviated_count} tags!")

    # Save updated tags with abbreviations
    with open(OUTPUT_FILE_ABBREV, "w", encoding="utf-8") as f:
        json.dump(updated_tags, f, indent=2)

    print(f"? Abbreviations added and saved to {OUTPUT_FILE}")


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

def sanitize_filename(name):
    words_to_discard = {"-gore", "-death", "-scat"}
    name = "+".join([word for word in name.split() if word not in words_to_discard])
    return re.sub(r'[<>:"/\\|?*]', '_', name)

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

abbrev_path = Path("e6_tags_abbreviated.json")
async def ensure_tags():
    if not os.path.exists(abbrev_path):
        await scrape_all_tags()
        abbreviator_main()

async def download_images(tags, e6_user_agent, e6_api_key, sender_email, sender_email_password, email, base_dir=""):
    """Main function to fetch images asynchronously."""
    start_time = time.time()  # Start tracking time
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_email("Download Started", f"Your download for tags '{tags}' has started at {now}.", sender_email, sender_email_password, email)
    
    abbreviation_path = Path("example.txt")
    
    folder_name = sanitize_filename(tags)
    folder_path = os.path.join(base_dir, folder_name)

    # Create the folder if it doesn't exist
    os.makedirs(folder_path, exist_ok=True)

    user_agent = "e6ImageSaver/2.0 (by N_o_p_e on e621)"
    username = e6_user_agent
    api_key = e6_api_key

    limit = 50
    page = "first"
    
    urlified_tags = encode_url_component(tags.strip().replace(" ", "+"))
    base_url = f"https://e621.net/posts.json?limit={limit}&tags={urlified_tags}"

    auth_string = f"{username}:{api_key}"
    auth_encoded = base64.b64encode(auth_string.encode()).decode()

    headers = {
        "Authorization": f"Basic {auth_encoded}",
        "User-Agent": user_agent,
    }
    
    global tag_list_abbreviated
    
    await ensure_tags()
        
    with open("e6_tags_abbreviated.json", "r", encoding="utf-8") as f:
            tag_list_abbreviated = json.load(f)
        

    async with aiohttp.ClientSession() as session:
        while True:
            print(f"\nNow on page {page}\n")

            try:
                async with session.get(base_url, headers=headers) as response:
                    if response.status != 200:
                        print(f"Error {response.status}: {await response.text()}")
                        break

                    data = await response.json()

                    if not data.get("posts"):
                        print("No more posts found.")
                        break

                    lowest_id = float('inf')
                    tasks = []

                    for post in data["posts"]:
                        file_url = post.get("file", {}).get("url")
                        
                        #print(f"This file is { post.get('file').get('size') / 1000000 } mb")

                        if not file_url:
                            print(f"Skipping post {post['id']} as it has no file URL.")
                            continue
                            
                        # Ensure tag_list is a flat list of strings
                        tag_list = post.get("tags", {}).get("general", []) + \
                                   post.get("tags", {}).get("species", []) + \
                                   post.get("tags", {}).get("character", [])

                        # Ensure all entries in `tag_list_abbreviated` have an abbreviation key
                        tag_abbreviation_dict = {
                            tag["name"]: tag["abbreviation"]
                            for tag in tag_list_abbreviated if "abbreviation" in tag
                        }

                        # Replace tags with abbreviations (fallback to original tag if missing)
                        tags_abbreviated = [tag_abbreviation_dict.get(tag, tag) for tag in tag_list]


                        #print(file_url.split("/")[-1][-9:])
                        # Construct the sanitized file name
                        artists = post.get("tags", {}).get("artist", [])
                        file_name = sanitize_filename("-".join(artists + tags_abbreviated + [file_url.split("/")[-1][-9:]]))

                        # Ensure filename is within limits
                        thrown_out = False
                        loop = 1
                        while len(file_name) > 255:
                            thrown_out = True
                            loop += 1
                            if loop == 1000:
                                tags_abbreviated = []
                            elif loop > 1000:
                                artists = ['too_long']
                            else:
                                tags_abbreviated = tags_abbreviated[:-1]  # Remove last abbreviation
                            file_name = sanitize_filename("-".join(artists + tags_abbreviated + [file_url.split("/")[-1][-9:]]))

                        #if thrown_out:
                            #print("Name was too long. Had to throw out some tags.")
                        file_path = os.path.join(folder_path, file_name)
                        
                        lowest_id = min(lowest_id, post.get('id'))
                        if os.path.exists(file_path):
                            continue

                        print(f"Queueing download for {file_name}...")
                        tasks.append(download_image(session, file_url, file_path, user_agent))

                    # Download all images concurrently
                    await asyncio.gather(*tasks)

                    if len(data["posts"]) < limit:
                        print("All posts downloaded.")
                        break
                    
                    # REMOVE THIS CODE LATER
                    if page == 'first':
                        page = 'b5200901'
                    else:
                        page = 'b' + str(lowest_id)
                    #END REMOVED CODE
                    
                    #page = 'b' + str(lowest_id)
                    
                    base_url = f"https://e621.net/posts.json?page={page}&limit={limit}&tags={urlified_tags}"
                    await asyncio.sleep(1.05)

            except Exception as e:
                print(f"Error: {e}")
                break
    end_time = time.time()  # End tracking time
    elapsed_time = end_time - start_time
    print(f"\nTotal runtime: {elapsed_time:.2f} seconds")
    now = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    send_email("Download Completed", f"Your download for tags '{tags}' has completed in {elapsed_time:.2f} seconds at {now}.", sender_email, sender_email_password, email)

if __name__ == "__main__":
    import sys
    #print(len(sys.argv))
    if len(sys.argv) < 4 or len(sys.argv) > 8 or len(sys.argv) == 6:
        print("Usages:\n python3 async_e6_downloader.py \"<tags>\" <e6 username> <e6 api-key>\n python3 async_e6_downloader.py \"<tags>\" <e6 username> <e6 api-key> <download folder path>\n python3 async_e6_downloader.py \"<tags>\" <e6 username> <e6 api-key> <sender_email> <sender_email_password> <receiver_email>\n python3 async_e6_downloader.py \"<tags>\" <e6 username> <e6 api-key> <sender_email> <sender_email_password> <receiver_email> <download folder path>")
    elif len(sys.argv) == 4:
        tags = (sys.argv[1])
        e6_agent = sys.argv[2]
        e6_key = sys.argv[3]
        asyncio.run(download_images(tags, e6_agent, e6_key, "", "", ""))
    elif len(sys.argv) == 5:
        tags = (sys.argv[1])
        e6_agent = sys.argv[2]
        e6_key = sys.argv[3]
        folder_path = sys.argv[4]
        asyncio.run(download_images(tags, e6_agent, e6_key, "", "", "", base_dir=folder_path))
    elif len(sys.argv) == 7:
        tags = (sys.argv[1])
        e6_agent = sys.argv[2]
        e6_key = sys.argv[3]
        sender_email = sys.argv[4]
        sender_email_password = sys.argv[5]
        email = sys.argv[6]
        asyncio.run(download_images(tags, e6_agent, e6_key, sender_email, sender_email_password, email))
    else:
        tags = (sys.argv[1])
        e6_agent = sys.argv[2]
        e6_key = sys.argv[3]
        sender_email = sys.argv[4]
        sender_email_password = sys.argv[5]
        email = sys.argv[6]
        folder_path = sys.argv[7]
        asyncio.run(download_images(tags, e6_agent, e6_key, sender_email, sender_email_password, email, base_dir=folder_path))
