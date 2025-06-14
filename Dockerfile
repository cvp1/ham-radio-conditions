# Use Python 3.9 slim image
FROM python:3.9-slim

# Set environment variables
ENV PYTHONUNBUFFERED=1
ENV FLASK_APP=app.py
ENV FLASK_ENV=production
ENV GRID_SQUARE=DM41vv
ENV TEMP_UNIT=F

# Set working directory
WORKDIR /app

# Copy requirements file
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code
COPY . .

# Expose port
EXPOSE 8087

# Run the application using gunicorn with optimized settings
CMD ["python", "-m", "gunicorn", "--bind", "0.0.0.0:8087", "--workers", "2", "--threads", "2", "--timeout", "30", "app:app"] 