from dataclasses import dataclass
from datetime import datetime
from typing import Dict, List, Optional

@dataclass
class QualityMetrics:
    """Metrics used to calculate knowledge quality score."""
    completeness: float = 0.0    # How complete/detailed the knowledge is (0-1)
    reliability: float = 0.0     # How reliable the source/execution is (0-1)
    relevance: float = 0.0       # How relevant/specific the knowledge is (0-1)
    freshness: float = 0.0       # How recent the knowledge is (0-1)
    verification: float = 0.0    # How well verified/tested the knowledge is (0-1)
    consistency: float = 0.0     # How consistent with other knowledge (0-1)

    def calculate_total_score(self, weights: Optional[Dict[str, float]] = None) -> float:
        """Calculate total quality score using optional weights."""
        if weights is None:
            weights = {
                'completeness': 1.0,
                'reliability': 1.0,
                'relevance': 1.0,
                'freshness': 0.8,
                'verification': 1.0,
                'consistency': 0.8
            }
        
        total_weight = sum(weights.values())
        
        score = (
            self.completeness * weights['completeness'] +
            self.reliability * weights['reliability'] +
            self.relevance * weights['relevance'] +
            self.freshness * weights['freshness'] +
            self.verification * weights['verification'] +
            self.consistency * weights['consistency']
        ) / total_weight
        
        return round(score, 3)

