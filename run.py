"""
run.py
------
Entry point to start the Uvicorn development server.
Usage (after `gcloud auth application-default login` and `cp .env.example .env`):
    python run.py
    # or
    uvicorn app.main:app --env-file .env --reload
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        env_file=".env",    # GCS_* settings (see .env.example); ignored if absent
        host="0.0.0.0",
        port=8000,
        reload=False,       # set True for development with auto-reload
        log_level="info",
    )
