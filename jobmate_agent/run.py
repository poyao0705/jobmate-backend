# run.py
import logging
from jobmate_agent.app import create_app, db

logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        app = create_app()
        with app.app_context():
            db.create_all()
        logger.info("Starting Flask server on http://127.0.0.1:5000")
        app.run(debug=False, host="127.0.0.1", port=5000)
    except Exception as e:
        logger.error(f"Error starting Flask app: {e}")
        import traceback

        logger.error(traceback.format_exc())
