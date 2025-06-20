#!/usr/bin/env python3
"""
Development setup script for Ham Radio Conditions app.
Helps developers set up the development environment.
"""

import os
import sys
import subprocess
from pathlib import Path

def run_command(command, description):
    """Run a command and handle errors."""
    print(f"🔄 {description}...")
    try:
        result = subprocess.run(command, shell=True, check=True, capture_output=True, text=True)
        print(f"✅ {description} completed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ {description} failed:")
        print(f"   Command: {command}")
        print(f"   Error: {e.stderr}")
        return False

def create_env_file():
    """Create a .env file with template values."""
    env_file = Path('.env')
    if env_file.exists():
        print("📝 .env file already exists, skipping creation")
        return True
    
    env_content = """# Weather API Configuration
OPENWEATHER_API_KEY=your_weather_api_key_here
ZIP_CODE=your_zip_code_here
TEMP_UNIT=F

# Ham Radio Configuration
CALLSIGN=your_callsign_here

# QRZ XML Database API Configuration
QRZ_USERNAME=your_qrz_username_here
QRZ_PASSWORD=your_qrz_password_here

# Flask Configuration
FLASK_ENV=development
SECRET_KEY=dev-secret-key-change-in-production
PORT=5001

# Database Configuration
DATABASE_PATH=data/ham_radio.db
DATA_RETENTION_DAYS=7

# Cache Configuration
CACHE_UPDATE_INTERVAL=300
CLEANUP_INTERVAL=3600
"""
    
    try:
        with open(env_file, 'w') as f:
            f.write(env_content)
        print("✅ Created .env file with template values")
        print("📝 Please edit .env file with your actual API keys and configuration")
        return True
    except Exception as e:
        print(f"❌ Failed to create .env file: {e}")
        return False

def create_directories():
    """Create necessary directories."""
    directories = ['data', 'logs', 'static/icons']
    
    for directory in directories:
        try:
            Path(directory).mkdir(parents=True, exist_ok=True)
            print(f"✅ Created directory: {directory}")
        except Exception as e:
            print(f"❌ Failed to create directory {directory}: {e}")
            return False
    
    return True

def check_python_version():
    """Check if Python version is compatible."""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 8):
        print(f"❌ Python 3.8+ required, found {version.major}.{version.minor}")
        return False
    
    print(f"✅ Python version {version.major}.{version.minor}.{version.micro} is compatible")
    return True

def install_dependencies():
    """Install Python dependencies."""
    return run_command(
        "pip install -r requirements.txt",
        "Installing Python dependencies"
    )

def run_tests():
    """Run the test suite."""
    return run_command(
        "python test_app.py",
        "Running application tests"
    )

def main():
    """Main setup function."""
    print("🚀 Setting up Ham Radio Conditions development environment")
    print("=" * 60)
    
    # Check Python version
    if not check_python_version():
        return 1
    
    # Create directories
    if not create_directories():
        return 1
    
    # Create .env file
    if not create_env_file():
        return 1
    
    # Install dependencies
    if not install_dependencies():
        return 1
    
    # Run tests
    if not run_tests():
        print("⚠️  Tests failed, but setup completed. Please check the errors above.")
    
    print("\n" + "=" * 60)
    print("🎉 Development environment setup completed!")
    print("\n📋 Next steps:")
    print("1. Edit .env file with your actual API keys and configuration")
    print("2. Run the application: python app.py")
    print("3. Open http://localhost:5001 in your browser")
    print("\n🐳 For Docker deployment:")
    print("1. Test Docker setup: python test_docker.py")
    print("2. Run with Docker: docker compose up --build")
    print("3. Open http://localhost:8087 in your browser")
    print("\n📚 For more information, see README.md")
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 