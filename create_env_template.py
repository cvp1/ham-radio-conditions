#!/usr/bin/env python3
"""
Create environment template for Docker deployment.
Helps users set up the required environment variables.
"""

import os
from pathlib import Path

def create_env_template():
    """Create a .env file template with all required variables."""
    env_file = Path('.env')
    
    if env_file.exists():
        print("📝 .env file already exists")
        response = input("Do you want to overwrite it? (y/N): ")
        if response.lower() != 'y':
            print("Skipping .env file creation")
            return
    
    env_content = """# ========================================
# Ham Radio Conditions Environment Variables
# ========================================

# REQUIRED: Weather API Configuration
# Get your API key from: https://openweathermap.org/api
OPENWEATHER_API_KEY=your_openweather_api_key_here

# REQUIRED: Location Configuration
# Your ZIP code for weather and propagation data
ZIP_CODE=your_zip_code_here

# OPTIONAL: Temperature Unit (F or C)
TEMP_UNIT=F

# OPTIONAL: Ham Radio Configuration
# Your ham radio callsign (for display purposes)
CALLSIGN=your_callsign_here

# OPTIONAL: QRZ XML Database API Configuration
# Get credentials from: https://xmldata.qrz.com/
# Note: QRZ functionality is optional - app works without it
QRZ_USERNAME=your_qrz_username_here
QRZ_PASSWORD=your_qrz_password_here

# ========================================
# Flask Configuration
# ========================================

# Environment (development/production)
FLASK_ENV=production

# Secret key for Flask sessions
# Generate a secure key: python -c "import secrets; print(secrets.token_hex(32))"
SECRET_KEY=dev-secret-key-change-in-production

# Port for the application
PORT=8087

# ========================================
# Database Configuration
# ========================================

# Database file path (relative to app directory)
DATABASE_PATH=data/ham_radio.db

# How many days to keep data (default: 7)
DATA_RETENTION_DAYS=7

# ========================================
# Cache Configuration
# ========================================

# How often to update conditions cache (seconds, default: 300 = 5 minutes)
CACHE_UPDATE_INTERVAL=300

# How often to cleanup old data (seconds, default: 3600 = 1 hour)
CLEANUP_INTERVAL=3600
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Created .env file template")
        print("\n📋 Next steps:")
        print("1. Edit the .env file with your actual values")
        print("2. At minimum, set OPENWEATHER_API_KEY and ZIP_CODE")
        print("3. QRZ credentials are optional but recommended")
        print("4. Run: docker compose up --build")
        
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")

def validate_env_file():
    """Validate the current .env file."""
    env_file = Path('.env')
    
    if not env_file.exists():
        print("❌ .env file not found")
        return False
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    required_vars = ['OPENWEATHER_API_KEY', 'ZIP_CODE']
    optional_vars = ['QRZ_USERNAME', 'QRZ_PASSWORD', 'CALLSIGN']
    
    print("🔍 Validating .env file...")
    
    # Check required variables
    missing_required = []
    for var in required_vars:
        if var not in content or f'{var}=your_' in content:
            missing_required.append(var)
    
    if missing_required:
        print(f"❌ Missing required variables: {', '.join(missing_required)}")
        return False
    
    # Check optional variables
    missing_optional = []
    for var in optional_vars:
        if var not in content or f'{var}=your_' in content:
            missing_optional.append(var)
    
    if missing_optional:
        print(f"⚠️  Missing optional variables: {', '.join(missing_optional)}")
        print("   These are not required but provide additional functionality")
    
    print("✅ .env file validation passed")
    return True

def main():
    """Main function."""
    print("🔧 Environment Setup Helper")
    print("=" * 40)
    
    if len(os.sys.argv) > 1 and os.sys.argv[1] == 'validate':
        validate_env_file()
    else:
        create_env_template()
        print("\n" + "=" * 40)
        validate_env_file()

if __name__ == '__main__':
    main() 