import json
from typing import Optional

from openhands.core.config import AgentConfig, LLMConfig
from openhands.core.logger import openhands_logger as logger
from openhands.events.event import Event
from openhands.events.serialization.event import event_to_memory
from openhands.events.stream import EventStream
from openhands.memory.global_kb import GlobalKnowledgeBase, KnowledgeEntry
from openhands.utils.embeddings import (
    LLAMA_INDEX_AVAILABLE,
    EmbeddingsLoader,
    check_llama_index,
)

# Conditional imports based on llama_index availability
if LLAMA_INDEX_AVAILABLE:
    import chromadb
    from llama_index.core import Document
    from llama_index.core.indices.vector_store.base import VectorStoreIndex
    from llama_index.core.indices.vector_store.retrievers.retriever import (
        VectorIndexRetriever,
    )
    from llama_index.core.schema import TextNode
    from llama_index.vector_stores.chroma import ChromaVectorStore

# Singleton instance of GlobalKnowledgeBase
_global_kb: Optional[GlobalKnowledgeBase] = None

def get_global_kb(llm_config: LLMConfig) -> GlobalKnowledgeBase:
    """Get or create the global knowledge base singleton."""
    global _global_kb
    if _global_kb is None:
        _global_kb = GlobalKnowledgeBase(llm_config)
    return _global_kb

