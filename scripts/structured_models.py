from pydantic import BaseModel
from typing import List, Optional
from datetime import datetime

class TopicEvaluation(BaseModel):
    """Model for evaluating a single topic's significance and uniqueness."""
    topic_id: Optional[int]
    title: str
    relevance_score: float  # 0-1 score of relevance to cybersecurity
    significance_score: float  # 0-1 score of topic significance
    is_duplicate: bool
    duplicate_reason: Optional[str]
    recommended_action: str  # "include" or "exclude"
    priority_rank: Optional[int]  # Relative rank among other topics
    tags: List[str]  # Suggested tags for categorization
    suggested_tags: List[str]  # Additional suggested tags for the topic

class TopicBatchEvaluation(BaseModel):
    """Model for evaluating a batch of topics."""
    evaluated_topics: List[TopicEvaluation]
    top_picks: List[str]  # Titles of the most significant topics
    excluded_topics: List[str]  # Titles of topics that should be excluded
    batch_summary: str  # Summary of the evaluation results 