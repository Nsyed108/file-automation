import os
import tempfile
import shutil
from flask import jsonify

from selinium_helpers import process_files_with_selenium

def handle_upload(request):
    email = request.form.get('email')
    password = request.form.get('password')
    uploaded_files_list = request.files.getlist("files")

    if not email or not password:
        return jsonify({"message": "Email and password are required."}), 400
    if not uploaded_files_list:
        return jsonify({"message": "No files uploaded."}), 400

    temp_dir = tempfile.mkdtemp()
    file_paths = []
    seen_filenames = set()

    for file in uploaded_files_list:
        filename = os.path.basename(file.filename)
        if not filename.lower().endswith(".pdf") or filename in seen_filenames:
            continue
        path = os.path.join(temp_dir, filename)
        file.save(path)
        file_paths.append(path)
        seen_filenames.add(filename)

    if not file_paths:
        return jsonify({"message": "No valid or unique PDF files to process."}), 400

    try:
        results = process_files_with_selenium(email, password, file_paths)
        return jsonify({"message": "File processing completed.", "results": results}), 200
    except Exception as e:
        return jsonify({"message": str(e), "results": []}), 500
    finally:
        shutil.rmtree(temp_dir, ignore_errors=True)
