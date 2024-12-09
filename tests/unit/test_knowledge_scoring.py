import pytest
from datetime import datetime, timedelta

from openhands.memory.knowledge_scoring import KnowledgeScorer, QualityMetrics
from openhands.memory.global_kb import KnowledgeEntry, GlobalKnowledgeBase
from openhands.core.config import LLMConfig
from unittest.mock import MagicMock

@pytest.fixture
def scorer():
    return KnowledgeScorer()

@pytest.fixture
def llm_config():
    config = MagicMock(spec=LLMConfig)
    config.embedding_model = "local"
    return config

def test_quality_metrics_calculation():
    """Test basic quality metrics calculation."""
    metrics = QualityMetrics(
        completeness=0.8,
        reliability=0.7,
        relevance=0.9,
        freshness=0.6,
        verification=0.8,
        consistency=0.7
    )
    
    # Test with default weights
    score = metrics.calculate_total_score()
    assert 0 <= score <= 1
    
    # Test with custom weights
    custom_weights = {
        'completeness': 2.0,
        'reliability': 1.5,
        'relevance': 1.0,
        'freshness': 0.5,
        'verification': 1.0,
        'consistency': 0.5
    }
    weighted_score = metrics.calculate_total_score(custom_weights)
    assert 0 <= weighted_score <= 1

def test_api_documentation_scoring(scorer):
    """Test scoring of API documentation."""
    content = """
    GET /api/v1/users
    
    Parameters:
    - page: int (optional) - Page number
    - limit: int (optional) - Items per page
    
    Returns:
    List of user objects
    
    Example:
    GET /api/v1/users?page=1&limit=10
    """
    
    metadata = {
        'url': 'https://api.example.com/docs',
        'source': 'official_documentation',
        'timestamp': datetime.utcnow().isoformat()
    }
    
    metrics = scorer.score_knowledge(content, 'api_documentation', metadata)
    
    # API docs should score high on completeness and reliability
    assert metrics.completeness >= 0.8
    assert metrics.reliability >= 0.8
    assert metrics.freshness >= 0.9  # Recent timestamp

def test_code_pattern_scoring(scorer):
    """Test scoring of code patterns."""
    content = """
    def handle_error(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            try:
                return func(*args, **kwargs)
            except Exception as e:
                logger.error(f"Error: {e}")
                raise
        return wrapper
    """
    
    metadata = {
        'success': True,
        'executed': True,
        'has_tests': True,
        'verified_count': 3
    }
    
    metrics = scorer.score_knowledge(content, 'code_pattern', metadata)
    
    # Code pattern should score high on verification and reliability
    assert metrics.verification >= 0.8
    assert metrics.reliability >= 0.7

def test_security_pattern_scoring(scorer):
    """Test scoring of security patterns."""
    content = """
    Security Best Practice: API Authentication
    
    Risk:
    Unauthorized access to sensitive endpoints
    
    Mitigation:
    1. Use OAuth 2.0 with JWT
    2. Implement rate limiting
    3. Use HTTPS only
    
    Example:
    Authorization: Bearer <jwt_token>
    """
    
    metadata = {
        'source': 'security_audit',
        'timestamp': datetime.utcnow().isoformat(),
        'verified_count': 2
    }
    
    metrics = scorer.score_knowledge(content, 'security_patterns', metadata)
    
    # Security patterns should score high on completeness and reliability
    assert metrics.completeness >= 0.8
    assert metrics.reliability >= 0.8

@pytest.mark.asyncio
async def test_quality_based_search(llm_config):
    """Test search results ordering by quality score."""
    kb = GlobalKnowledgeBase(llm_config)
    
    # Add entries with varying quality
    high_quality_entry = KnowledgeEntry(
        content="Comprehensive API documentation with examples and best practices",
        category="api_documentation",
        source="official_docs",
        metadata={
            'url': 'https://docs.example.com',
            'verified_count': 5,
            'success': True,
            'has_tests': True
        }
    )
    
    medium_quality_entry = KnowledgeEntry(
        content="Basic API endpoint description",
        category="api_documentation",
        source="community",
        metadata={
            'verified_count': 1
        }
    )
    
    low_quality_entry = KnowledgeEntry(
        content="Quick API note",
        category="api_documentation",
        source="session_note",
        timestamp=datetime.utcnow() - timedelta(days=365)
    )
    
    # Add entries
    kb.add_entry(high_quality_entry)
    kb.add_entry(medium_quality_entry)
    kb.add_entry(low_quality_entry)
    
    # Search with quality filtering
    results = kb.search_knowledge(
        "API",
        category="api_documentation",
        min_quality=0.7,
        sort_by_quality=True
    )
    
    # Verify results
    assert len(results) >= 1
    assert results[0].quality_score >= 0.7
    if len(results) > 1:
        # Verify sorting
        assert results[0].quality_score >= results[1].quality_score

def test_freshness_scoring(scorer):
    """Test freshness score calculation."""
    base_content = "Test content"
    base_metadata = {'source': 'test'}
    
    # Test with recent content
    recent_metadata = {
        **base_metadata,
        'timestamp': datetime.utcnow().isoformat()
    }
    metrics = scorer.score_knowledge(base_content, 'api_documentation', recent_metadata)
    assert metrics.freshness >= 0.9
    
    # Test with old content
    old_metadata = {
        **base_metadata,
        'timestamp': (datetime.utcnow() - timedelta(days=400)).isoformat()
    }
    metrics = scorer.score_knowledge(base_content, 'api_documentation', old_metadata)
    assert metrics.freshness <= 0.3

def test_consistency_scoring(scorer):
    """Test consistency score calculation."""
    content = "Use HTTPS for all API endpoints"
    similar_entries = [
        {'content': "Always use HTTPS for API security"},
        {'content': "HTTPS is required for API endpoints"},
        {'content': "Totally unrelated content"}
    ]
    
    metrics = scorer.score_knowledge(
        content, 
        'security_patterns',
        {'source': 'test'},
        similar_entries
    )
    
    # Should have high consistency due to similar entries
    assert metrics.consistency >= 0.7