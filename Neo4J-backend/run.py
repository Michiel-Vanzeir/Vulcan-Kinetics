"""Flask entry point: `python run.py` starts the whoknows backend on 127.0.0.1:5000."""
import os

from app import create_app

app = create_app()

if __name__ == "__main__":
    # The Werkzeug debugger allows code execution from the browser, so it is opt-in only.
    app.run(host="127.0.0.1", port=5000, debug=os.getenv("FLASK_DEBUG") == "1")
