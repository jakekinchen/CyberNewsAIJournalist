"""
Module containing parsers for different types of feeds.
"""

import httpx
import xml.etree.ElementTree as ET
import json
import gzip
from datetime import datetime
import logging
from bs4 import BeautifulSoup
import io

logger = logging.getLogger(__name__)

async def fetch_feed_content(url, format='xml'):
    """Fetch content from a feed URL."""
    try:
        print(f"Attempting to fetch feed from {url} (format: {format})")
        async with httpx.AsyncClient(verify=False, timeout=30.0) as client:
            response = await client.get(url)
            response.raise_for_status()
            print(f"Successfully fetched feed from {url}")
            
            if format == 'json':
                if url.endswith('.gz'):
                    # Handle gzipped content
                    content = gzip.decompress(response.content)
                    return json.loads(content)
                return response.json()
            else:
                return response.text
    except httpx.HTTPError as e:
        print(f"HTTP error fetching feed from {url}: {e}")
        return None
    except Exception as e:
        print(f"Error fetching feed from {url}: {e.__class__.__name__}: {str(e)}")
        return None

def parse_rss_feed(content, feed_config):
    """Parse RSS/XML feed content."""
    try:
        # Parse XML content
        root = ET.fromstring(content)
        items = root.findall(".//item")
        
        # Get article selectors from config
        selectors = feed_config['article_selector']
        date_format = feed_config['date_format']
        
        topics = []
        for item in items:
            try:
                # Extract fields using selectors
                topic = {
                    'name': item.find(selectors['title']).text,
                    'url': item.find(selectors['link']).text,
                    'description': item.find(selectors['description']).text,
                    'date_published': item.find(selectors['date']).text,
                    'provider': feed_config['name'],
                    'category': feed_config['category'],
                    'date_accessed': datetime.now().isoformat()
                }
                topics.append(topic)
            except Exception as e:
                logger.error(f"Error parsing item from {feed_config['name']}: {e}")
                continue
                
        return topics
    except Exception as e:
        logger.error(f"Error parsing RSS feed from {feed_config['name']}: {e}")
        return []

def parse_cisa_kev(content, feed_config):
    """Parse CISA Known Exploited Vulnerabilities JSON feed."""
    try:
        vulnerabilities = content.get('vulnerabilities', [])
        topics = []
        
        for vuln in vulnerabilities:
            topic = {
                'name': f"CISA KEV: {vuln.get('vulnerabilityName')}",
                'url': f"https://www.cisa.gov/known-exploited-vulnerabilities-catalog",
                'description': (f"CVE: {vuln.get('cveID')} - "
                              f"Vendor: {vuln.get('vendorProject')} - "
                              f"Product: {vuln.get('product')} - "
                              f"Required Action: {vuln.get('requiredAction')}"),
                'date_published': vuln.get('dateAdded'),
                'provider': feed_config['name'],
                'category': feed_config['category'],
                'date_accessed': datetime.now().isoformat()
            }
            topics.append(topic)
            
        return topics
    except Exception as e:
        logger.error(f"Error parsing CISA KEV feed: {e}")
        return []

def parse_nvd_feed(content, feed_config):
    """Parse NVD JSON feed."""
    try:
        cve_items = content.get('CVE_Items', [])
        topics = []
        
        for item in cve_items:
            cve = item.get('cve', {})
            impact = item.get('impact', {})
            
            # Get CVSS v3 score if available, otherwise try v2
            cvss_data = (impact.get('baseMetricV3', {}).get('cvssV3', {}) or 
                        impact.get('baseMetricV2', {}).get('cvssV2', {}))
            
            description = cve.get('description', {}).get('description_data', [{}])[0].get('value', '')
            
            topic = {
                'name': f"CVE: {cve.get('CVE_data_meta', {}).get('ID')}",
                'url': f"https://nvd.nist.gov/vuln/detail/{cve.get('CVE_data_meta', {}).get('ID')}",
                'description': (f"{description}\n"
                              f"CVSS Score: {cvss_data.get('baseScore', 'N/A')} "
                              f"({cvss_data.get('severity', 'N/A')})"),
                'date_published': item.get('publishedDate'),
                'provider': feed_config['name'],
                'category': feed_config['category'],
                'date_accessed': datetime.now().isoformat()
            }
            topics.append(topic)
            
        return topics
    except Exception as e:
        logger.error(f"Error parsing NVD feed: {e}")
        return []

async def parse_feed(content, feed_config):
    """Parse feed content based on feed type."""
    if feed_config.get('format') == 'json':
        if feed_config['parser_type'] == 'cisa_kev':
            return parse_cisa_kev(content, feed_config)
        elif feed_config['parser_type'] == 'nvd':
            return parse_nvd_feed(content, feed_config)
    else:
        return parse_rss_feed(content, feed_config) 