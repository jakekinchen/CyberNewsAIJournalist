from google_cse import fetch_sources_from_google_cse

def test_google_cse():
    # Test query
    test_query = 'cybersecurity news'
    
    print('\nTesting Google CSE source fetching:')
    sources = fetch_sources_from_google_cse(test_query)
    print(f'\nFetched {len(sources)} sources:')
    for source in sources:
        print(f'\nSource: {source}')

if __name__ == '__main__':
    test_google_cse() 