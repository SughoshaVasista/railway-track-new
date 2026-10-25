from datetime import datetime, timezone
from flask import Flask, jsonify, request

app = Flask(__name__)

alerts = [
    {"id": "ALT-102", "defect": "Crack", "severity": "S3", "track": "Track A", "chainage": "KM 12/4", "confidence": 0.94, "status": "ACTIVE"},
    {"id": "ALT-103", "defect": "Joint Gap", "severity": "S2", "track": "Track B", "chainage": "KM 13/2", "confidence": 0.87, "status": "ACKNOWLEDGED"},
]
devices = [{"id": "device-01", "name": "AMRIN-01", "platform": "Raspberry Pi", "status": "ONLINE", "uptime": None}]
tasks = []
workers = [{"id": "worker-01", "name": "Maintenance Worker", "status": "ONLINE", "role": "worker"}]
users = {
    "admin": {"password": "admin", "role": "admin", "name": "Admin User"},
    "worker": {"password": "worker", "role": "worker", "name": "Maintenance Worker", "worker_id": "worker-01"},
}


def envelope(data):
    return jsonify(data)


@app.after_request
def cors(response):
    response.headers["Access-Control-Allow-Origin"] = "*"
    response.headers["Access-Control-Allow-Headers"] = "Content-Type, Authorization"
    response.headers["Access-Control-Allow-Methods"] = "GET, POST, OPTIONS"
    return response


@app.post("/api/auth/login")
def login():
    body = request.get_json(silent=True) or {}
    user = users.get(body.get("username"))
    if not user or user["password"] != body.get("password"):
        return envelope({"error": "Invalid credentials"}), 401
    # Production backend must re-check the authenticated role on every endpoint.
    result = {"token": f"mock-{body['username']}-token", "role": user["role"], "name": user["name"]}
    if user.get("worker_id"):
        result["worker_id"] = user["worker_id"]
    return envelope(result)


@app.get("/api/alerts")
def list_alerts():
    result = alerts
    for key in ("severity", "status", "track"):
        if request.args.get(key):
            result = [item for item in result if item.get(key) == request.args[key]]
    return envelope({"items": result})


@app.get("/api/alerts/<alert_id>")
def alert_detail(alert_id):
    return envelope(next((item for item in alerts if item["id"] == alert_id), {}))


@app.post("/api/alerts/<alert_id>/<action>")
def alert_action(alert_id, action):
    item = next((item for item in alerts if item["id"] == alert_id), None)
    if item and action in {"acknowledge", "resolve", "false-positive"}:
        item["status"] = {"acknowledge": "ACKNOWLEDGED", "resolve": "RESOLVED", "false-positive": "FALSE_POSITIVE"}[action]
    if action == "history":
        return envelope({"items": []})
    return envelope(item or {})


@app.get("/api/alerts/<alert_id>/history")
def alert_history(alert_id):
    return envelope({"items": []})


@app.get("/api/devices")
def list_devices():
    return envelope({"items": devices})


@app.get("/api/devices/<device_id>/sensors")
def sensors(device_id):
    return envelope({"items": []})


@app.get("/api/devices/<device_id>/diagnostics")
def diagnostics(device_id):
    return envelope({"device_id": device_id, "status": "NO_DATA", "checks": []})


@app.get("/api/tasks")
def list_tasks():
    return envelope({"items": tasks})


@app.post("/api/tasks")
def create_task():
    body = request.get_json(silent=True) or {}
    task = {"id": f"TASK-{len(tasks) + 1:03d}", **body}
    tasks.append(task)
    return envelope(task), 201


@app.get("/api/workers")
def list_workers():
    return envelope({"items": workers})


@app.route("/api/tasks/<task_id>/<action>", methods=["POST", "PUT"])
def task_action(task_id, action):
    if action == "evidence":
        return envelope({"task_id": task_id, "status": "RECEIVED"})
    return envelope({"task_id": task_id, "status": request.json.get("status") if request.is_json else None})


@app.get("/api/tracks")
def tracks():
    return envelope({"items": []})


@app.get("/api/trains")
def trains():
    return envelope({"items": []})


@app.get("/api/switch/status")
def switch_status():
    return envelope({"status": "READY", "action": "MAINTAIN", "action_level": "WARNING", "train_id": "train_0", "switch_id": "switch_0", "target_track": "Track A", "confidence": 0.78, "reason": "Track A has S2 defect. Track B is occupied.", "rules_checked": [{"rule": "Target track is not occupied", "passed": True}, {"rule": "No S3 defect on target track", "passed": True}, {"rule": "Switch mechanism is available", "passed": True}, {"rule": "Train is not too close to switch", "passed": True}], "raw_scores": {"A": 0.78, "B": None}})


@app.post("/api/switch/decision")
def switch_decision():
    return envelope({"status": "RECEIVED", "decision": request.get_json(silent=True)})


@app.get("/api/simulation/state")
def simulation_state():
    return envelope({"status": "DISCONNECTED"})


@app.post("/api/simulation/mode")
def simulation_mode():
    return envelope({"mode": request.json.get("mode") if request.is_json else None})


@app.get("/api/dashboard/summary")
def dashboard_summary():
    return envelope({"active_alerts": len(alerts), "s3_alerts": sum(item["severity"] == "S3" for item in alerts), "s2_alerts": sum(item["severity"] == "S2" for item in alerts), "s1_alerts": 0, "pending_tasks": len(tasks), "online_devices": sum(item["status"] == "ONLINE" for item in devices), "total_devices": len(devices)})


@app.get("/api/dashboard/event-log")
def event_log():
    return envelope({"items": [], "generated_at": datetime.now(timezone.utc).isoformat()})


@app.get("/api/model/status")
def model_status():
    return envelope({"status": "NO_DATA"})


@app.get("/api/inference/status")
def inference_status():
    return envelope({"status": "MOCK_MODE", "loaded": False, "inference_active": False, "weights_available": False, "name": None, "runtime_version": None, "class_count": None, "input_size": None, "inference_ms": None, "device": None, "last_inference_at": None})


@app.post("/api/inference/detect")
def inference_unavailable():
    return jsonify({"success": False, "data": None, "error": "Image inference is unavailable on the mock server. Start the FastAPI ML backend to run the trained model."}), 503


@app.get("/api/ai/detection")
def ai_detection():
    return envelope({"status": "NO_DATA"})


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=8000, debug=True)
