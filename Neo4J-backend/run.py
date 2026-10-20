"""Flask entry point: `python run.py` starts the whoknows backend on :5000."""
from app import create_app

app = create_app()

if __name__ == "__main__":
    app.run(debug=True, port=5000)
