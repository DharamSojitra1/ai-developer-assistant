# Retrieval Pipeline

The knowledge base answers questions from documents that users upload. This page explains what happens between a question and the context given to the model.

## Ingestion

Uploaded files are loaded, cleaned, split into chunks, embedded, and stored. Supported formats are plain text, Markdown, and PDF. Markdown is split along its headings first, so a chunk never mixes two sections, and each chunk is prefixed with its heading path.

Every chunk stores the document ID, source file name, document type, visibility, and owner. Private documents are only visible to the user who uploaded them, while shared documents are visible to everyone and can only be added by administrators.

## Candidate Retrieval

A question first retrieves up to 10 candidates. Vector search compares the question embedding with chunk embeddings using cosine distance, and candidates with a distance above 0.35 are discarded.

Keyword search runs in parallel using BM25. It catches exact terms that embeddings handle poorly, such as error codes, configuration names, and product identifiers. The two result lists are merged with reciprocal rank fusion, which rewards chunks that both methods rank highly.

## Reranking

The merged candidates are rescored by a cross-encoder model, ms-marco-MiniLM-L6-v2, which reads the question and the chunk together. Only the top 3 chunks after reranking are kept, and chunks whose rerank score is below the configured threshold are dropped.

If the reranker fails, retrieval returns no context instead of falling back to unranked results. Returning nothing is safer than giving the model unvalidated context.

## Answerability Check

Before the context reaches the model, a small language-model call decides whether the retrieved chunks can actually answer the question. If they cannot, the assistant says it does not have enough information. This check is the main defence against confident answers built on loosely related chunks.

## Duplicates and Updates

Each document's cleaned text is hashed with SHA-256. Indexing the same content again under the same ID is skipped, and indexing identical content under a new ID is rejected with HTTP 409. When a document is edited, only chunks whose text changed are sent to the embedding model; unchanged chunks reuse their stored vectors.
