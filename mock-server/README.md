# Development mock server

This Flask server is for local development only. It returns the same HTTP paths consumed by `src/services/api.js`; empty collections intentionally exercise the frontend empty states.

```powershell
python -m pip install flask
python mock-server/server.py
```

Run Vite with `VITE_API_BASE_URL=http://localhost:8000/api` in a local `.env` file. Do not use this server as a production data source.
