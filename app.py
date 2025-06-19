import sys
from flask import Flask
from flask_cors import CORS
from file_uploader import handle_upload
from selinium_helpers import auto_upload_from_folder, teardown_driver, use_cloned_chrome_profile_directly

import json

def read_args_from_json(config_path):
    with open(config_path, 'r') as f:
        data = json.load(f)
    required_keys = ["email", "password", "input_dir", "success_dir"]
    for key in required_keys:
        if key not in data or not data[key]:
            print("*************************************************************")
            print(f"Error: The required setting '{key}' is missing or empty in your configuration file: {config_path}")
            print("Please edit your configuration file and make sure all required fields are filled in.\n")
            print("*************************************************************")
            sys.exit(1)
    return data["email"], data["password"], data["input_dir"], data["success_dir"]



if __name__ == "__main__":
    # Read config from environment or command line
    # Example usage: python script.py myemail@example.com mypassword /input/dir /success/dir
    if len(sys.argv) != 2:
        print("Usage: python run_automation.py <config.txt>")
        sys.exit(1)
    config_file = sys.argv[1]
    email, password, input_dir, success_dir = read_args_from_json(config_file)
    handle_upload(email, password, input_dir, success_dir)
