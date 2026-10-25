# AMRIN ML event ingestion contract

This endpoint records detections from a separately operated ML service. It does not run a model, control signals, or issue commands to railway hardware.

## Authentication and transport

Configure `ML_INGEST_TOKEN` in `backend/.env` and restart the API. Use a high-entropy secret over HTTPS and send it in `X-ML-API-Key`. The endpoint returns `503` when the token is not configured and `401` for a missing or invalid token. This token is separate from user JWTs and must never be placed in a `VITE_` variable or browser code.

Request: `POST /api/integrations/ml/events`, JSON content type, maximum request size follows backend `MAX_CONTENT_LENGTH` (10 MiB by default). The accepted version is `schema_version: "1.0"`. Unknown fields are rejected. Image URLs and embedded base64 images are not accepted; the sender can keep evidence in its own authenticated object store until a separately designed upload contract is available.

## Version 1 payload

Required fields: `schema_version`, `source_event_id`, `detected_at`, `source`, `device_id`, `defect`, `severity`, `confidence`, `latitude`, and `longitude`. `detected_at` must be ISO 8601 with an explicit UTC offset. `device_id` must identify a registered AMRIN device.

| Field | Type and constraints |
| --- | --- |
| `source_event_id` | Nonblank string, at most 160 characters; unique per source and device |
| `source` | Nonblank service/producer name, at most 80 characters |
| `device_id` | Registered device identifier, at most 64 characters |
| `defect` | Nonblank class/defect name, at most 120 characters |
| `severity` | `S1`, `S2`, or `S3` |
| `confidence` | Number from 0 through 1 |
| `latitude`, `longitude` | WGS84 decimal degrees, respectively -90..90 and -180..180 |
| `gps_accuracy_m` | Optional number from 0 through 100000 |
| `track`, `chainage`, `city` | Optional strings, at most 80 characters |
| `boxes` | Optional list of at most 100 JSON objects, normalized model coordinates/metadata |
| `sensor_fusion` | Optional JSON object with supporting readings/fusion evidence |
| `model_version` | Optional string, at most 120 characters |
| `inference_ms` | Optional measured number from 0 through 600000; omit if not measured |

Example request (replace the placeholder with the service secret; never use a real token in shared logs):

```json
{
  "schema_version": "1.0",
  "source_event_id": "camera-2026-10-20-0042",
  "detected_at": "2026-10-20T10:30:00Z",
  "source": "rail-vision-v1",
  "device_id": "device-01",
  "defect": "rail_crack",
  "severity": "S2",
  "confidence": 0.94,
  "latitude": 12.9716,
  "longitude": 77.5946,
  "gps_accuracy_m": 2.5,
  "track": "Track A",
  "chainage": "KM 12/4",
  "boxes": [{"x": 0.1, "y": 0.2, "width": 0.3, "height": 0.2}],
  "sensor_fusion": {"vibration": "elevated"},
  "model_version": "vision-1.2",
  "inference_ms": 21.4
}
```

```powershell
curl.exe -X POST http://localhost:8000/api/integrations/ml/events `
  -H "Content-Type: application/json" `
  -H "X-ML-API-Key: <ML_INGEST_TOKEN>" `
  --data-binary "@event.json"
```

## Response and retry behavior

First accepted event returns `201`:

```json
{"event_id":"MLE-<stable-id>","alert_id":"ALT-<stable-id>","duplicate":false}
```

A repeat with the same `source`, `device_id`, and `source_event_id` returns the same IDs with `duplicate: true`. Alert, ML origin event, alert history, and event log are committed in one transaction. Distinct sources or devices may use the same source event ID. Errors use the API's `{ "error": { "code", "message" } }` envelope; malformed/out-of-range payloads return `422`, unknown device returns `422`, missing/bad key returns `401`, unconfigured ingestion returns `503`, and oversized bodies return `413`.

No image or arbitrary remote URL is fetched. Alert source is explicitly `ml_backend`; the original producer is preserved in the ML event namespace and payload. `/api/model/status` continues reporting no connected inference service because an ingested event alone is not proof of current model health.

## Verification

`backend/tests/test_ml_ingest.py` covers authorized persistence, duplicate idempotency, missing/bad/unconfigured token, invalid timestamps and numeric bounds, unknown devices, and rejection of arbitrary image URLs. Database exceptions roll back all associated rows; no independent image-upload route exists in this contract.
