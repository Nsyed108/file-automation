from flask import Flask
from flask_cors import CORS
from selinium_helpers import auto_upload_from_folder, teardown_driver, use_cloned_chrome_profile_directly

app = Flask(__name__)
CORS(app)

if __name__ == '__main__':
    try:
        print("Starting Flask server...")
        # Auto start upload
        auto_upload_from_folder("Sypore", "Performance@1124", "/home/nabeel/Documents/downloaded-files")
        app.run(debug=False, port=5000, threaded=False)
    except Exception as e:
        print(f"Flask application failed to start or encountered a fatal error: {e}")
    finally:
        print("Flask application stopping. Attempting to close driver...")
        teardown_driver()
