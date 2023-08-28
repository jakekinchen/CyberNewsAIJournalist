#Download the Json at the following url and save the attributes to the supabase table labeled exploits: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
import requests
import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv

supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase = create_client(supabase_url, supabase_key)

def get_exploits():
    # Get the JSON from CISA
    try:
        response = requests.get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    except:
        return
    # Convert the JSON to a Python dictionary
    exploits = json.loads(response.text)
    return exploits

def isolate_new_exploits(exploits):
    try:
        existing_exploits = supabase.table('exploits').select('cve, url').execute()
        print("Successfully queried existing exploits")
    except Exception as error:
        print(f'Failed to query existing exploits: {error}')
        return exploits
    if existing_exploits.data == None:
        return exploits
    existing_cve_ids = [exploit['cve'] for exploit in existing_exploits.data]
    existing_urls = [exploit['url'] for exploit in existing_exploits.data]
    new_exploits = [exploit for exploit in exploits if exploit['cveID'] not in existing_cve_ids and f"https://nvd.nist.gov/vuln/detail/{exploit['cveID']}" not in existing_urls]
    return new_exploits

def format_json_for_supabase(exploits, catalog_version):
    # take each object and replace each object's field names cveID, vendorProject, product, vulnerabilityName, dateAdded, shortDescription, requiredAction, dueDate, and notes to cve, vendor_project, product, vulnerability_name, date_added, short_description, required_action, due_date, and notes respectively
    # also for each object, add field url that is the string https://nvd.nist.gov/vuln/detail/ + the cve field
    # then add the field 'source' to each object and it sbould contain the value 'cisa'
    # then add the field 'catalog_version' to each object
    # then return the array of objects
    for exploit in exploits:
        exploit['cve'] = exploit.pop('cveID')
        exploit['vendor_project'] = exploit.pop('vendorProject')
        exploit['vulnerability_name'] = exploit.pop('vulnerabilityName')
        exploit['date_added'] = exploit.pop('dateAdded')
        exploit['short_description'] = exploit.pop('shortDescription')
        exploit['required_action'] = exploit.pop('requiredAction')
        exploit['due_date'] = exploit.pop('dueDate')
        exploit['notes'] = exploit.pop('notes')
        exploit['url'] = 'https://nvd.nist.gov/vuln/detail/' + exploit['cve']
        exploit['source'] = 'cisa'
        exploit['catalog_version'] = catalog_version
    return exploits

def insert_new_exploits(exploits):
    # Insert the new exploits into Supabase
    try:
        supabase.table('exploits').insert(exploits).execute()
        print("Successfully inserted new exploits.")
    except Exception as error:
        print(f'Failed to insert new exploits: {error}')

async def get_cisa_exploits():
    # Get the exploits from CISA
    exploits = get_exploits()
    #if exploits is null then return an error
    if exploits is None:
        print("Failed to get exploits from CISA")
        return False
    #Copy the catalogVersion field value
    catalog_version = exploits['catalogVersion']
    #Format into a date 2023-08-24 the catalog version whose value format is as follows: 2023.08.24
    catalog_version = catalog_version.replace('.', '-')
    # Remove the outer parent object and isolate the child objects within vulnerabilities
    exploits = exploits['vulnerabilities']
    # Isolate the new exploits
    new_exploits = isolate_new_exploits(exploits)
    # Format the new exploits for Supabase
    formatted_exploits = format_json_for_supabase(new_exploits, catalog_version)
    # Insert the exploits into Supabase
    try:
        insert_new_exploits(formatted_exploits)
        return True
    except Exception as error:
        print(f'Failed to insert new exploits: {error}')
        return False
    
    try: 
        response = supabase.table('exploits').select('*').execute()
        print("Successfully queried exploits")
    except Exception as error:
        print(f'Failed to query exploits: {error}')
        return False

def add_hyperlinks(url):
    """ Scrape hyperlinks from a tags in the href value that are children of the class tag <td data-testid="vuln-hyperlinks-link-2"> """
    try:
        response = requests.get(url)
    except Exception as error:
        print(f'Failed to get response from {url}: {error}')
        return
    html = response.text
    soup = BeautifulSoup(html, 'html.parser')
    links = soup.select('td[data-testid="vuln-hyperlinks-link-2"] a')
    links = [link['href'] for link in links]
    return links