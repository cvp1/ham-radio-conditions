#!/usr/bin/env python3
"""
Production WSGI entry point for Ham Radio Conditions app.
"""

import os
from app_factory import create_app
from config import Config

os.environ['FLASK_ENV'] = 'production'

app = create_app(Config)

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=8087) 