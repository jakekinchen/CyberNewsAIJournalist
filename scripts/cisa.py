#Download the Json at the following url and save the attributes to the supabase table labeled exploits: https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json
import httpx
import json
import os
from supabase_utils import supabase
from bs4 import BeautifulSoup
from datetime import datetime

def get_exploits():
    # Get the JSON from CISA
    try:
        response = httpx.get("https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json")
    except:
        return
    # Convert the JSON to a Python dictionary
    exploits = json.loads(response.text)
    return exploits

def isolate_new_exploits(exploits):
    try:
        existing_exploits = supabase.table('exploits').select('cve, url').execute()
    except Exception as error:
        print(f'Failed to query existing exploits: {error}')
        return exploits
    if existing_exploits.data == None:
        return exploits
    existing_cve_ids = [exploit['cve'] for exploit in existing_exploits.data]
    new_exploits = [exploit for exploit in exploits if exploit['cveID'] not in existing_cve_ids]
    if len(new_exploits) == 0:
        return None
    # Print the amount of new exploits
    print(f"Found {len(new_exploits)} new exploits")
    return new_exploits

# New exploits: ['CVE-2023-20198', 'CVE-2023-4966']
#python_scraping_test-app-1  | Failed to insert exploits: {'code': 'PGRST204', 'details': None, 'hint': None, 'message': "Column 'knownRansomwareCampaignUse' of relation 'exploits' does not exist"}

def format_json_for_supabase(exploits, catalog_version):
    # take each object and replace each object's field names cveID, vendorProject, product, vulnerabilityName, dateAdded, shortDescription, requiredAction, dueDate, and notes to cve, vendor_project, product, vulnerability_name, date_added, short_description, required_action, due_date, and notes respectively
    # also for each object, add field url that is the string https://nvd.nist.gov/vuln/detail/ + the cve field
    # then add the field 'source' to each object and it sbould contain the value 'cisa'
    # then add the field 'catalog_version' to each object
    # then return the array of objects
    for exploit in exploits:
        exploit['cve'] = exploit.pop('cveID')
        exploit['known_ransomware_campaign_use'] = exploit.pop('knownRansomwareCampaignUse')
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

def get_list_of_supabase_exploits():
    try:
        response = supabase.table('exploits').select('cve').execute()
        print("Successfully queried exploits")
    except Exception as error:
        print(f'Failed to query exploits: {error}')
        return []
    if response.data == None:
        return []
    return [exploit['cve'] for exploit in response.data]

def insert_or_update_exploits(exploits):
    existing_cve_ids = get_list_of_supabase_exploits()
    #Check if the exploits already exist in Supabase
    #If they do, update them as a group
    #If they don't, insert them as a group
    exploits_to_insert = []
    exploits_to_update = []
    for exploit in exploits:
        if exploit['cve'] in existing_cve_ids:
            exploits_to_update.append(exploit)
        else:
            exploits_to_insert.append(exploit)
    print(f"Amount of existing exploits: {len(existing_cve_ids)}")
    print(f"New exploits: {[exploit['cve'] for exploit in exploits]}")
    if exploits_to_insert:
        try:
            supabase.table('exploits').insert(exploits_to_insert).execute()
            print("Successfully inserted exploits")
        except Exception as error:
            if error.code == 'PGRST204':
                print(f"Failed to insert exploits because {error.message}")
                print(f"Here is what we tried to insert{exploits_to_insert}")
                print("There may be a new column in the exploits table that needs to be added to the Supabase table")
                return
            print(f'Failed to insert exploits: {error}')
            return
    if exploits_to_update:
        try: 
            supabase.table('exploits').update(exploits_to_update).execute()
            print("Successfully updated exploits")
        except Exception as error:
            print(f'Failed to update exploits: {error}')
            return

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
    # Remove the outer parent object and isolate the child objects within vulnerabilities
    exploits = exploits['vulnerabilities']
    # Isolate the new exploits
    new_exploits = isolate_new_exploits(exploits)
    if new_exploits is None:
        print("No new exploits found")
        return True
    print("Isolated new exploits")
    # Format the new exploits for Supabase
    formatted_exploits = format_json_for_supabase(new_exploits, catalog_version)
    print("Formatted new exploits for Supabase")
    # Insert the exploits into Supabase
    try:
        insert_or_update_exploits(formatted_exploits)
        return True
    except Exception as error:
        print(f'Failed to insert new exploits: {error}')
        return False

def add_hyperlinks(url):
    # children of the class tag <td data-testid="vuln-hyperlinks-link-2"> are the hyperlinks
    try:
        response = httpx.get(url)
    except Exception as error:
        print(f'Failed to get response from {url}: {error}')
        return
    html = response.text
    if html is None:
        print(f'Failed to get html from {url}')
        return
    #else:
        #print(f'Successfully got html from {url}')
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
