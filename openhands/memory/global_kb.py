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

class KnowledgeEntry:
    """Represents a single entry in the global knowledge base."""
    def __init__(
        self,
        content: str,
        category: str,
        source: str,
        timestamp: Optional[datetime] = None,
        version: int = 1,
        metadata: Optional[dict] = None
    ):
        self.content = content
        self.category = category  # e.g., "technology", "api", "best_practice"
        self.source = source      # e.g., "session_123", "manual_entry"
        self.timestamp = timestamp or datetime.utcnow()
        self.version = version    # incremented when entry is updated
        self.metadata = metadata or {}

    def to_dict(self) -> dict:
        return {
            "content": self.content,
            "category": self.category,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "version": self.version,
            "metadata": self.metadata
        }

    @classmethod
    def from_dict(cls, data: dict) -> "KnowledgeEntry":
        return cls(
            content=data["content"],
            category=data["category"],
            source=data["source"],
            timestamp=datetime.fromisoformat(data["timestamp"]),
            version=data["version"],
            metadata=data["metadata"]
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

    def search_knowledge(self, query: str, k: int = 5, category: Optional[str] = None) -> list[KnowledgeEntry]:
        """Search the knowledge base for relevant entries.
        
        Args:
            query: The search query
            k: Number of results to return
            category: Optional category to filter results
            
        Returns:
            list[KnowledgeEntry]: List of matching knowledge entries
        """
        retriever = self.index.as_retriever(similarity_top_k=k)
        results = retriever.retrieve(query)
        
        entries = []
        for node in results:
            try:
                entry_dict = json.loads(node.get_text())
                if category and entry_dict["category"] != category:
                    continue
                entries.append(KnowledgeEntry.from_dict(entry_dict))
            except (json.JSONDecodeError, KeyError) as e:
                logger.warning(f"Failed to parse knowledge entry: {e}")
                continue
                
        return entries

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