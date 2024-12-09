import json
from datetime import datetime, timedelta
import pytest
from unittest.mock import MagicMock, patch

from openhands.core.config import LLMConfig
from openhands.memory.global_kb import GlobalKnowledgeBase, KnowledgeEntry
from openhands.memory.memory import LongTermMemory
from openhands.events.event import Event
from openhands.events.stream import EventStream

@pytest.fixture
def llm_config():
    config = MagicMock(spec=LLMConfig)
    config.embedding_model = "local"
    return config

@pytest.fixture
def agent_config():
    config = MagicMock()
    config.memory_max_threads = 4
    return config

@pytest.fixture
def event_stream():
    stream = MagicMock(spec=EventStream)
    stream.sid = "test_session_123"
    return stream

@pytest.fixture
def knowledge_entry():
    return KnowledgeEntry(
        content="Test content",
        category="test_category",
        source="test_source",
        timestamp=datetime.utcnow(),
        version=1,
        metadata={"test_key": "test_value"}
    )

def test_knowledge_entry_serialization(knowledge_entry):
    """Test that KnowledgeEntry can be properly serialized and deserialized."""
    # Convert to dict
    entry_dict = knowledge_entry.to_dict()
    
    # Convert back to KnowledgeEntry
    new_entry = KnowledgeEntry.from_dict(entry_dict)
    
    # Verify all attributes match
    assert new_entry.content == knowledge_entry.content
    assert new_entry.category == knowledge_entry.category
    assert new_entry.source == knowledge_entry.source
    assert new_entry.version == knowledge_entry.version
    assert new_entry.metadata == knowledge_entry.metadata
    
    # Timestamps should be within 1 second (to account for potential float precision differences)
    time_diff = abs((new_entry.timestamp - knowledge_entry.timestamp).total_seconds())
    assert time_diff < 1

@pytest.mark.asyncio
async def test_global_kb_basic_operations(llm_config):
    """Test basic operations of the GlobalKnowledgeBase."""
    kb = GlobalKnowledgeBase(llm_config)
    
    # Test adding an entry
    entry = KnowledgeEntry(
        content="Example API usage",
        category="api_documentation",
        source="test",
    )
    doc_id = kb.add_entry(entry)
    assert doc_id is not None
    
    # Test retrieving the entry
    retrieved = kb.get_entry(doc_id)
    assert retrieved is not None
    assert retrieved.content == entry.content
    assert retrieved.category == entry.category
    
    # Test updating the entry
    new_content = "Updated API usage"
    success = kb.update_entry(doc_id, new_content)
    assert success
    
    # Verify update
    updated = kb.get_entry(doc_id)
    assert updated is not None
    assert updated.content == new_content
    assert updated.version == 2  # Version should be incremented

@pytest.mark.asyncio
async def test_global_kb_search(llm_config):
    """Test search functionality of the GlobalKnowledgeBase."""
    kb = GlobalKnowledgeBase(llm_config)
    
    # Add multiple entries
    entries = [
        KnowledgeEntry(
            content="Python API for file operations",
            category="api_documentation",
            source="test"
        ),
        KnowledgeEntry(
            content="Best practices for error handling",
            category="best_practices",
            source="test"
        ),
        KnowledgeEntry(
            content="Common Python file operations",
            category="code_pattern",
            source="test"
        )
    ]
    
    for entry in entries:
        kb.add_entry(entry)
    
    # Test search
    results = kb.search_knowledge("file operations")
    assert len(results) > 0
    assert any("file operations" in r.content for r in results)
    
    # Test category filter
    api_results = kb.search_knowledge("file operations", category="api_documentation")
    assert all(r.category == "api_documentation" for r in api_results)

@pytest.mark.asyncio
async def test_memory_integration(llm_config, agent_config, event_stream):
    """Test integration between LongTermMemory and GlobalKnowledgeBase."""
    memory = LongTermMemory(llm_config, agent_config, event_stream)
    
    # Create a test event with API documentation
    api_event = Event(
        type="observation",
        data={
            "web_content": "API Documentation: Example function usage...",
            "type": "web_read"
        }
    )
    
    # Add event to memory
    memory.add_event(api_event)
    
    # Search both local and global memory
    results = memory.search("API documentation")
    assert len(results) > 0
    
    # At least one result should be from global KB
    global_results = [r for r in results if '"category": "api_documentation"' in r]
    assert len(global_results) > 0

@pytest.mark.asyncio
async def test_automatic_knowledge_extraction(llm_config, agent_config, event_stream):
    """Test automatic extraction of knowledge from events."""
    memory = LongTermMemory(llm_config, agent_config, event_stream)
    
    # Create a successful code execution event
    code_event = Event(
        type="action",
        data={
            "code": "print('Hello, World!')",
            "result": "Hello, World!",
            "type": "execute_python"
        }
    )
    
    # Add event to memory
    memory.add_event(code_event)
    
    # Search for code patterns in global KB
    results = memory.global_kb.search_knowledge("Hello World", category="code_pattern")
    assert len(results) > 0
    
    # Verify the extracted knowledge
    result = results[0]
    assert result.category == "code_pattern"
    assert "Hello, World!" in result.content
    assert result.source.startswith("session_")

@pytest.mark.asyncio
async def test_knowledge_versioning(llm_config):
    """Test versioning of knowledge entries."""
    kb = GlobalKnowledgeBase(llm_config)
    
    # Create initial entry
    entry = KnowledgeEntry(
        content="Initial content",
        category="test",
        source="test"
    )
    doc_id = kb.add_entry(entry)
    
    # Make multiple updates
    updates = ["Update 1", "Update 2", "Update 3"]
    versions = []
    
    for update in updates:
        kb.update_entry(doc_id, update)
        entry = kb.get_entry(doc_id)
        versions.append(entry.version)
    
    # Verify version increments
    assert versions == [2, 3, 4]
    
    # Verify final content
    final = kb.get_entry(doc_id)
    assert final.content == updates[-1]
    assert final.version == len(updates) + 1  # Initial version + number of updates