# Ham Radio Conditions

A real-time ham radio propagation forecasting and monitoring Progressive Web App (PWA). Monitors solar weather, calculates Maximum Usable Frequency (MUF), assesses HF band conditions, aggregates live spots, and shows contest schedules.

![Python](https://img.shields.io/badge/python-3.9+-blue) ![Flask](https://img.shields.io/badge/flask-2.3-green) ![Docker](https://img.shields.io/badge/docker-ready-blue)

## Features

- **Propagation Conditions** — Real-time SFI, A/K-index, MUF calculation from GIRO ionosonde data, per-band quality ratings (Excellent → Poor) with day/night assessments
- **Live Spots** — Aggregated spots from PSKReporter, Reverse Beacon Network, and WSPRNet
- **Contest Calendar** — Today / This Week / Upcoming contests with mode badges and live countdowns
- **POTA/SOTA Activations** — Active park and summit activations from api.pota.app and SOTA
- **Solar Cycle** — Current cycle position and trend
- **Local Weather** — Conditions via OpenWeather API
- **PWA** — Installable on mobile/desktop, works offline with cached data

## Quick Start

### Requirements

- Python 3.9+
- An [OpenWeather API key](https://openweathermap.org/api) (free tier is sufficient)

### Setup

```bash
# Clone and create a virtual environment
git clone https://github.com/yourname/ham-radio-conditions.git
cd ham-radio-conditions
python -m venv venv
source venv/bin/activate   # Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Create and populate the .env file
python create_env_template.py
# Edit .env and fill in OPENWEATHER_API_KEY and ZIP_CODE

# Run the development server
python wsgi_dev.py
```

Open [http://127.0.0.1:5001](http://127.0.0.1:5001) in your browser.

### Environment Variables

| Variable | Required | Description |
|---|---|---|
| `OPENWEATHER_API_KEY` | Yes | From [openweathermap.org/api](https://openweathermap.org/api) |
| `ZIP_CODE` | Yes | 5-digit US ZIP code for local weather and solar geometry |
| `CALLSIGN` | No | Your amateur radio callsign (display only) |
| `TEMP_UNIT` | No | `F` or `C` (default: `F`) |
| `SECRET_KEY` | No | Flask secret key (auto-generated default for dev) |

Validate your `.env` at any time:

```bash
python create_env_template.py validate
```

## Docker

```bash
# Build and start
docker compose up --build

# Run in background
docker compose up -d

# Or build and run manually
docker build -t ham-radio-conditions:latest .
docker run -p 8087:8087 --env-file .env ham-radio-conditions:latest
```

The production server listens on port **8087**.

## Architecture

```
ham-radio-conditions/
├── wsgi.py                  # Production WSGI entry point (gunicorn)
├── wsgi_dev.py              # Development server (port 5001)
├── app_factory.py           # Flask app factory, blueprint registration
├── config.py                # Config classes (Dev / Prod / Testing)
├── ham_radio_conditions.py  # Core orchestrator — HamRadioConditions class
├── database.py              # SQLite setup (spots, user_preferences tables)
├── dxcc_data.py             # Static DXCC entity / grid square reference data
│
├── data_sources/            # External data fetchers
│   ├── solar_data.py        # HamQSL XML + NOAA space weather JSON
│   ├── spots_data.py        # PSKReporter, RBN, WSPRNet
│   ├── weather_data.py      # OpenWeather API
│   ├── geomagnetic_data.py  # Geomagnetic coordinate calculations
│   ├── activations_data.py  # POTA (api.pota.app) + SOTA activations
│   └── contest_data.py      # Contest calendar (OpenHamClock JSON API)
│
├── calculations/            # Signal processing and propagation math
│   ├── muf_calculator.py    # MUF from GIRO ionosonde data (prop.kc2g.com)
│   ├── propagation_calculator.py  # Band quality assessment
│   ├── band_optimizer.py    # Dynamic band recommendations
│   └── time_analyzer.py     # Day/night analysis via astral
│
├── routes/
│   ├── api.py               # All /api/* REST endpoints
│   └── pwa.py               # PWA manifest + service worker routes
│
├── utils/
│   ├── cache_manager.py     # Multi-namespace in-memory cache with TTL
│   ├── background_tasks.py  # Background refresh (conditions every 10 min)
│   └── logging_config.py    # Logging setup
│
├── validation/              # Prediction accuracy tracking (7 modules)
├── templates/index.html     # Single-page frontend (vanilla JS + Tailwind)
└── static/                  # PWA manifest, service worker, icons
```

### Data Flow

1. `HamRadioConditions.generate_report()` concurrently fetches all data sources
2. Calculations run against the raw data (MUF → band quality → recommendations)
3. Result is cached for 10 minutes; background task refreshes it automatically
4. Frontend receives initial data via Jinja template injection, then polls `/api/conditions` every 5 minutes

### API Endpoints

| Endpoint | Method | Description |
|---|---|---|
| `/api/conditions` | GET | Full propagation report |
| `/api/spots` | GET | Live spots |
| `/api/weather` | GET | Weather conditions |
| `/api/contests` | GET | Contest calendar |
| `/api/activations` | GET | POTA/SOTA activations |
| `/api/location` | GET/POST | Get or set location by ZIP code |
| `/api/cache/clear` | POST | Clear caches |
| `/api/debug/solar-conditions` | GET | Solar/MUF debug info |

## Data Sources

| Source | Data | Notes |
|---|---|---|
| [HamQSL](http://www.hamqsl.com/solar.html) | SFI, A/K-index, band conditions | XML feed |
| [NOAA Space Weather](https://www.swpc.noaa.gov/) | Geomagnetic alerts | JSON API |
| [GIRO / prop.kc2g.com](https://prop.kc2g.com/) | Ionosonde MUF measurements | JSON API |
| [PSKReporter](https://pskreporter.info/) | Digital mode spots | XML |
| [Reverse Beacon Network](https://reversebeacon.net/) | CW/RTTY spots | XML |
| [WSPRNet](https://wsprnet.org/) | WSPR spots | CSV |
| [OpenWeather](https://openweathermap.org/) | Local weather | REST API (key required) |
| [api.pota.app](https://api.pota.app/) | POTA activations | JSON API |
| [SOTA](https://api2.sota.org.uk/) | SOTA activations | JSON API |
| [OpenHamClock](https://open-hamclock-production.up.railway.app/) | Contest calendar | JSON API |

## Development Notes

- No test suite exists; the `validation/` module validates propagation prediction accuracy against real-world data
- `ham_radio_conditions_refactored.py` is a legacy file; the active orchestrator is `ham_radio_conditions.py`
- `dxcc_data.py` is large static reference data — do not regenerate it
- The frontend is a single `templates/index.html` file using vanilla JS and Tailwind CSS via CDN
- Cache namespaces: `conditions` (10 min), `spots` (2 min), `weather` (10 min), `contests` (30 min), `activations` (5 min)
