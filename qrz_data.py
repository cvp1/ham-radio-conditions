#!/usr/bin/env python3
"""
Simple Working QRZ Class
Based on the exact code that worked in the debug script
"""

import requests
import xml.etree.ElementTree as ET
from urllib.parse import urlencode
import logging
from datetime import datetime, timedelta
import time

class QRZLookup:
    def __init__(self, username, password):
        self.username = username
        self.password = password
        self.session_key = None
        self.session_expires = None
        self.base_url = "https://xmldata.qrz.com/xml/current/"
        
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.INFO)
        
        if not username or not password:
            self.logger.warning("QRZ credentials not configured")
        else:
            self.logger.info("QRZ credentials found")
    
    def _get_session_key(self):
        """Get session key using the method that actually works from debug script"""
        try:
            # Check if we have a valid session key
            if self.session_key and self.session_expires and datetime.now() < self.session_expires:
                return self.session_key
            
            params = {
                'username': self.username,
                'password': self.password,
                'agent': 'working-qrz-lookup'
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ HTTP Error: {response.status_code}")
                return None
            
            # Parse XML
            root = ET.fromstring(response.text)
            
            # Use the method that works - iterate through children
            session = None
            for child in root:
                if 'Session' in child.tag:
                    session = child
                    break
            
            if session is None:
                print(f"❌ No session element found")
                return None
            
            # Check for errors first - be more specific about what constitutes an error
            for child in session:
                tag_name = child.tag.split('}')[-1].lower()  # Remove namespace and lowercase
                if tag_name in ['error', 'e'] and child.text:  # Only actual error tags
                    print(f"❌ QRZ Error: {child.text}")
                    return None
            
            # Find the key using iteration
            key_elem = None
            for child in session:
                if 'Key' in child.tag:
                    key_elem = child
                    break
            
            if key_elem is None or not key_elem.text:
                print(f"❌ No session key found")
                # Debug: show what we did find
                print(f"Session children found:")
                for child in session:
                    print(f"  {child.tag}: {child.text}")
                return None
            
            self.session_key = key_elem.text
            self.session_expires = datetime.now() + timedelta(hours=23)
            
            print(f"✅ Got session key: {self.session_key[:15]}...")
            
            # Log subscription info
            for child in session:
                if 'SubExp' in child.tag and child.text:
                    print(f"📅 Subscription expires: {child.text}")
                elif 'Count' in child.tag and child.text:
                    print(f"📊 Lookups remaining: {child.text}")
            
            return self.session_key
            
        except Exception as e:
            print(f"❌ Error getting session: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def lookup(self, callsign):
        """Look up a callsign using the working method"""
        try:
            callsign = callsign.upper().strip()
            
            session_key = self._get_session_key()
            if not session_key:
                return None
            
            params = {
                's': session_key,
                'callsign': callsign
            }
            
            url = f"{self.base_url}?{urlencode(params)}"
            response = requests.get(url, timeout=10)
            
            if response.status_code != 200:
                print(f"❌ Lookup HTTP Error: {response.status_code}")
                return None
            
            root = ET.fromstring(response.text)
            
            # Check for session errors first
            session = None
            for child in root:
                if 'Session' in child.tag:
                    session = child
                    break
            
            if session is not None:
                for child in session:
                    tag_name = child.tag.split('}')[-1].lower()  # Remove namespace and lowercase
                    if tag_name in ['error', 'e'] and child.text:  # Only actual error tags
                        if 'Session Timeout' in child.text or 'Invalid session key' in child.text:
                            print("⚠️ Session expired, retrying...")
                            self.session_key = None
                            time.sleep(1)
                            return self.lookup(callsign)  # Retry once
                        elif 'Not found' in child.text:
                            print(f"ℹ️ Callsign {callsign} not found")
                            return None
                        else:
                            print(f"❌ QRZ API error: {child.text}")
                            return None
            
            # Find callsign element using iteration
            callsign_elem = None
            for child in root:
                if 'Callsign' in child.tag:
                    callsign_elem = child
                    break
            
            if callsign_elem is None:
                print(f"❌ No callsign data found for {callsign}")
                return None
            
            # Extract data using iteration (same as debug script)
            data = {'callsign': callsign, 'source': 'QRZ'}
            for child in callsign_elem:
                tag_name = child.tag.split('}')[-1]  # Remove namespace if present
                if child.text:
                    data[tag_name] = child.text
            
            # Build formatted fields for compatibility
            fname = data.get('fname', '')
            name = data.get('name', '')
            if fname or name:
                data['full_name'] = f"{fname} {name}".strip()
            
            addr2 = data.get('addr2', '')
            state = data.get('state', '')
            location_parts = []
            if addr2:
                location_parts.append(addr2)
            if state:
                location_parts.append(state)
            data['location'] = ', '.join(location_parts)
            
            print(f"✅ Found data for {callsign}: {len(data)} fields")
            return data
            
        except Exception as e:
            print(f"❌ Lookup error for {callsign}: {e}")
            import traceback
            traceback.print_exc()
            return None
    
    def get_formatted_info(self, callsign):
        """Get formatted callsign information for display"""
        try:
            data = self.lookup(callsign)
            
            if not data:
                return f"Callsign {callsign} not found in QRZ database"
            
            # Format the information
            info = []
            info.append(f"Callsign: {data.get('callsign', 'N/A')}")
            
            # Name
            if data.get('full_name'):
                info.append(f"Name: {data.get('full_name')}")
            elif data.get('fname') or data.get('name'):
                name = f"{data.get('fname', '')} {data.get('name', '')}".strip()
                info.append(f"Name: {name}")
            
            # License class
            if data.get('class'):
                info.append(f"License Class: {data.get('class')}")
            
            # Location
            if data.get('location'):
                info.append(f"Location: {data.get('location')}")
            
            if data.get('country'):
                info.append(f"Country: {data.get('country')}")
            
            # Grid square
            if data.get('grid'):
                info.append(f"Grid Square: {data.get('grid')}")
            
            # DXCC
            if data.get('dxcc'):
                info.append(f"DXCC: {data.get('dxcc')}")
            
            # Zones
            if data.get('cqzone'):
                info.append(f"CQ Zone: {data.get('cqzone')}")
            
            if data.get('ituzone'):
                info.append(f"ITU Zone: {data.get('ituzone')}")
            
            # QSL Info
            if data.get('qslmgr'):
                info.append(f"QSL Manager: {data.get('qslmgr')}")
            
            if data.get('lotw'):
                info.append(f"LoTW: {data.get('lotw')}")
            
            if data.get('eqsl'):
                info.append(f"eQSL: {data.get('eqsl')}")
            
            # Email
            if data.get('email'):
                info.append(f"Email: {data.get('email')}")
            
            return '\n'.join(info)
            
        except Exception as e:
            print(f"❌ Error formatting info for {callsign}: {e}")
            return f"Error retrieving information for {callsign}: {str(e)}"
    
    def test_connection(self):
        """Test the QRZ connection"""
        try:
            print("🧪 Testing QRZ connection...")
            
            session_key = self._get_session_key()
            if not session_key:
                print("❌ Authentication failed")
                return False
            
            print(f"✅ Authentication successful!")
            
            # Test lookup
            print("🔍 Testing lookup with W1AW...")
            data = self.lookup('W1AW')
            
            if data:
                print("✅ Lookup successful!")
                print(f"📊 Data fields returned: {len(data)}")
                print(f"📻 Call: {data.get('call', 'N/A')}")
                print(f"👤 Name: {data.get('fname', '')} {data.get('name', '')}")
                return True
            else:
                print("❌ Lookup failed")
                return False
                
        except Exception as e:
            print(f"❌ Test failed: {e}")
            import traceback
            traceback.print_exc()
            return False
