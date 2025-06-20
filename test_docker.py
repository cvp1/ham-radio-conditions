#!/usr/bin/env python3
"""
Test script to verify Docker configuration works correctly.
"""

import os
import sys
import subprocess
from pathlib import Path

def check_docker_installed():
    """Check if Docker is installed and running."""
    try:
        result = subprocess.run(['docker', '--version'], capture_output=True, text=True, check=True)
        print(f"✅ Docker is installed: {result.stdout.strip()}")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Docker is not installed or not accessible")
        return False

def check_docker_compose_installed():
    """Check if Docker Compose is installed."""
    try:
        # Try the new 'docker compose' command first
        result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True, check=True)
        print(f"✅ Docker Compose is installed: {result.stdout.strip()}")
        return 'docker compose'
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            # Fall back to the old 'docker-compose' command
            result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True, check=True)
            print(f"✅ Docker Compose is installed (legacy): {result.stdout.strip()}")
            return 'docker-compose'
        except (subprocess.CalledProcessError, FileNotFoundError):
            print("❌ Docker Compose is not installed or not accessible")
            return None

def check_env_file():
    """Check if .env file exists and has required variables."""
    env_file = Path('.env')
    if not env_file.exists():
        print("❌ .env file not found")
        print("   Please create a .env file with your API keys")
        return False
    
    with open(env_file, 'r') as f:
        content = f.read()
    
    required_vars = [
        'OPENWEATHER_API_KEY',
        'ZIP_CODE',
        'QRZ_USERNAME',
        'QRZ_PASSWORD'
    ]
    
    missing_vars = []
    for var in required_vars:
        if var not in content or f'{var}=your_' in content:
            missing_vars.append(var)
    
    if missing_vars:
        print(f"❌ Missing or placeholder values in .env file: {', '.join(missing_vars)}")
        return False
    
    print("✅ .env file exists and has required variables")
    return True

def test_docker_build(compose_cmd):
    """Test Docker build process."""
    print("🔄 Testing Docker build...")
    try:
        result = subprocess.run(
            compose_cmd.split() + ['build'],
            capture_output=True,
            text=True,
            check=True
        )
        print("✅ Docker build successful")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker build failed:")
        print(f"   Error: {e.stderr}")
        return False

def test_docker_run(compose_cmd):
    """Test Docker run process (brief test)."""
    print("🔄 Testing Docker run (brief test)...")
    try:
        # Start the container
        result = subprocess.run(
            compose_cmd.split() + ['up', '-d'],
            capture_output=True,
            text=True,
            check=True
        )
        
        # Wait a moment for startup
        import time
        time.sleep(10)
        
        # Check if container is running
        result = subprocess.run(
            compose_cmd.split() + ['ps'],
            capture_output=True,
            text=True,
            check=True
        )
        
        if 'Up' in result.stdout:
            print("✅ Docker container is running")
            
            # Stop the container
            subprocess.run(compose_cmd.split() + ['down'], capture_output=True)
            return True
        else:
            print("❌ Docker container failed to start properly")
            subprocess.run(compose_cmd.split() + ['down'], capture_output=True)
            return False
            
    except subprocess.CalledProcessError as e:
        print(f"❌ Docker run test failed:")
        print(f"   Error: {e.stderr}")
        # Try to clean up
        subprocess.run(compose_cmd.split() + ['down'], capture_output=True)
        return False

def main():
    """Run all Docker tests."""
    print("🐳 Testing Docker Configuration")
    print("=" * 50)
    
    # Check Docker installation
    if not check_docker_installed():
        return 1
    
    # Check Docker Compose installation
    compose_cmd = check_docker_compose_installed()
    if not compose_cmd:
        return 1
    
    tests = [
        lambda: check_env_file(),
        lambda: test_docker_build(compose_cmd),
        lambda: test_docker_run(compose_cmd),
    ]
    
    passed = 0
    total = len(tests)
    
    for test in tests:
        if test():
            passed += 1
        print()
    
    print("=" * 50)
    print(f"Tests passed: {passed}/{total}")
    
    if passed == total:
        print("🎉 All Docker tests passed! Your Docker setup is ready.")
        print(f"\n📋 To run the application:")
        print(f"   {compose_cmd} up --build")
        print("   # Then visit http://localhost:8087")
    else:
        print("⚠️  Some Docker tests failed. Please check the errors above.")
        return 1
    
    return 0

if __name__ == '__main__':
    sys.exit(main()) 