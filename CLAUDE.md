# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Ham Radio Conditions is a real-time ham radio propagation forecasting and monitoring PWA. It calculates MUF (Maximum Usable Frequency), assesses band quality, aggregates live spots from PSKReporter/RBN/WSPRNet, and integrates solar weather and local weather data. Built with Flask (Python 3.9+), SQLite, and a single-page frontend.

## Commands

### Development
```bash
python wsgi_dev.py                  # Run dev server on http://127.0.0.1:5001
```

### Production
```bash
# Via Docker (preferred)
docker build -t ham-radio-conditions:latest .
docker compose up --build           # Build and start
docker compose up -d                # Start in background

# Direct
gunicorn --bind 0.0.0.0:8087 --workers 2 --threads 2 --timeout 30 wsgi:app
```

### Environment Setup
```bash
python create_env_template.py       # Generate .env template
python create_env_template.py validate  # Validate .env file
```

### Required Environment Variables
- `OPENWEATHER_API_KEY` - from https://openweathermap.org/api
- `ZIP_CODE` - 5-digit US ZIP code for location

## Architecture

### Application Flow
`wsgi.py` / `wsgi_dev.py` → `app_factory.create_app(Config)` → Flask app with blueprints

The app factory (`app_factory.py`) initializes: database, CORS, cache, `HamRadioConditions` service, `TaskManager` for background jobs, and registers route blueprints.

### Core Service
`ham_radio_conditions.py` - Central orchestrator class (`HamRadioConditions`). Owns all data providers and calculators, exposes methods like `generate_report()`, `get_live_activity()`, `get_weather_conditions()`. Instances are stored in `app.config['HAM_CONDITIONS']` and accessed by route handlers via `current_app.config`.

### Data Flow
1. **Data Sources** (`data_sources/`) - Fetch from external APIs:
   - `solar_data.py` - HamQSL XML feed, NOAA space weather JSON
   - `spots_data.py` - PSKReporter, Reverse Beacon Network, WSPRNet
   - `weather_data.py` - OpenWeather API
   - `geomagnetic_data.py` - Geomagnetic coordinate calculations
2. **Calculations** (`calculations/`) - Process raw data:
   - `muf_calculator.py` - MUF from ionosonde data (GIRO network via prop.kc2g.com) with formula fallback
   - `propagation_calculator.py` - Band quality assessment
   - `band_optimizer.py` - Dynamic band recommendations based on MUF, time-of-day, weather
   - `time_analyzer.py` - Day/night propagation analysis using astral (sunrise/sunset)
3. **Validation** (`validation/`) - Prediction accuracy tracking with 7 validator modules (real-time, historical, ionosonde, cross-validation, statistical analysis)

### Routes
- `routes/api.py` - All REST endpoints under `/api/` prefix (conditions, spots, weather, location, version, debug, cache)
- `routes/pwa.py` - PWA manifest and service worker routes
- `app_factory.py:register_routes()` - Root `/` route serving the main template

### Key API Endpoints
| Endpoint | Method | Description |
|---|---|---|
| `/api/conditions` | GET | Current propagation conditions |
| `/api/spots` | GET | Live activity/spots |
| `/api/weather` | GET | Weather conditions |
| `/api/location` | GET/POST | Get or update location (by ZIP code) |
| `/api/cache/clear` | POST | Clear caches (optional `cache_type` in body) |
| `/api/debug/solar-conditions` | GET | Solar/MUF debug info |

### Caching
`utils/cache_manager.py` provides a multi-namespace in-memory cache with TTL expiration and background cleanup. Namespaces: conditions (5 min), spots (2 min), weather (10 min). Background task in `utils/background_tasks.py` calls `generate_report()` every 5 minutes.

### Database
SQLite (`data/ham_radio.db`), managed by `database.py`. Two tables: `spots` (timestamped radio spot data) and `user_preferences` (key-value settings including stored ZIP code).

### Frontend
Single-page app in `templates/index.html` with PWA support (`static/sw.js`, `static/manifest.json`, `static/offline.html`). Fetches all data from `/api/*` endpoints.

### Configuration
`config.py` defines `Config`, `DevelopmentConfig`, `ProductionConfig`, `TestingConfig`. Environment selection via `FLASK_ENV`. Dev runs on port 5001, production on 8087.

### JSON Safety
Both `app_factory.py` and `ham_radio_conditions.py` contain `safe_json_serialize()` functions that convert NaN/Inf floats to `"N/A"` before sending to templates or API responses.

## Key Dependencies
- Flask + flask-caching + flask-cors + gunicorn
- pandas, numpy, scipy, scikit-learn (data processing and ML predictions)
- astral + timezonefinder (sunrise/sunset and timezone lookups)
- beautifulsoup4 + lxml (HTML/XML parsing of external feeds)
- aiohttp (async HTTP for concurrent data fetching)

## Notes
- `dxcc_data.py` contains a large static mapping of DXCC entities and grid squares - it's reference data, not generated
- `ham_radio_conditions_refactored.py` is an older version of the main service class; the active one is `ham_radio_conditions.py`
- No test suite exists currently; the `validation/` module validates prediction accuracy against real data, not unit tests
- Docker image uses `python:3.9-slim` with gcc/g++ for scipy/numpy compilation
