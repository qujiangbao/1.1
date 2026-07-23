"""Investment Agent State"""
from typing import TypedDict, List, Optional, Dict, Any


class InvestmentState(TypedDict):
    task_id: str
    intent: str
    priority: str
    input: Dict[str, Any]

    # Input
    query: str
    industry: Optional[str]
    region: Optional[str]
    keywords: Optional[List[str]]
    enterprise_ids: Optional[List[str]]

    # Results
    search_results: Optional[List[Dict]]
    profiles: Optional[List[Dict]]
    scores: Optional[List[Dict]]
    recommendations: Optional[List[Dict]]
    strategy: Optional[Dict]
    report: Optional[Dict]

    # Context from other agents
    industry_context: Optional[Dict]
    policy_context: Optional[Dict]
    risk_context: Optional[Dict]

    # Control
    status: str                     # idle/searching/profiling/scoring/done/failed
    error: Optional[Dict]
    retry_count: int

    # Trace
    tools_used: List[str]
    data_sources: List[str]
