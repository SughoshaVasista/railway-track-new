from __future__ import annotations

import json
from flask import Flask, jsonify, request

app = Flask(__name__)


@app.post("/api/switch/decision")
def receive():
    data = request.get_json(silent=True)
    if not isinstance(data, dict):
        return jsonify({"success": False, "error": "JSON object required"}), 400
    print("─" * 50, flush=True)
    print(json.dumps(data, indent=2, allow_nan=False), flush=True)
    return jsonify({"success": True})


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=8000)
