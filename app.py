"""
Main application entry point for Ham Radio Conditions.
Uses the development WSGI for local development.
"""

from wsgi_dev import app

if __name__ == '__main__':
    app.run() 