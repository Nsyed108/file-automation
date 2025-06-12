from flask import request, jsonify

from file_uploader import handle_upload

def register_routes(app):
    @app.route('/')
    def index():
        return jsonify({"message": "Flask PDF Upload Server is running."})

    @app.route('/upload', methods=['POST'])
    def upload_files():
        return handle_upload(request)
