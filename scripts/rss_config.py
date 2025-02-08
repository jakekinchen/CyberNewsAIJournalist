"""
Configuration file for RSS feeds used in topic generation.
Each feed can have specific parsing rules and metadata.
"""

RSS_FEEDS = {
    'news_sources': [
        {
            'name': 'The Hacker News',
            'url': 'https://feeds.feedburner.com/TheHackersNews',
            'category': 'news',
            'priority': 1,
            'date_format': '%a, %d %b %Y %H:%M:%S %z',
            'article_selector': {
                'title': 'title',
                'link': 'link',
                'date': 'pubDate',
                'description': 'description'
            }
        }
    ],
    'vulnerability_sources': [],
    'advisory_sources': [],
    'research_sources': []
}

def get_all_feeds():
    """Get all configured RSS feeds."""
    all_feeds = []
    for category in RSS_FEEDS.values():
        all_feeds.extend(category)
    return all_feeds

def get_feeds_by_category(category):
    """Get RSS feeds for a specific category."""
    return RSS_FEEDS.get(category, [])

def get_feed_by_name(name):
    """Get a specific feed by its name."""
    for category in RSS_FEEDS.values():
        for feed in category:
            if feed['name'] == name:
                return feed
    return None 