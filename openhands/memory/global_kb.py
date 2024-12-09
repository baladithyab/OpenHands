import json
from datetime import datetime
from typing import Optional

import chromadb
from llama_index.core import Document
from llama_index.core.indices.vector_store.base import VectorStoreIndex
from llama_index.core.schema import TextNode
from llama_index.vector_stores.chroma import ChromaVectorStore

from openhands.core.config import LLMConfig
from openhands.core.logger import openhands_logger as logger
from openhands.utils.embeddings import (
    LLAMA_INDEX_AVAILABLE,
    EmbeddingsLoader,
    check_llama_index,
)

from openhands.memory.knowledge_scoring import KnowledgeScorer, QualityMetrics

class KnowledgeEntry:
    """Represents a single entry in the global knowledge base."""
    def __init__(
        self,
        content: str,
        category: str,
        source: str,
        timestamp: Optional[datetime] = None,
        version: int = 1,
        metadata: Optional[dict] = None,
        quality_metrics: Optional[QualityMetrics] = None
    ):
        self.content = content
        self.category = category  # e.g., "technology", "api", "best_practice"
        self.source = source      # e.g., "session_123", "manual_entry"
        self.timestamp = timestamp or datetime.utcnow()
        self.version = version    # incremented when entry is updated
        self.metadata = metadata or {}
        self._quality_metrics = quality_metrics
        self._quality_score = None
        
    @property
    def quality_metrics(self) -> QualityMetrics:
        """Get or calculate quality metrics for this entry."""
        if self._quality_metrics is None:
            scorer = KnowledgeScorer()
            self._quality_metrics = scorer.score_knowledge(
                self.content,
                self.category,
                self.metadata
            )
        return self._quality_metrics
        
    @property
    def quality_score(self) -> float:
        """Get the overall quality score for this entry."""
        if self._quality_score is None:
            scorer = KnowledgeScorer()
            weights = scorer.get_category_weights(self.category)
            self._quality_score = self.quality_metrics.calculate_total_score(weights)
        return self._quality_score

    def to_dict(self) -> dict:
        metrics = self.quality_metrics
        return {
            "content": self.content,
            "category": self.category,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "metadata": self.metadata,
            "quality_metrics": {
                "completeness": metrics.completeness,
                "reliability": metrics.reliability,
                "relevance": metrics.relevance,
                "freshness": metrics.freshness,
                "verification": metrics.verification,
                "consistency": metrics.consistency
            },
            "quality_score": self.quality_score
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeEntry":
        # Convert quality metrics if present
        quality_metrics = None
        if "quality_metrics" in data:
            quality_metrics = QualityMetrics(
                completeness=data["quality_metrics"]["completeness"],
                reliability=data["quality_metrics"]["reliability"],
                relevance=data["quality_metrics"]["relevance"],
                freshness=data["quality_metrics"]["freshness"],
                verification=data["quality_metrics"]["verification"],
                consistency=data["quality_metrics"]["consistency"]
            )
            
        return cls(
            content=data["content"],
            category=data["category"],
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=data["version"],
            metadata=data["metadata"],
            quality_metrics=quality_metrics
        )

class GlobalKnowledgeBase:
    """A persistent knowledge base that can be accessed across sessions."""

    def __init__(self, llm_config: LLMConfig):
        """Initialize the global knowledge base with ChromaDB."""
        check_llama_index()

        # Initialize ChromaDB client for global knowledge
        self.db = chromadb.PersistentClient(
            path="./cache/global_knowledge"
        )
        self.collection = self.db.get_or_create_collection(name="global_kb")
        
        # Set up vector store
        vector_store = ChromaVectorStore(chroma_collection=self.collection)
        
        # Initialize embedding model
        embedding_strategy = llm_config.embedding_model
        self.embed_model = EmbeddingsLoader.get_embedding_model(
            embedding_strategy, llm_config
        )
        
        # Create vector store index
        self.index = VectorStoreIndex.from_vector_store(vector_store, self.embed_model)
        
        logger.info("Global knowledge base initialized")

    def add_entry(self, entry: KnowledgeEntry) -> str:
        """Add a new knowledge entry to the global knowledge base.
        
        Returns:
            str: The document ID of the added entry
        """
        doc = Document(
            text=json.dumps(entry.to_dict()),
            extra_info={
                "category": entry.category,
                "source": entry.source,
                "version": entry.version,
                "timestamp": entry.timestamp.isoformat()
            }
        )
        
        # Create and insert node
        node = TextNode(
            text=doc.text,
            extra_info=doc.extra_info
        )
        self.index.insert_nodes([node])
        
        logger.info(f"Added knowledge entry: category={entry.category}, source={entry.source}")
        return node.doc_id

    def search_knowledge(
        self, 
        query: str, 
        k: int = 5, 
        category: Optional[str] = None,
        min_quality: float = 0.0,
        sort_by_quality: bool = True
    ) -> list[KnowledgeEntry]:
        """Search the knowledge base for relevant entries.
        
        Args:
            query: The search query
            k: Number of results to return
            category: Optional category to filter results
            min_quality: Minimum quality score (0-1) for results
            sort_by_quality: Whether to sort results by quality score
            
        Returns:
            list[KnowledgeEntry]: List of matching knowledge entries
        """
        # Retrieve more results than needed to allow for quality filtering
        retriever = self.index.as_retriever(similarity_top_k=k * 2)
        results = retriever.retrieve(query)
        
        entries = []
        for node in results:
            try:
                entry_dict = json.loads(node.get_text())
                if category and entry_dict["category"] != category:
                    continue
                    
                entry = KnowledgeEntry.from_dict(entry_dict)
                
                # Filter by minimum quality score
                if entry.quality_score >= min_quality:
                    # Add similarity score to metadata for ranking
                    entry.metadata['similarity_score'] = getattr(node, 'score', 0.0)
                    entries.append(entry)
                    
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse knowledge entry: {e}")
                continue
        
        if sort_by_quality:
            # Sort by combined score (quality * similarity)
            entries.sort(
                key=lambda e: (
                    e.quality_score * e.metadata.get('similarity_score', 0.0)
                ),
                reverse=True
            )
        
        return entries[:k]

    def update_entry(self, doc_id: str, new_content: str) -> bool:
        """Update an existing knowledge entry with new content.
        
        Returns:
            bool: True if update was successful
        """
        try:
            # Get existing node
            node = self.index.docstore.get_node(doc_id)
            entry_dict = json.loads(node.get_text())
            
            # Create updated entry
            entry = KnowledgeEntry.from_dict(entry_dict)
            entry.content = new_content
            entry.version += 1
            entry.timestamp = datetime.utcnow()
            
            # Replace node
            new_node = TextNode(
                text=json.dumps(entry.to_dict()),
                doc_id=doc_id,
                extra_info={
                    "category": entry.category,
                    "source": entry.source,
                    "version": entry.version,
                    "timestamp": entry.timestamp.isoformat()
                }
            )
            
            # Remove old and insert new
            self.index.delete(doc_id)
            self.index.insert_nodes([new_node])
            
            logger.info(f"Updated knowledge entry {doc_id} to version {entry.version}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update knowledge entry {doc_id}: {e}")
            return False

    def get_entry(self, doc_id: str) -> Optional[KnowledgeEntry]:
        """Retrieve a specific knowledge entry by ID."""
        try:
            node = self.index.docstore.get_node(doc_id)
            entry_dict = json.loads(node.get_text())
            return KnowledgeEntry.from_dict(entry_dict)
        except Exception as e:
            logger.error(f"Failed to get knowledge entry {doc_id}: {e}")
            return None