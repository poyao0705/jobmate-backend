#!/usr/bin/env python3
"""
Flask application entry point for development and production.
This file serves as the main entry point for the Flask application.
"""

from jobmate_agent.app import create_app


# Create the Flask application instance
app = create_app()



if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=5000)
