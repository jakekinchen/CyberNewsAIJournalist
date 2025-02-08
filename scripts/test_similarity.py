"""
Test script to demonstrate topic similarity checking.
"""

import asyncio
from topic_similarity import get_recent_topics, is_topic_unique
from datetime import datetime

async def main():
    # Get recent topics
    print("Getting topics from the last 48 hours...")
    recent_topics = await get_recent_topics()
    print(f"Found {len(recent_topics)} recent topics")
    
    # Print recent topics
    print("\nRecent topics:")
    for topic in recent_topics:
        print(f"- {topic['name']}")
    
    # Test some similar and different topics
    test_topics = [
        {
            'name': 'Critical Vulnerability Found in OpenSSL Version 3.0.4',
            'description': 'A critical vulnerability has been discovered in OpenSSL...',
            'date_published': datetime.now().isoformat(),
            'provider': 'Test',
            'category': 'vulnerabilities'
        },
        {
            'name': 'New OpenSSL Security Flaw Affects Version 3.0.4',  # Similar to first topic
            'description': 'Security researchers have identified a new flaw in OpenSSL...',
            'date_published': datetime.now().isoformat(),
            'provider': 'Test',
            'category': 'vulnerabilities'
        },
        {
            'name': 'Microsoft Releases Emergency Patch for Windows 11',  # Different topic
            'description': 'Microsoft has released an out-of-band security update...',
            'date_published': datetime.now().isoformat(),
            'provider': 'Test',
            'category': 'news'
        }
    ]
    
    # Test each topic
    print("\nTesting topic similarity:")
    for topic in test_topics:
        print(f"\nChecking topic: {topic['name']}")
        is_unique = await is_topic_unique(topic)
        print(f"Is unique: {is_unique}")

if __name__ == "__main__":
    asyncio.run(main()) 