from flask import Flask, request, jsonify

app = Flask(__name__)
users_db = {}


@app.route("/admin/delete-user", methods=["POST"])
def delete_user():
    user_id = request.json.get("user_id")
    if user_id in users_db:
        del users_db[user_id]
        return jsonify({"deleted": user_id})
    return jsonify({"error": "not found"}), 404


@app.route("/admin/list-users")
def list_users():
    return jsonify(list(users_db.values()))
