#!/usr/bin/env python3
"""
Development WSGI entry point for Ham Radio Conditions app.
"""

import os
from app_factory import create_app
from config import Config

os.environ['FLASK_ENV'] = 'development'

app = create_app(Config)

if __name__ == '__main__':
    app.run(debug=True, host='127.0.0.1', port=5001) 