class KnowledgeScorer:
    """Scores knowledge quality based on various metrics."""
    
    def __init__(self):
        self.category_weights = {
            'api_documentation': {
                'completeness': 1.2,  # API docs need to be very complete
                'reliability': 1.2,   # Source reliability is crucial
                'relevance': 1.0,
                'freshness': 1.0,     # API versions matter
                'verification': 0.8,
                'consistency': 0.8
            },
            'code_pattern': {
                'completeness': 1.0,
                'reliability': 1.2,    # Code must work
                'relevance': 1.0,
                'freshness': 0.6,      # Patterns can be older
                'verification': 1.2,    # Must be verified
                'consistency': 1.0
            },
            'security_patterns': {
                'completeness': 1.0,
                'reliability': 1.4,     # Security info must be reliable
                'relevance': 1.2,
                'freshness': 1.2,       # Security needs to be current
                'verification': 1.2,
                'consistency': 1.0
            }
        }
        
        # Default weights for unknown categories
        self.default_weights = {
            'completeness': 1.0,
            'reliability': 1.0,
            'relevance': 1.0,
            'freshness': 0.8,
            'verification': 1.0,
            'consistency': 0.8
        }

    def score_knowledge(self, content: str, category: str, metadata: dict,
                       similar_entries: List[dict] = None) -> QualityMetrics:
        """Score knowledge entry based on various quality metrics."""
        metrics = QualityMetrics()
        
        # 1. Completeness Score
        metrics.completeness = self._score_completeness(content, category)
        
        # 2. Reliability Score
        metrics.reliability = self._score_reliability(content, category, metadata)
        
        # 3. Relevance Score
        metrics.relevance = self._score_relevance(content, category, metadata)
        
        # 4. Freshness Score
        metrics.freshness = self._score_freshness(metadata)
        
        # 5. Verification Score
        metrics.verification = self._score_verification(content, category, metadata)
        
        # 6. Consistency Score
        metrics.consistency = self._score_consistency(content, similar_entries)
        
        return metrics

    def _score_completeness(self, content: str, category: str) -> float:
        """Score completeness based on content analysis."""
        score = 0.0
        
        # Base score on content length and structure
        if len(content) < 50:
            score += 0.3
        elif len(content) < 200:
            score += 0.6
        else:
            score += 0.8
            
        # Category-specific checks
        if category == 'api_documentation':
            # Check for essential API doc elements
            required_elements = ['parameters', 'return', 'example']
            found_elements = sum(1 for elem in required_elements 
                               if elem in content.lower())
            score += 0.2 * (found_elements / len(required_elements))
            
        elif category == 'code_pattern':
            # Check for code pattern completeness
            if all(x in content.lower() for x in ['import', 'def', 'return']):
                score += 0.2
                
        elif category == 'security_patterns':
            # Check for security pattern completeness
            required_elements = ['risk', 'mitigation', 'example']
            found_elements = sum(1 for elem in required_elements 
                               if elem in content.lower())
            score += 0.2 * (found_elements / len(required_elements))
            
        return min(1.0, score)

    def _score_reliability(self, content: str, category: str, metadata: dict) -> float:
        """Score reliability based on source and validation."""
        score = 0.5  # Base score
        
        # Source-based scoring
        source = metadata.get('source', '').lower()
        if 'official' in source or 'documentation' in source:
            score += 0.3
        elif 'verified' in source:
            score += 0.2
            
        # Success-based scoring
        if metadata.get('success') is True:
            score += 0.2
        elif metadata.get('verified_count', 0) > 0:
            score += 0.15
            
        # URL-based scoring
        url = metadata.get('url', '').lower()
        if url:
            if any(domain in url for domain in ['.gov', '.edu', 'github.com']):
                score += 0.2
            elif 'https' in url:
                score += 0.1
                
        return min(1.0, score)

    def _score_relevance(self, content: str, category: str, metadata: dict) -> float:
        """Score relevance based on specificity and context."""
        score = 0.5  # Base score
        
        # Context matching
        context = metadata.get('context', '').lower()
        if context and context in content.lower():
            score += 0.2
            
        # Specificity scoring
        if len(content.split()) > 10:  # More detailed content
            score += 0.1
            
        # Category-specific relevance
        if category == 'code_pattern':
            if 'error' in content.lower() and 'solution' in content.lower():
                score += 0.2
        elif category == 'api_documentation':
            if all(x in content.lower() for x in ['endpoint', 'method', 'response']):
                score += 0.2
                
        return min(1.0, score)

    def _score_freshness(self, metadata: dict) -> float:
        """Score freshness based on timestamp."""
        timestamp = metadata.get('timestamp')
        if not timestamp:
            return 0.5  # Default score if no timestamp
            
        try:
            if isinstance(timestamp, str):
                entry_time = datetime.fromisoformat(timestamp)
            else:
                entry_time = timestamp
                
            # Calculate age in days
            age_days = (datetime.utcnow() - entry_time).days
            
            if age_days < 7:
                return 1.0
            elif age_days < 30:
                return 0.8
            elif age_days < 90:
                return 0.6
            elif age_days < 365:
                return 0.4
            else:
                return 0.2
                
        except (ValueError, TypeError):
            return 0.5

    def _score_verification(self, content: str, category: str, metadata: dict) -> float:
        """Score verification based on testing and validation."""
        score = 0.5  # Base score
        
        # Execution verification
        if metadata.get('executed', False):
            score += 0.2
            if metadata.get('success', False):
                score += 0.2
                
        # Multiple source verification
        verified_count = metadata.get('verified_count', 0)
        score += min(0.3, verified_count * 0.1)
        
        # Test coverage
        if metadata.get('has_tests', False):
            score += 0.2
            
        return min(1.0, score)

    def _score_consistency(self, content: str, similar_entries: List[dict] = None) -> float:
        """Score consistency with existing knowledge."""
        if not similar_entries:
            return 0.5  # Default score if no similar entries
            
        score = 0.5
        consistent_count = 0
        
        for entry in similar_entries:
            entry_content = entry.get('content', '')
            # Basic consistency check - could be enhanced with more sophisticated comparison
            if self._calculate_similarity(content, entry_content) > 0.7:
                consistent_count += 1
                
        # Score based on number of consistent entries
        score += min(0.5, consistent_count * 0.1)
        
        return min(1.0, score)

    def _calculate_similarity(self, text1: str, text2: str) -> float:
        """Calculate similarity between two texts (simple implementation)."""
        # This is a basic implementation - could be enhanced with more sophisticated
        # algorithms like cosine similarity or embedding comparison
        words1 = set(text1.lower().split())
        words2 = set(text2.lower().split())
        
        if not words1 or not words2:
            return 0.0
            
        intersection = words1.intersection(words2)
        union = words1.union(words2)
        
        return len(intersection) / len(union)

    def get_category_weights(self, category: str) -> Dict[str, float]:
        """Get scoring weights for a specific category."""
        return self.category_weights.get(category, self.default_weights)