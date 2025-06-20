"""
WSGI entry point for development.
This file exposes the Flask application instance for development servers.
"""

from app_factory import create_app_with_error_handling

# Create the application instance with development config
app = create_app_with_error_handling('development')

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001) 