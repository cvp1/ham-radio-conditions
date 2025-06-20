"""
WSGI entry point for production deployment.
This file exposes the Flask application instance for Gunicorn.
"""

from app_factory import create_app_with_error_handling

# Create the application instance
app = create_app_with_error_handling('production')

if __name__ == '__main__':
    app.run() 