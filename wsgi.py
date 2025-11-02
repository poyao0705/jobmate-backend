#!/usr/bin/env python3
"""
WSGI entry point for production deployment.
This file is used by WSGI servers like Gunicorn for production deployment.
"""

from jobmate_agent.app import create_app

# Create the Flask application instance
application = create_app()

if __name__ == "__main__":
    application.run()
