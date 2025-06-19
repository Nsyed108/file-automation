import os
import sys
import tempfile
import shutil
from flask import jsonify

from selinium_helpers import process_files_with_selenium

def handle_upload(email, password, input_dir, success_dir):
    # Only process .pdf files that are unique by filename
    file_paths = []
    seen_filenames = set()
    for filename in os.listdir(input_dir):
        if filename.lower().endswith('.pdf') and filename not in seen_filenames:
            file_paths.append(os.path.join(input_dir, filename))
            seen_filenames.add(filename)

    if not file_paths:
        print("*************************************")
        print("No valid or unique PDF files to process in source folder.")
        print("*************************************")
        sys.exit(1)

    try:
        results = process_files_with_selenium(email, password, input_dir, success_dir)
        print("File processing completed. Results:")
        for result in results:
            print(result)
    except Exception as e:
        print("An error occurred:", str(e))
        sys.exit(2)