class LongTermMemory:
    """Handles storing information for the agent to access later, using chromadb."""

    event_stream: EventStream

    def __init__(
        self,
        llm_config: LLMConfig,
        agent_config: AgentConfig,
        event_stream: EventStream,
    ):
        """Initialize the chromadb and set up ChromaVectorStore for later use."""

        check_llama_index()

        # initialize the chromadb client for session memory
        db = chromadb.PersistentClient(
            path=f'./cache/sessions/{event_stream.sid}/memory',
        )
        self.collection = db.get_or_create_collection(name='memories')
        vector_store = ChromaVectorStore(chroma_collection=self.collection)

        # embedding model
        embedding_strategy = llm_config.embedding_model
        self.embed_model = EmbeddingsLoader.get_embedding_model(
            embedding_strategy, llm_config
        )

        # instantiate the index
        self.index = VectorStoreIndex.from_vector_store(vector_store, self.embed_model)
        self.thought_idx = 0

        # initialize the event stream
        self.event_stream = event_stream

        # max of threads to run the pipeline
        self.memory_max_threads = agent_config.memory_max_threads

        # Get reference to global knowledge base
        self.global_kb = get_global_kb(llm_config)

    def add_event(self, event: Event):
        """Adds a new event to the long term memory with a unique id.

        Parameters:
        - event: The new event to be added to memory
        """
        try:
            # convert the event to a memory-friendly format, and don't truncate
            event_data = event_to_memory(event, -1)
        except (json.JSONDecodeError, KeyError, ValueError) as e:
            logger.warning(f'Failed to process event: {e}')
            return

        # determine the event type and ID
        event_type = ''
        event_id = ''
        if 'action' in event_data:
            event_type = 'action'
            event_id = event_data['action']
        elif 'observation' in event_data:
            event_type = 'observation'
            event_id = event_data['observation']

        # create a Document instance for the event
        doc = Document(
            text=json.dumps(event_data),
            doc_id=str(self.thought_idx),
            extra_info={
                'type': event_type,
                'id': event_id,
                'idx': self.thought_idx,
            },
        )
        self.thought_idx += 1
        logger.debug('Adding %s event to memory: %d', event_type, self.thought_idx)
        self._add_document(document=doc)

        # Check if this event contains knowledge that should be added to global KB
        self._maybe_add_to_global_kb(event_data, event_type)

    def _maybe_add_to_global_kb(self, event_data: dict, event_type: str):
        """Check if an event contains knowledge that should be added to global KB.
        
        Knowledge Extraction Patterns:
        1. API Documentation & References
           - API documentation pages
           - Function signatures and usage examples
           - Package import patterns
           
        2. Code Patterns & Solutions
           - Successful code executions
           - Common programming patterns
           - Configuration examples
           - Build/deployment scripts
           
        3. Error Handling & Troubleshooting
           - Error messages and their solutions
           - Common pitfalls and workarounds
           - Debug patterns
           
        4. Best Practices & Conventions
           - Code style recommendations
           - Project structure patterns
           - Security best practices
           
        5. Environment & Setup
           - Dependencies and versions
           - Environment variables
           - Installation steps
           
        6. Tool Usage & Commands
           - CLI command patterns
           - Tool configuration
           - Common flags and options
        """
        try:
            if event_type == 'observation':
                # 1. API Documentation & References
                if 'web_content' in event_data:
                    content = event_data['web_content'].lower()
                    
                    # API Documentation
                    if any(term in content for term in ['api', 'documentation', 'reference', 'sdk']):
                        entry = KnowledgeEntry(
                            content=event_data['web_content'],
                            category='api_documentation',
                            source=f'session_{self.event_stream.sid}',
                            metadata={
                                'event_type': event_type,
                                'url': event_data.get('url', '')
                            }
                        )
                        self.global_kb.add_entry(entry)
                    
                    # Best Practices & Conventions
                    if any(term in content for term in ['best practice', 'convention', 'recommended', 'style guide']):
                        entry = KnowledgeEntry(
                            content=event_data['web_content'],
                            category='best_practices',
                            source=f'session_{self.event_stream.sid}',
                            metadata={
                                'event_type': event_type,
                                'url': event_data.get('url', '')
                            }
                        )
                        self.global_kb.add_entry(entry)
                    
                    # Security Patterns
                    if any(term in content for term in ['security', 'vulnerability', 'cve', 'authentication']):
                        entry = KnowledgeEntry(
                            content=event_data['web_content'],
                            category='security_patterns',
                            source=f'session_{self.event_stream.sid}',
                            metadata={
                                'event_type': event_type,
                                'url': event_data.get('url', '')
                            }
                        )
                        self.global_kb.add_entry(entry)

            elif event_type == 'action':
                # 2. Code Patterns & Solutions
                if 'code' in event_data and 'result' in event_data:
                    result_lower = event_data['result'].lower()
                    code_lower = event_data['code'].lower()
                    
                    # Successful Code Executions
                    if 'error' not in result_lower and 'exception' not in result_lower:
                        # Identify specific code patterns
                        pattern_type = None
                        if any(term in code_lower for term in ['import', 'from']):
                            pattern_type = 'import_pattern'
                        elif any(term in code_lower for term in ['def ', 'class ']):
                            pattern_type = 'definition_pattern'
                        elif any(term in code_lower for term in ['try:', 'except', 'finally:']):
                            pattern_type = 'error_handling'
                        elif any(term in code_lower for term in ['async ', 'await ']):
                            pattern_type = 'async_pattern'
                        else:
                            pattern_type = 'code_pattern'

                        entry = KnowledgeEntry(
                            content=json.dumps({
                                'code': event_data['code'],
                                'result': event_data['result'],
                                'pattern_type': pattern_type
                            }),
                            category=pattern_type,
                            source=f'session_{self.event_stream.sid}',
                            metadata={
                                'event_type': event_type,
                                'command_type': event_data.get('type', '')
                            }
                        )
                        self.global_kb.add_entry(entry)
                    
                    # Error Solutions
                    elif 'error' in result_lower or 'exception' in result_lower:
                        # Only store if this error was later resolved in the session
                        # This requires checking future events, which we'll implement
                        # TODO: Implement error resolution tracking
                        pass

                # 3. Tool Usage & Commands
                if event_data.get('type') == 'execute_bash':
                    command = event_data.get('code', '').strip()
                    result = event_data.get('result', '').lower()
                    
                    # Store successful command patterns
                    if command and 'error' not in result and 'exception' not in result:
                        # Identify command category
                        cmd_category = 'shell_command'
                        if 'git' in command:
                            cmd_category = 'git_command'
                        elif 'docker' in command or 'container' in command:
                            cmd_category = 'container_command'
                        elif 'pip' in command or 'poetry' in command:
                            cmd_category = 'package_management'
                        elif any(term in command for term in ['chmod', 'chown', 'sudo']):
                            cmd_category = 'permission_command'
                            
                        entry = KnowledgeEntry(
                            content=json.dumps({
                                'command': command,
                                'result': event_data.get('result', ''),
                                'working_directory': event_data.get('cwd', '')
                            }),
                            category=cmd_category,
                            source=f'session_{self.event_stream.sid}',
                            metadata={
                                'event_type': event_type,
                                'shell': event_data.get('shell', 'bash')
                            }
                        )
                        self.global_kb.add_entry(entry)

                # 4. Environment & Setup
                if event_data.get('type') in ['execute_bash', 'execute_python']:
                    content_lower = (event_data.get('code', '') + event_data.get('result', '')).lower()
                    
                    # Detect environment-related operations
                    if any(term in content_lower for term in [
                        'env', 'export', 'path=', 'config', 'setup', 'install',
                        'requirements.txt', 'pyproject.toml', 'package.json'
                    ]):
                        entry = KnowledgeEntry(
                            content=json.dumps({
                                'operation': event_data.get('code', ''),
                                'result': event_data.get('result', ''),
                                'context': event_data.get('type', '')
                            }),
                            category='environment_setup',
                            source=f'session_{self.event_stream.sid}',
                            metadata={
                                'event_type': event_type,
                                'setup_type': 'environment'
                            }
                        )
                        self.global_kb.add_entry(entry)

        except Exception as e:
            logger.warning(f'Failed to process event for global KB: {e}')

    def _add_document(self, document: 'Document'):
        """Inserts a single document into the index."""
        self.index.insert_nodes([self._create_node(document)])

    def _create_node(self, document: 'Document') -> 'TextNode':
        """Create a TextNode from a Document instance."""
        return TextNode(
            text=document.text,
            doc_id=document.doc_id,
            extra_info=document.extra_info,
        )

    def search(self, query: str, k: int = 10) -> list[str]:
        """Searches through both local memory and global knowledge base.

        Parameters:
        - query (str): A query to match search results to
        - k (int): Number of top results to return from each source

        Returns:
        - list[str]: Combined list of results from both local and global memory
        """
        # Search local session memory
        retriever = VectorIndexRetriever(
            index=self.index,
            similarity_top_k=k,
        )
        local_results = retriever.retrieve(query)

        # Search global knowledge base
        global_results = self.global_kb.search_knowledge(query, k=k)

        # Combine and log results
        combined_results = []
        
        # Add local results
        for result in local_results:
            logger.debug(
                f'Local Memory - Doc ID: {result.doc_id}:\n Text: {result.get_text()}\n Score: {result.score}'
            )
            combined_results.append(result.get_text())

        # Add global results
        for entry in global_results:
            logger.debug(
                f'Global KB - Category: {entry.category}:\n Content: {entry.content}\n Source: {entry.source}'
            )
            combined_results.append(json.dumps(entry.to_dict()))

        return combined_results

    def _events_to_docs(self) -> list['Document']:
        """Convert all events from the EventStream to documents for batch insert into the index."""
        try:
            events = self.event_stream.get_events()
        except Exception as e:
            logger.debug(f'No events found for session {self.event_stream.sid}: {e}')
            return []

        documents: list[Document] = []

        for event in events:
            try:
                # convert the event to a memory-friendly format, and don't truncate
                event_data = event_to_memory(event, -1)

                # determine the event type and ID
                event_type = ''
                event_id = ''
                if 'action' in event_data:
                    event_type = 'action'
                    event_id = event_data['action']
                elif 'observation' in event_data:
                    event_type = 'observation'
                    event_id = event_data['observation']

                # create a Document instance for the event
                doc = Document(
                    text=json.dumps(event_data),
                    doc_id=str(self.thought_idx),
                    extra_info={
                        'type': event_type,
                        'id': event_id,
                        'idx': self.thought_idx,
                    },
                )
                documents.append(doc)
                self.thought_idx += 1

                # Also check for global knowledge in each event
                self._maybe_add_to_global_kb(event_data, event_type)

            except (json.JSONDecodeError, KeyError, ValueError) as e:
                logger.warning(f'Failed to process event: {e}')
                continue

        if documents:
            logger.debug(f'Batch inserting {len(documents)} documents into the index.')
        else:
            logger.debug('No valid documents found to insert into the index.')

        return documents

    def create_nodes(self, documents: list['Document']) -> list['TextNode']:
        """Create nodes from a list of documents."""
        return [self._create_node(doc) for doc in documents]