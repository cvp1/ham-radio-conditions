#!/usr/bin/env python3
"""
Docker Compose command helper script.
Provides the correct Docker Compose commands for different Docker versions.
"""

import subprocess
import sys

def detect_docker_compose_command():
    """Detect which Docker Compose command is available."""
    try:
        # Try the new 'docker compose' command first
        result = subprocess.run(['docker', 'compose', 'version'], capture_output=True, text=True, check=True)
        return 'docker compose'
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            # Fall back to the old 'docker-compose' command
            result = subprocess.run(['docker-compose', '--version'], capture_output=True, text=True, check=True)
            return 'docker-compose'
        except (subprocess.CalledProcessError, FileNotFoundError):
            return None

def print_commands():
    """Print the correct Docker Compose commands."""
    compose_cmd = detect_docker_compose_command()
    
    if not compose_cmd:
        print("❌ Docker Compose not found!")
        print("Please install Docker Compose first.")
        return
    
    print(f"🐳 Using Docker Compose command: {compose_cmd}")
    print("=" * 50)
    print("\n📋 Common Docker Compose Commands:")
    print(f"  Build and start:     {compose_cmd} up --build")
    print(f"  Start in background: {compose_cmd} up -d")
    print(f"  Stop:               {compose_cmd} down")
    print(f"  View logs:          {compose_cmd} logs")
    print(f"  View status:        {compose_cmd} ps")
    print(f"  Rebuild:            {compose_cmd} build")
    print(f"  Restart:            {compose_cmd} restart")
    
    print("\n🚀 Quick Start:")
    print(f"  1. {compose_cmd} up --build")
    print("  2. Open http://localhost:8087")
    print("  3. To stop: Ctrl+C or 'docker compose down'")
    
    print("\n🔧 Development:")
    print(f"  View logs:          {compose_cmd} logs -f")
    print(f"  Shell access:       {compose_cmd} exec ham_conditions bash")
    print(f"  Rebuild one service: {compose_cmd} build ham_conditions")

def main():
    """Main function."""
    print("🐳 Docker Compose Command Helper")
    print("=" * 50)
    
    if len(sys.argv) > 1 and sys.argv[1] == '--version':
        compose_cmd = detect_docker_compose_command()
        if compose_cmd:
            print(f"Using: {compose_cmd}")
        else:
            print("Docker Compose not found")
        return
    
    print_commands()

if __name__ == '__main__':
    main() 