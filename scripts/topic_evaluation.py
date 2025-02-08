from scripts.structured_models import TopicEvaluation, TopicBatchEvaluation
from scripts.gpt_utils import structured_output_gpt
from typing import List, Dict, Any
from datetime import datetime, timedelta

def evaluate_topic_batch(current_topics: List[Dict[str, Any]], recent_topics: List[Dict[str, Any]], max_topics: int = 5) -> TopicBatchEvaluation:
    """
    Evaluate a batch of potential topics against recent topics to select the most significant and unique ones.
    
    Args:
        current_topics: List of new topics to evaluate
        recent_topics: List of recent topics to check for duplicates
        max_topics: Maximum number of topics to select
        
    Returns:
        TopicBatchEvaluation containing the evaluation results
    
    Raises:
        ValueError: If evaluation fails
    """
    # Prepare the prompt with topic information
    prompt = f"""Evaluate these potential topics for a cybersecurity news site:

Current Topics to Evaluate:
{format_topics_for_prompt(current_topics)}

Recent Topics (for duplicate checking):
{format_topics_for_prompt(recent_topics)}

Please evaluate each topic's significance, relevance to cybersecurity, and check for any duplicates or similar topics in the recent topics list.
Rank them by importance and select the top {max_topics} most significant and unique topics.
"""
    
    system_prompt = """You are a cybersecurity news editor responsible for selecting the most important and unique topics for coverage.
Focus on topics that are:
1. Highly relevant to cybersecurity
2. Significant impact or importance
3. Not duplicates or too similar to recent coverage
4. Timely and newsworthy

Your response must be a valid JSON object with the following structure:
{
    "evaluated_topics": [
        {
            "topic_id": null,
            "title": "string",
            "relevance_score": 0.0,
            "significance_score": 0.0,
            "is_duplicate": false,
            "duplicate_reason": null,
            "recommended_action": "include",
            "priority_rank": 1,
            "tags": ["tag1", "tag2"],
            "suggested_tags": ["tag3", "tag4"]
        }
    ],
    "top_picks": ["title1", "title2"],
    "excluded_topics": ["title3"],
    "batch_summary": "string"
}"""

    # Get structured evaluation
    evaluation = structured_output_gpt(
        prompt=prompt,
        model_class=TopicBatchEvaluation,
        system_prompt=system_prompt
    )
    
    if evaluation is None:
        raise ValueError("Failed to evaluate topics using structured output")
    
    return evaluation

def format_topics_for_prompt(topics: List[Dict[str, Any]]) -> str:
    """Format topics into a readable string for the prompt."""
    formatted = []
    for topic in topics:
        title = topic.get('title', topic.get('name', 'Untitled'))
        desc = topic.get('description', 'No description')
        formatted.append(f"- Title: {title}\n  Description: {desc}")
    return "\n\n".join(formatted)

async def get_recent_topics(supabase, days: int = 30) -> List[Dict[str, Any]]:
    """Get topics from the last N days."""
    try:
        cutoff_date = datetime.now() - timedelta(days=days)
        response = supabase.table('topics').select('*').gte('date_published', cutoff_date.isoformat()).execute()
        return response.data if response and hasattr(response, 'data') else []
    except Exception as e:
        print(f"Error fetching recent topics: {e}")
        return []

async def filter_topics_structured(topics: List[Dict[str, Any]], supabase) -> List[Dict[str, Any]]:
    """
    Use structured output evaluation to filter and select the most significant topics.
    
    Args:
        topics: List of potential topics to evaluate
        supabase: Supabase client for fetching recent topics
        
    Returns:
        List of selected topics
    """
    try:
        # Get recent topics for duplicate checking
        recent_topics = await get_recent_topics(supabase)
        
        # Evaluate topics using structured output
        evaluation = evaluate_topic_batch(topics, recent_topics)
        
        if not evaluation:
            print("Failed to evaluate topics")
            return topics  # Fall back to original topics if evaluation fails
            
        # Filter to selected topics
        selected_topics = []
        for topic in topics:
            title = topic.get('title', topic.get('name', 'Untitled'))
            if title in evaluation.top_picks:
                # Find the evaluation for this topic
                topic_eval = next(
                    (t for t in evaluation.evaluated_topics if t.title == title),
                    None
                )
                if topic_eval:
                    # Add evaluation metadata to topic
                    topic['relevance_score'] = topic_eval.relevance_score
                    topic['significance_score'] = topic_eval.significance_score
                    topic['priority_rank'] = topic_eval.priority_rank
                    topic['suggested_tags'] = topic_eval.suggested_tags
                selected_topics.append(topic)
        
        return selected_topics
    except Exception as e:
        print(f"Error in structured filtering: {e}")
        return topics  # Fall back to original topics if there's an error 