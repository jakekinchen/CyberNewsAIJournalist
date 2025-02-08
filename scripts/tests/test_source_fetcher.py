from source_fetcher import fetch_sources_from_query

def test_source_fetching():
    # Test query
    test_query = 'cybersecurity news'
    
    print('\nTesting Google CSE source fetching:')
    sources = fetch_sources_from_query(test_query, strategy='google_cse')
    print(f'\nFetched {len(sources)} sources using Google CSE:')
    for source in sources:
        print(f'\nSource: {source}')
        
    print('\nTesting Bing source fetching:')
    sources = fetch_sources_from_query(test_query, strategy='bing')
    print(f'\nFetched {len(sources)} sources using Bing:')
    for source in sources:
        print(f'\nSource: {source}')

if __name__ == '__main__':
    test_source_fetching() 