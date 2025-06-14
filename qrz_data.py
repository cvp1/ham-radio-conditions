import requests
from bs4 import BeautifulSoup
import logging
import os
from dotenv import load_dotenv
import xml.etree.ElementTree as ET
from datetime import datetime

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)

class QRZData:
    def __init__(self):
        self.logger = logging.getLogger(__name__)
        self.logger.setLevel(logging.DEBUG)
        
        # Get QRZ credentials from environment variables
        self.api_key = os.getenv('QRZ_API_KEY')
        self.base_url = "https://xmldata.qrz.com/xml/current"
        
        if not self.api_key:
            self.logger.warning("QRZ API key not found in environment variables")
    
    def get_operator_info(self, callsign):
        """Get operator information using QRZ API"""
        try:
            if not self.api_key:
                self.logger.error("QRZ API key not configured")
                return None
            
            self.logger.info(f"Looking up callsign {callsign} using QRZ API")
            
            # Make request to QRZ XML API
            params = {
                'KEY': self.api_key,
                'ACTION': 'LOOKUP',
                'CALLSIGN': callsign
            }
            
            response = requests.get(self.base_url, params=params)
            self.logger.debug(f"API response status code: {response.status_code}")
            
            if response.status_code == 200:
                # Parse XML response
                soup = BeautifulSoup(response.text, 'xml')
                
                # Check for errors
                error = soup.find('Error')
                if error:
                    self.logger.error(f"QRZ API error: {error.text}")
                    return None
                
                # Extract operator data
                data = {
                    'callsign': callsign,
                    'name': '',
                    'last_name': '',
                    'email': '',
                    'url': '',
                    'license_class': '',
                    'license_expires': '',
                    'grid': '',
                    'bio': '',
                    'image': '',
                    'address': {
                        'street': '',
                        'city': '',
                        'state': '',
                        'country': ''
                    }
                }
                
                # Extract data from XML
                session = soup.find('Session')
                if session:
                    # Basic info
                    data['name'] = session.find('fname').text if session.find('fname') else ''
                    data['last_name'] = session.find('name').text if session.find('name') else ''
                    data['email'] = session.find('email').text if session.find('email') else ''
                    data['url'] = session.find('url').text if session.find('url') else ''
                    
                    # License info
                    data['license_class'] = session.find('class').text if session.find('class') else ''
                    data['license_expires'] = session.find('expires').text if session.find('expires') else ''
                    
                    # Location info
                    data['grid'] = session.find('grid').text if session.find('grid') else ''
                    
                    # Address
                    addr = session.find('addr1')
                    if addr:
                        data['address']['street'] = addr.text
                    city = session.find('addr2')
                    if city:
                        data['address']['city'] = city.text
                    state = session.find('state')
                    if state:
                        data['address']['state'] = state.text
                    country = session.find('country')
                    if country:
                        data['address']['country'] = country.text
                    
                    # Additional info
                    data['bio'] = session.find('bio').text if session.find('bio') else ''
                    data['image'] = session.find('image').text if session.find('image') else ''
                
                self.logger.info(f"Successfully retrieved data for {callsign}")
                return data
            
            self.logger.error(f"Failed to get operator info for {callsign} - Status code: {response.status_code}")
            return None
            
        except Exception as e:
            self.logger.error(f"Error getting operator info: {str(e)}", exc_info=True)
            return None 