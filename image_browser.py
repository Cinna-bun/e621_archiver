from flask import Flask, request, render_template
from pymongo import MongoClient
import os

# Ask the user for the static folder path at startup
STATIC_FOLDER = input("Enter the static folder path (e.g., /mnt/external/images): ").strip()

# Check if the path exists; if not, keep asking
while not os.path.exists(STATIC_FOLDER):
    print(f"Error: '{STATIC_FOLDER}' does not exist. Please enter a valid path.")
    STATIC_FOLDER = input("Enter the static folder path: ").strip()

app = Flask(__name__, static_folder=STATIC_FOLDER)

# Connect to MongoDB (local instance)
client = MongoClient("mongodb://localhost:27017")
db = client["image_database"]  # Database name
collection = db["images"]  # Collection storing image documents

@app.route("/", methods=["GET"])
def search():
    tag_query = request.args.get("tag", "").strip()
    page = int(request.args.get("page", 1))  # Get page number, default to 1
    per_page = 50  # Number of images per page

    results_changed = []
    total_pages = 1
    query = {}

    if tag_query:
        tags = tag_query.split()
        tag_conditions = []
        favorite_condition = None

        for tag in tags:
            if tag.startswith("fav:"):
                favorite_user = tag.split(":", 1)[1]
                favorite_condition = {"favorite_of": favorite_user}
            else:
                tag_conditions.append({"$or": [{f"tags.{group}": tag} for group in ["general", "species", "character", "artist", "invalid", "lore", "meta"]]})
        
        # Merge conditions
        if tag_conditions:
            query["$and"] = tag_conditions
        if favorite_condition:
            query.update(favorite_condition)
        
        projection = {"local_path": 1, "_id": 0}

        # Fetch results from MongoDB
        all_results = [doc["local_path"] for doc in collection.find(query, projection)]
        total_pages = (len(all_results) + per_page - 1) // per_page  # Calculate total pages

        # Paginate results
        start = (page - 1) * per_page
        end = start + per_page
        paginated_results = all_results[start:end]

        # Apply path transformation logic
        for result in paginated_results:
            results_changed.append("/" + os.path.join(*result.split("/")[-5:]))

    return render_template("results.html", results=results_changed, tag=tag_query, page=page, total_pages=total_pages)

if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000, debug=True)
