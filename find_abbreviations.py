import json
import re

# Load tag abbreviations from e6_tags_abbreviated.json
def load_tags(filename="e6_tags_abbreviated.json"):
    with open(filename, "r", encoding="utf-8") as f:
        tags = json.load(f)
    return {tag["name"]: tag["abbreviation"] for tag in tags}  # Convert list to dict {name: abbreviation}

# Function to abbreviate a user input string
def abbreviate_string(input_string, tag_dict):
    words = re.split(r'[/_ ]', input_string)  # Split by space, underscore, or slash
    abbreviated_words = [tag_dict.get(word, word) for word in words]  # Replace words with abbreviations
    return abbreviated_words  # Return list of abbreviations

# Generate search query based on OS
def generate_search_query(abbreviations, os_type):
    if not abbreviations:
        return ""

    if os_type == "windows":
        return f'filename:{" AND filename:".join(abbreviations)}'
    elif os_type == "macos":
        return f'({" && ".join([f\'kMDItemFSName == "*{word}*"\' for word in abbreviations])})'
    return ""

# Main function to handle user input
def main():
    # Ask user for OS type
    while True:
        os_choice = input("Are you using Windows or macOS? (Enter 'windows' or 'macos'): ").strip().lower()
        if os_choice in ["windows", "macos"]:
            break
        print("Invalid input. Please enter 'windows' or 'macos'.")

    tag_dict = load_tags()
    
    while True:
        user_input = input("\nEnter a tag string to abbreviate (or type 'exit' to quit): ").strip().lower()
        if user_input == "exit":
            print("Goodbye!")
            break

        abbreviated_list = abbreviate_string(user_input, tag_dict)
        search_query = generate_search_query(abbreviated_list, os_choice)

        print(f"?? Abbreviated: {'-'.join(abbreviated_list)}")
        print(f"?? Use this in {os_choice.title()} search: {search_query}")

if __name__ == "__main__":
    main()
