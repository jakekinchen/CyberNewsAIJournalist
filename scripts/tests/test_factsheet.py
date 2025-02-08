import asyncio
import os
import sys
from unittest.mock import patch, AsyncMock, MagicMock

# Mock the extract_text module before importing source_fetcher
sys.modules['extract_text'] = MagicMock()
sys.modules['extract_text'].scrape_content = AsyncMock()

# Mock the supabase module
mock_supabase = MagicMock()
mock_supabase.table = MagicMock()
mock_supabase.table.return_value.update = MagicMock()
mock_supabase.table.return_value.update.return_value.eq = MagicMock()
mock_supabase.table.return_value.update.return_value.eq.return_value.execute = MagicMock()
sys.modules['supabase_utils'] = MagicMock()
sys.modules['supabase_utils'].supabase = mock_supabase

from source_fetcher import create_factsheet, create_factsheets_for_sources, get_related_sources, aggregate_factsheets, update_external_source_info
from dotenv import load_dotenv
import logging
import pytest

# Set up logging
logging.basicConfig(level=logging.DEBUG)

# Load environment variables
load_dotenv()

@pytest.mark.asyncio
async def test_single_factsheet():
    """Test creating a factsheet for a single source"""
    try:
        # Create a test source
        test_source = {
            'id': 1,
            'topic_id': 123,
            'content': """As many as 768 vulnerabilities with designated CVE identifiers were reported as exploited in the wild in 2024, up from 639 CVEs in 2023, registering a 20% increase year-over-year. VulnCheck said 23.6% of known exploited vulnerabilities (KEV) were known to be weaponized either on or before the day their CVEs were publicly disclosed.""",
            'factsheet': None
        }
        
        logging.debug(f"OpenAI API Key present: {bool(os.getenv('OPENAI_API_KEY'))}")
        logging.debug(f"Testing factsheet creation with source ID: {test_source['id']}")
        
        # Mock query_gpt to return a test factsheet
        with patch('source_fetcher.query_gpt', return_value="Test factsheet content"):
            # Test factsheet creation
            factsheet = await create_factsheet(test_source, "CVE Exploits in 2024")
            logging.info(f"Generated factsheet: {factsheet}")
            
            # Basic assertions
            assert factsheet is not None, "Factsheet should not be None"
            assert isinstance(factsheet, str), "Factsheet should be a string"
            assert len(factsheet) > 0, "Factsheet should not be empty"
            assert factsheet == "Test factsheet content", "Factsheet content should match mock"
        
    except Exception as e:
        logging.error(f"Error during factsheet creation: {str(e)}", exc_info=True)
        raise

@pytest.mark.asyncio
async def test_create_factsheets_for_sources():
    """
    Test create_factsheets_for_sources to ensure:
    - It fetches related sources
    - It creates factsheets if missing
    - It aggregates them into a combined_factsheet
    - It updates external sources info when needed
    """

    # Define a fake topic
    mock_topic = {
        'id': 123,
        'name': 'Test Topic'
    }

    # Define fake related sources
    mock_related_sources = [
        {
            'id': 1, 
            'factsheet': None, 
            'topic_id': 123, 
            'name': 'Test Topic', 
            'external_source': False, 
            'url': 'http://source1.com', 
            'content': 'Source1 content...'
        },
        {
            'id': 2, 
            'factsheet': '{"already":"exists"}', 
            'topic_id': 123, 
            'name': 'Test Topic', 
            'external_source': False, 
            'url': 'http://source2.com', 
            'content': 'Source2 content...'
        },
        {
            'id': 3, 
            'factsheet': None, 
            'topic_id': 123, 
            'name': 'Test Topic', 
            'external_source': True,  
            'url': 'http://source3.com', 
            'content': 'External source content...'
        }
    ]

    with patch("source_fetcher.get_related_sources", return_value=mock_related_sources), \
         patch("source_fetcher.create_factsheet", new_callable=AsyncMock) as mock_create_factsheet, \
         patch("source_fetcher.aggregate_factsheets") as mock_aggregate_factsheets, \
         patch("source_fetcher.update_external_source_info") as mock_update_external_source_info:

        # Mock create_factsheet behavior
        async def create_factsheet_side_effect(source, topic_name):
            if source['id'] == 1:
                return "factsheet1"
            elif source['id'] == 3:
                return "factsheet3"
            return None

        mock_create_factsheet.side_effect = create_factsheet_side_effect
        mock_aggregate_factsheets.return_value = "aggregated_facts"

        # Run the method under test
        combined_factsheet, external_info = await create_factsheets_for_sources(mock_topic)

        # Assertions
        assert combined_factsheet == "aggregated_facts", "Combined factsheet should match aggregator output"
        
        assert external_info is not None, "External info should not be None"
        assert len(external_info) == 1, "Should have one external source"
        assert external_info[0]["factsheet"] == "factsheet3", "External factsheet should match"
        
        mock_aggregate_factsheets.assert_called_once_with(mock_topic, 'factsheet1{"already":"exists"}')

        mock_update_external_source_info.assert_called_once()
        topic_id_arg, external_info_arg = mock_update_external_source_info.call_args[0]
        assert topic_id_arg == 123, "Topic ID should match"
        assert len(external_info_arg) == 1, "Should have one external source info"
        assert external_info_arg[0]["id"] == 3, "External source ID should match"

        assert mock_create_factsheet.await_count == 2, "Should create factsheets for two sources"

if __name__ == "__main__":
    asyncio.run(test_single_factsheet()) 