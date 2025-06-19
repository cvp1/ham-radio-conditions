#!/usr/bin/env python3

from datetime import datetime, timedelta
import pytz
from astral import LocationInfo
from astral.sun import sun

# St. David, AZ coordinates (from grid square DM41vv)
lat = 31.9
lon = -110.2

# Get timezone
if 31.0 <= lat <= 37.0 and -115.0 <= lon <= -109.0:
    timezone = pytz.timezone('America/Phoenix')
else:
    timezone = pytz.timezone('America/Denver')

print(f"Location: St. David, AZ ({lat}, {lon})")
print(f"Timezone: {timezone}")

# Get current time
now = datetime.now(timezone)
print(f"Current time: {now}")

# Calculate sunrise/sunset using the same logic as the fixed method
location = LocationInfo("Location", "Region", "US", lat, lon)
today = now.date()
tomorrow = today + timedelta(days=1)

# Get today's sunrise and sunset
sun_today = sun(location.observer, date=today)
sunrise_local = sun_today['sunrise'].astimezone(timezone)
sunset_today_local = sun_today['sunset'].astimezone(timezone)

# Get tomorrow's sunset
sun_tomorrow = sun(location.observer, date=tomorrow)
sunset_tomorrow_local = sun_tomorrow['sunset'].astimezone(timezone)

# Use the next sunset after now
if sunset_today_local > now:
    sunset_local = sunset_today_local
else:
    sunset_local = sunset_tomorrow_local

print(f"Sunrise: {sunrise_local}")
print(f"Sunset: {sunset_local}")
print(f"Is day: {sunrise_local <= now <= sunset_local}")

# Check if it's actually 11:20 AM
print(f"\nTime check:")
print(f"Current hour: {now.hour}")
print(f"Current minute: {now.minute}")
print(f"Is between 6 AM and 6 PM: {6 <= now.hour < 18}") 