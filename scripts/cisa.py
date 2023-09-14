#Download the Json at the following url and save the attributes to the supabase table labeled exploits: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
import requests
import json
import os
from supabase import create_client, Client
from dotenv import load_dotenv
from bs4 import BeautifulSoup

supabase_url = os.getenv('SUPABASE_ENDPOINT')
supabase_key = os.getenv('SUPABASE_KEY')
supabase: Client = create_client(supabase_url, supabase_key)

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
    new_exploits = [exploit for exploit in exploits if exploit['cveID'] not in existing_cve_ids]
    # Print the amount of new exploits
    print(f"Found {len(new_exploits)} new exploits")
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
        exploit['hyperlinks'] = add_hyperlinks(exploit['url'])
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
    # If exploits is null then return an error
    if exploits is None:
        print("Failed to get exploits from CISA")
        return False
    #Copy the catalogVersion field value
    catalog_version = exploits['catalogVersion']
    # Replace dots with dashes in the catalogVersion field value
    catalog_version = catalog_version.replace('.', '-')
     # Query the most recent catalog_version from Supabase
    try:
        most_recent_exploit = supabase.table('exploits').select('catalog_version').order('date_added', ascending=False).limit(1).execute()
        most_recent_catalog_version = most_recent_exploit.data[0]['catalog_version'] if most_recent_exploit.data else None
    except Exception as error:
        print(f'Failed to query the most recent catalog_version: {error}')
        most_recent_catalog_version = None

    # Check if the catalog version has changed
    if most_recent_catalog_version == catalog_version:
        print("Catalog version hasn't changed. Skipping CISA process.")
        return True
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

def add_hyperlinks(url):
    # children of the class tag <td data-testid="vuln-hyperlinks-link-2"> are the hyperlinks
    try:
        response = requests.get(url)
    except Exception as error:
        print(f'Failed to get response from {url}: {error}')
        return
    html = response.text
    if html is None:
        print(f'Failed to get html from {url}')
        return
    else:
        print(f'Successfully got html from {url}')
        #print(html)
    soup = BeautifulSoup(html, 'html.parser')
    # Generalize the selector to get all links under `td` elements that have a `data-testid` attribute starting with "vuln-hyperlinks-link-"
    links = soup.select('td[data-testid^="vuln-hyperlinks-link-"] a')
    # Extract href attributes from the selected links
    links = [link['href'] for link in links]
    return links

def upload_hyperlinks():
    # Find all exploits that have a source of cisa and a url that contains https://nvd.nist.gov/vuln/detail/ and empty hyperlinks array
    try:
        response = supabase.table('exploits').select('*').eq('source', 'cisa').execute()
        print("Successfully queried exploits")
    except Exception as error:
        print(f'Failed to query exploits: {error}')
        return
    exploits = response.data
    if exploits is None:
        print("No exploits found")
        return
    for exploit in exploits:
        print(f"Adding hyperlinks to exploit with cve {exploit['cve']}")
        # Get the hyperlinks
        # continue if exploit hyperlinks is not empty
        if exploit['hyperlinks']:
            print(f"Exploit with cve {exploit['cve']} already has hyperlinks")
            continue
        hyperlinks = add_hyperlinks(exploit['url'])
        if hyperlinks is None:
            print(f"Failed to get hyperlinks for exploit with cve {exploit['cve']}")
            continue
        # Update the exploit with the hyperlinks
        try:
            supabase.table('exploits').update({'hyperlinks': hyperlinks}).eq('id', exploit['id']).execute()
            print(f"Successfully updated exploit with cve {exploit['cve']}")
        except Exception as error:
            print(f'Failed to update exploit with cve {exploit["cve"]}: {error}')
            continue
    print("Successfully added hyperlinks to exploits")
