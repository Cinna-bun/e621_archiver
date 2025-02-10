# e6_scraper
A digital scraper for e621.net which is asyncronous and names files with their tags for easy searching.

# Required Dependencies
To install the required dependencies, just run "pip install -r requirements.txt" in your terminal

# Easy downloading and handling of small archives
In order to easily download and handle small archives of your favorite tags, or perhaps your favorites list, you can use async_e6_downloader.py
Please note that if you download massive numbers of files with this, your operating system might not handle browsing the folder very well, and it might crash your computer!

# For mass archiving of data
In order to download enormous numbers of files, consider using async_e6_downloader_mongodb.py

You will need to download MongoDB and create your own database (or use a remote one, if you have that ability). If you need help you can just ask chatgpt and tell it your operating system, it should give you some pretty easy steps.

Once you have that set up, go to async_e6_downloader_mongodb.py and search for "change this". You'll need to replace the database strings with yours, if it is different.

After that you should be finished! Just run the program and watch it fly.

# Browsing mass archived images
THIS ONLY WORKS WITH THE MONGODB VERSION OF THIS PROGRAM.

Now that you have all that done, you might want to browse your images you've archived in an elegant way. In order to do this, download the templates folder and image_browser.py. You'll need to make sure they're in the same directory when you run them! You will need to replace the database strings in image_browser.py with yours.

Run: python3 image_browser.py

Open a web browser and visit http://localhost:5000/, or if you are running this on a raspberry pi (as it was originally written for), you can visit http://<your_pi_IP>:5000/
