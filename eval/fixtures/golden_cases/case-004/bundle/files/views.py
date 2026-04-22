from flask import Flask, request

app = Flask(__name__)


@app.route("/profile")
def profile():
    name = request.args.get("name", "")
    bio = request.args.get("bio", "")
    html = f"""
    <html>
    <body>
        <h1>Profile: {name}</h1>
        <div class="bio">{bio}</div>
    </body>
    </html>
    """
    return html
