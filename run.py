"""
run.py
------
Entry point to start the Uvicorn development server.
Usage:
    conda run -n agri python run.py
    # or
    conda run -n agri uvicorn app.main:app --reload
"""

import uvicorn

if __name__ == "__main__":
    uvicorn.run(
        "app.main:app",
        host="0.0.0.0",
        port=8000,
        reload=False,       # set True for development with auto-reload
        log_level="info",
    )
