import os
import sys
# Import pathlib for more robust path handling, though os.path will work fine too
from google import genai

# --- CONFIGURATION ---
# We assume the user runs this script from a location where 'data/commits' is accessible.
# CHANGE THIS PATH to match your top-level directory structure.
DIFFS_FOLDER = "data/diffsets"
MODEL_NAME = "gemini-2.5-flash"
# ---------------------

def create_gemini_client():
    """Initializes and verifies the Gemini client."""
    try:
        return genai.Client()
    except Exception as e:
        print("Error: Could not initialize the Gemini client.")
        print("Please ensure the GEMINI_API_KEY environment variable is configured.")
        print(f"Error detail: {e}")
        sys.exit(1)

def generate_commit_message(diff_content: str, client: genai.Client) -> str:
    """
    Generates a commit message from the diff content using the Gemini model.
    """

    # The English Prompt (remains the same and is effective)
    prompt = f"""
    Generate a concise and descriptive commit message based on the following diff.
    The message must follow the Conventional Commits format (e.g., 'feat:', 'fix:', 'docs:', etc.).
    The subject line (first line) should be less than 70 characters.
    Include a more detailed message body if necessary.
    ONLY return the generated commit message, without any other explanations, headers, or triple quotes.

    Diff content:
    --- DIFF START ---
    {diff_content}
    --- DIFF END ---
    """

    try:
        response = client.models.generate_content(
            model=MODEL_NAME,
            contents=prompt
        )
        return response.text.strip()
    except Exception as e:
        return f"❌ GEMINI_ERROR: Could not generate message. Detail: {e}"

if __name__ == "__main__":

    # 1. Initialize the client
    gemini_client = create_gemini_client()

    # 2. Check for the existence of the diffs folder
    if not os.path.isdir(DIFFS_FOLDER):
        print(f"⚠️ The top-level folder '{DIFFS_FOLDER}' does not exist.")
        print("Please ensure the path is correct.")
        sys.exit(0)

    print(f"Searching for diff files (*.txt) recursively starting in '{DIFFS_FOLDER}'...")

    files_processed = 0

    # 3. Iterate over the entire directory tree using os.walk()
    # root: current folder path (e.g., data/commits/app1)
    # dirs: list of subfolder names in root
    # files: list of file names in root
    for root, dirs, files in os.walk(DIFFS_FOLDER):
        for filename in files:
            # Check for .txt files and skip previously created output files
            if filename.endswith(".txt") and not filename.endswith("_new.txt"):

                # Construct the full path for the input file
                input_filepath = os.path.join(root, filename)

                # Define the path for the new output file
                output_filename = filename.replace(".txt", "_new.txt")
                output_filepath = os.path.join(root, output_filename)

                print(f"\nProcessing file: {input_filepath}...")

                try:
                    # Read the diff content
                    with open(input_filepath, 'r', encoding='utf-8') as f:
                        diff_data = f.read()

                    # Generate the commit message
                    commit_message = generate_commit_message(diff_data, gemini_client)

                    # Save the message to the new file in the same subfolder
                    with open(output_filepath, 'w', encoding='utf-8') as f:
                        f.write(commit_message)

                    print(f"✅ Success: Commit message saved to '{output_filepath}'")
                    files_processed += 1

                except IOError as e:
                    print(f"❌ I/O Error processing {input_filepath}: {e}")
                except Exception as e:
                    print(f"❌ An unexpected error occurred while processing {input_filepath}: {e}")

    if files_processed == 0:
        print("\n🚫 No .txt files were found to process.")
    else:
        print(f"\n✨ Process completed. Total files processed: {files_processed}.")
