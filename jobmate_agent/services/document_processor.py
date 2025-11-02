"""
Document processing service for chunking and embedding using LangChain.
Handles O*NET skills processing with advanced text splitting and vector storage.
Note: Resume and job description processing removed in skill-only mode.
"""

import os
import logging
from typing import List, Dict, Any, Optional, Tuple
from langchain_core.documents import Document
from jobmate_agent.services.vector_store.vector_store import get_or_create_collection
import tiktoken

logger = logging.getLogger(__name__)

# Configure debug logging only via environment, do not reconfigure root handlers
if os.getenv("DEBUG_MODE") == "1":
    logger.setLevel(logging.DEBUG)


def tiktoken_len(text: str) -> int:
    """Count tokens using tiktoken for accurate chunk sizing."""
    try:
        encoding = tiktoken.get_encoding("cl100k_base")  # GPT-4 encoding
        return len(encoding.encode(text))
    except Exception as e:
        logger.warning(
            f"Failed to count tokens with tiktoken, falling back to len(): {e}"
        )
        return len(text)


class DocumentProcessor:
    """Document processor for chunking and embedding using LangChain."""

    def __init__(
        self,
        collection_name: str,
        embedding_model: str = None,
        *,
        chunk_size: Optional[int] = None,
        chunk_overlap: Optional[int] = None,
        separators: Optional[List[str]] = None,
    ):
        """Initialize the document processor.

        Args:
            collection_name (str): Name of the ChromaDB collection
            embedding_model (str, optional): OpenAI embedding model to use. Defaults to text-embedding-3-small.
        """
        self.collection_name = collection_name
        # Enforce a fixed embedding model to match collection dimensions
        self.embedding_model = "text-embedding-3-large"

        # Log the actual embedding model at debug to reduce noise
        logger.debug(f"Using embedding model: {self.embedding_model}")

        # Fixed embedding dimensions aligned with text-embedding-3-large
        self.embedding_dimensions = 3072

        logger.debug(f"Embedding dimensions: {self.embedding_dimensions}")
        # Lazy import heavy dependencies to avoid startup failures
        from langchain_openai import OpenAIEmbeddings
        from langchain_text_splitters import RecursiveCharacterTextSplitter
        from langchain_chroma import Chroma

        self.embeddings = OpenAIEmbeddings(model=self.embedding_model)
        # Resolve chunking configuration from parameters or environment
        resolved_chunk_size = (
            int(os.getenv("CHUNK_TOKENS", 600))
            if chunk_size is None
            else int(chunk_size)
        )
        resolved_chunk_overlap = (
            int(os.getenv("CHUNK_OVERLAP", 60))
            if chunk_overlap is None
            else int(chunk_overlap)
        )
        resolved_separators = separators or ["\n\n", "\n", ". ", " ", ""]

        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=resolved_chunk_size,
            chunk_overlap=resolved_chunk_overlap,
            length_function=tiktoken_len,
            separators=resolved_separators,
        )
        self.collection = get_or_create_collection(collection_name)

        # Check CHROMA_PERSIST_DIR configuration
        chroma_dir = os.getenv("CHROMA_PERSIST_DIR", "./instance/chroma")
        if chroma_dir == "./instance/chroma":
            logger.info(
                "CHROMA_PERSIST_DIR not set - using default './instance/chroma'"
            )

        # Create a Chroma wrapper for LangChain compatibility
        self.vectorstore = Chroma(
            collection_name=collection_name,
            embedding_function=self.embeddings,
            persist_directory=chroma_dir,
        )

        # Check if collection exists and has correct dimensions
        try:
            existing_collection = self.vectorstore._collection
            if existing_collection:
                # Get the collection metadata to check dimensions
                collection_metadata = existing_collection.get()
                if collection_metadata and "embeddings" in collection_metadata:
                    existing_dim = (
                        len(collection_metadata["embeddings"][0])
                        if collection_metadata["embeddings"]
                        else 0
                    )
                    if existing_dim != self.embedding_dimensions:
                        logger.warning(
                            f"Collection dimension mismatch: existing={existing_dim}, expected={self.embedding_dimensions}. "
                            "Recreate the collection to avoid embedding errors."
                        )
        except Exception as e:
            logger.debug(f"Could not check collection dimensions: {e}")

        logger.info(
            f"Initialized DocumentProcessor collection='{self.collection_name}' model='{self.embedding_model}'"
        )

    def process_document(
        self,
        doc_id: str,
        text: str,
        metadata: Dict[str, Any] = None,
        delete_existing: bool = True,
    ) -> int:
        """Process a document: chunk, embed, and store.

        Args:
            doc_id (str): Unique document identifier
            text (str): Document text content
            metadata (Dict[str, Any], optional): Additional metadata for the document. Defaults to None.
            delete_existing (bool, optional): Whether to delete existing chunks for this doc_id. Defaults to True.

        Returns:
            int: Number of chunks created
        """
        try:
            # Delete existing chunks if requested
            if delete_existing:
                self.delete_document(doc_id)

            document = Document(page_content=text, metadata=metadata or {})

            # Chunk the document using recursive strategy
            chunks = self.text_splitter.split_documents([document])

            # Generate unique IDs for each chunk
            chunk_ids = [f"{doc_id}_chunk_{i}" for i in range(len(chunks))]

            for i, chunk in enumerate(chunks):
                chunk.metadata.update(
                    {
                        "doc_id": doc_id,
                        "chunk_id": i,
                        "total_chunks": len(chunks),
                        "chunk_strategy": "recursive",
                        "text_preview": (
                            chunk.page_content[:100] + "..."
                            if len(chunk.page_content) > 100
                            else chunk.page_content
                        ),
                        "collection": self.collection_name,
                    }
                )

            # Add documents with explicit IDs for proper deletion later
            self.vectorstore.add_documents(chunks, ids=chunk_ids)

            # Ensure persistence to disk using the underlying collection
            if hasattr(self.vectorstore, "_collection") and hasattr(
                self.vectorstore._collection, "persist"
            ):
                self.vectorstore._collection.persist()
            elif hasattr(self.collection, "persist"):
                self.collection.persist()

            logger.info(f"Processed document '{doc_id}' chunks={len(chunks)}")
            return len(chunks)

        except Exception as e:
            logger.error(f"Error processing document '{doc_id}': {str(e)}")
            raise

    def search_similar(
        self,
        query: str,
        k: int = 10,
        filter_dict: Dict = None,
        score_threshold: float = None,
        user_id: str = None,
    ) -> List[Document]:
        """Search for similar documents.

        Args:
            query (str): Search query
            k (int, optional): Number of results to return. Defaults to 10.
            filter_dict (Dict, optional): Metadata filters. Defaults to None.
            score_threshold (float, optional): Minimum similarity score. Defaults to None.
            user_id (str, optional): User ID for automatic filtering. Defaults to None.

        Returns:
            List[Document]: List of similar documents
        """
        try:
            # Enforce user isolation if user_id provided
            if user_id:
                filter_dict = filter_dict or {}
                filter_dict["user_id"] = user_id
            if score_threshold:
                # Use similarity search with score and filter by threshold
                results_with_scores = self.vectorstore.similarity_search_with_score(
                    query=query,
                    k=k * 2,  # Get more results to filter
                    filter=filter_dict,
                )
                # Filter by score threshold (lower score = more similar in Chroma)
                filtered_results = [
                    doc
                    for doc, score in results_with_scores
                    if score <= score_threshold
                ]
                return filtered_results[:k]
            else:
                return self.vectorstore.similarity_search(
                    query=query, k=k, filter=filter_dict
                )
        except Exception as e:
            logger.error(f"Error searching similar documents: {str(e)}")
            raise

    def search_with_relevance(
        self, query: str, k: int = 10, user_id: str = None
    ) -> List[Tuple[Document, float]]:
        """Search with normalized relevance scores (higher = more similar).

        Args:
            query (str): Search query
            k (int, optional): Number of results to return. Defaults to 10.
            user_id (str, optional): User ID for automatic filtering. Defaults to None.

        Returns:
            List[Tuple[Document, float]]: List of (document, relevance_score) tuples
        """
        try:
            # Enforce user isolation if user_id provided
            filter_dict = {}
            if user_id:
                filter_dict["user_id"] = user_id

            results_with_scores = self.vectorstore.similarity_search_with_score(
                query=query,
                k=k,
                filter=filter_dict if filter_dict else None,
            )

            # Normalize scores: convert distance to similarity (higher = better)
            normalized_results = [
                (doc, 1.0 - score) for doc, score in results_with_scores
            ]

            return normalized_results

        except Exception as e:
            logger.error(f"Error searching with relevance: {str(e)}")
            raise

    def search_with_score(
        self, query: str, k: int = 10, filter_dict: Dict = None
    ) -> List[Tuple[Document, float]]:
        """Search with similarity scores.

        Args:
            query (str): Search query
            k (int, optional): Number of results to return. Defaults to 10.
            filter_dict (Dict, optional): Metadata filters. Defaults to None.

        Returns:
            List[Tuple[Document, float]]: List of (document, score) tuples
        """
        try:
            return self.vectorstore.similarity_search_with_score(
                query=query, k=k, filter=filter_dict
            )
        except Exception as e:
            logger.error(f"Error searching with scores: {str(e)}")
            raise

    def get_retriever(
        self, k: int = 10, search_type: str = "similarity"
    ) -> "VectorStoreRetriever":
        """Get a retriever for use in LangChain chains.

        Args:
            k (int, optional): Number of documents to retrieve. Defaults to 10.
            search_type (str, optional): Type of search ('similarity', 'mmr', 'similarity_score_threshold'). Defaults to "similarity".

        Returns:
            VectorStoreRetriever: VectorStoreRetriever instance
        """
        # Lazy import to avoid heavy dependency at app startup
        from langchain_core.vectorstores import VectorStoreRetriever
        search_kwargs = {"k": k}

        if search_type == "mmr":
            search_kwargs["fetch_k"] = k * 2
            search_kwargs["lambda_mult"] = 0.5

        return self.vectorstore.as_retriever(
            search_type=search_type, search_kwargs=search_kwargs
        )

    def delete_document(self, doc_id: str) -> int:
        """Delete all chunks for a document.

        Args:
            doc_id (str): Document identifier

        Returns:
            int: Number of chunks deleted (0 if none found)
        """
        try:
            # Use singleton collection for better performance
            results = self.collection.get(where={"doc_id": doc_id})

            if not results or not results.get("ids"):
                logger.info(f"No chunks found for document '{doc_id}'")
                return 0

            # Delete by IDs
            chunk_ids = results["ids"]
            self.collection.delete(ids=chunk_ids)

            # Ensure persistence using the underlying collection
            if hasattr(self.vectorstore, "_collection") and hasattr(
                self.vectorstore._collection, "persist"
            ):
                self.vectorstore._collection.persist()
            elif hasattr(self.collection, "persist"):
                self.collection.persist()

            logger.info(f"Deleted {len(chunk_ids)} chunks for document '{doc_id}'")
            return len(chunk_ids)

        except Exception as e:
            logger.error(f"Error deleting document '{doc_id}': {str(e)}")
            return 0

    def get_document_stats(self, doc_id: str) -> Dict[str, Any]:
        """Get statistics for a document.

        Args:
            doc_id (str): Document identifier

        Returns:
            Dict[str, Any]: Dictionary with document statistics
        """
        try:
            # Use singleton collection for efficient filtering
            results = self.collection.get(where={"doc_id": doc_id})

            if not results or not results.get("documents"):
                return {"chunk_count": 0, "total_tokens": 0}

            documents = results["documents"]
            total_tokens = sum(tiktoken_len(doc) for doc in documents)

            return {
                "chunk_count": len(documents),
                "total_tokens": total_tokens,
                "avg_chunk_tokens": total_tokens // len(documents) if documents else 0,
            }

        except Exception as e:
            logger.error(f"Error getting document stats for '{doc_id}': {str(e)}")
            return {"error": str(e)}


def get_skills_processor() -> DocumentProcessor:
    """Get processor for skills_ontology collection."""
    return DocumentProcessor("skills_ontology")


def process_job_description(*args, **kwargs) -> int:
    raise NotImplementedError(
        "Job description embeddings are removed in skill-only mode."
    )
