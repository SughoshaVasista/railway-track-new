# Raspberry Pi sensor input for the AMRIN simulator

The standalone simulator reads fresh sensor readings from the AMRIN API. It does not connect directly to GPIO or control railway equipment. The Raspberry Pi (or a sensor gateway running on it) sends readings to the API; the admin-only simulator polls the selected registered device every three seconds.

## 1. Configure the backend

Set a long random `SENSOR_INGEST_TOKEN` in `backend/.env`, then restart FastAPI. Keep this secret on the backend and Raspberry Pi only. Never put it in a `VITE_` variable or browser code.

## 2. Register the device

Sign in as an administrator and create a device through `POST /api/devices` (also available in FastAPI `/docs`):

```json
{
  "id": "pi-track-a-01",
  "name": "Track A Raspberry Pi",
  "platform": "Raspberry Pi 4",
  "city": "bengaluru"
}
```

Send the resulting device ID with sensor readings. The simulator lists registered devices for administrators.

## 3. Send the decision inputs

`POST /api/integrations/sensors/readings` with header `X-Sensor-API-Key: <SENSOR_INGEST_TOKEN>` and JSON body:

```json
{
  "device_id": "pi-track-a-01",
  "readings": [
    {"name": "simulation_state", "value": {
      "track_A_defect": "NONE",
      "track_B_defect": "S2",
      "track_A_occupied": false,
      "track_B_occupied": false,
      "switch_A_available": true,
      "switch_B_available": true,
      "distance_to_switch_A": 80,
      "distance_to_switch_B": 120,
      "delay_score": 0.8
    }, "status": "OK", "recorded_at": "2026-10-21T10:00:00Z"}
  ]
}
```

Alternatively, send one reading per named input using those exact field names. Defect values are `NONE`, `S1`, `S2`, or `S3`; distances are meters; occupancy and switch availability are booleans. `delay_score` is optional and is clamped to 0–1. Each reading may include an ISO-8601 `recorded_at` timestamp; when omitted, the API records the server's current UTC time.

The simulator ignores readings older than 90 seconds and only calculates a decision after all eight required fields arrive fresh. It shows which fields are missing when telemetry is incomplete. The scenario mode remains available for local demos.

The Raspberry Pi needs network access to the backend URL. For local testing, start Uvicorn with `--host 0.0.0.0` so it accepts LAN connections, allow port 8000 through the development computer's firewall, and use that computer's LAN IP instead of `localhost`. For a hosted deployment, use the deployed HTTPS API URL. The integration key is a shared device-ingestion secret, so rotate it if the Raspberry Pi is lost or compromised.
