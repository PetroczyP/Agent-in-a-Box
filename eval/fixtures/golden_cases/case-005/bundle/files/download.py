import os
from flask import Flask, request, send_file, abort

app = Flask(__name__)
UPLOAD_DIR = "/var/app/uploads"


@app.route("/download")
def download_file():
    filename = request.args.get("file", "")
    filepath = os.path.join(UPLOAD_DIR, filename)
    if not os.path.exists(filepath):
        abort(404)
    return send_file(filepath, as_attachment=True)
