"""
Run script for FastAPI application.
Use: python run_fastapi.py
Or with uvicorn directly: uvicorn jobmate_agent.app_fastapi:app --reload
"""
import uvicorn
import logging
from pathlib import Path

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

if __name__ == "__main__":
    try:
        # Ensure instance directory exists
        Path("instance").mkdir(parents=True, exist_ok=True)
        
        logger.info("Starting FastAPI server on http://127.0.0.1:5000")
        
        uvicorn.run(
            "jobmate_agent.app_fastapi:app",
            host="127.0.0.1",
            port=5000,
            reload=True,
            log_level="info"
        )
    except Exception as e:
        logger.error(f"Error starting FastAPI app: {e}")
        import traceback
        logger.error(traceback.format_exc())
