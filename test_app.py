#!/usr/bin/env python3
"""
Simple test to verify the refactored application works correctly.
"""

import os
import sys
import tempfile
import shutil
from unittest.mock import patch

def test_app_creation():
    """Test that the application can be created without errors."""
    try:
        # Set up temporary environment
        with tempfile.TemporaryDirectory() as temp_dir:
            # Create minimal .env file for testing
            env_content = """
OPENWEATHER_API_KEY=test_key
ZIP_CODE=12345
QRZ_USERNAME=test_user
QRZ_PASSWORD=test_pass
FLASK_ENV=testing
            """.strip()
            
            env_file = os.path.join(temp_dir, '.env')
            with open(env_file, 'w') as f:
                f.write(env_content)
            
            # Change to temp directory and copy necessary files
            original_cwd = os.getcwd()
            os.chdir(temp_dir)
            
            # Mock the environment
            with patch.dict(os.environ, {
                'OPENWEATHER_API_KEY': 'test_key',
                'ZIP_CODE': '12345',
                'QRZ_USERNAME': 'test_user',
                'QRZ_PASSWORD': 'test_pass',
                'FLASK_ENV': 'testing'
            }):
                # Try to import and create the app
                from app_factory import create_app
                
                # Create the app
                app = create_app('testing')
                
                # Basic checks
                assert app is not None
                assert hasattr(app, 'config')
                assert app.config['TESTING'] is True
                
                print("✅ Application creation test passed!")
                return True
                
    except Exception as e:
        print(f"❌ Application creation test failed: {e}")
        return False

def test_config_loading():
    """Test that configuration can be loaded correctly."""
    try:
        from config import get_config
        
        # Test getting default config
        config = get_config()
        assert config is not None
        assert hasattr(config, 'DEBUG')
        assert hasattr(config, 'PORT')
        
        print("✅ Configuration loading test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Configuration loading test failed: {e}")
        return False

def test_logging_setup():
    """Test that logging can be set up correctly."""
    try:
        from utils.logging_config import get_logger
        
        # Test getting a logger
        logger = get_logger('test')
        assert logger is not None
        assert hasattr(logger, 'info')
        assert hasattr(logger, 'error')
        
        print("✅ Logging setup test passed!")
        return True
        
    except Exception as e:
        print(f"❌ Logging setup test failed: {e}")
        return False

def main():
    """Run all tests."""
    print("Running refactoring tests...")
    print("=" * 50)
    
    tests = [
        test_config_loading,
        test_logging_setup,
        test_app_creation,
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
        print("🎉 All tests passed! Refactoring appears successful.")
        return 0
    else:
        print("⚠️  Some tests failed. Please check the errors above.")
        return 1

if __name__ == '__main__':
    sys.exit(main()) 