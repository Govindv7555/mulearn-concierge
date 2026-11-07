"""
µLearn Concierge — RAG Retrieval Engine
Uses BM25 (rank_bm25) for lightweight, fast keyword retrieval over markdown knowledge files.
Includes query-stopword filtering and threshold gating so small talk passes no context to the LLM.
"""

import os
import re
import glob
import time
from rank_bm25 import BM25Okapi

# Common filler / conversational words to exclude from BM25 scoring
STOPWORDS = {
    "a", "about", "above", "after", "again", "against", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both", "but",
    "by", "can", "did", "do", "does", "doing", "down", "during", "each", "few", "for", "from",
    "further", "had", "has", "have", "having", "he", "her", "here", "hers", "him", "his", "how",
    "i", "if", "in", "into", "is", "it", "its", "just", "me", "more", "most", "my", "no", "nor",
    "not", "now", "of", "off", "on", "once", "only", "or", "other", "our", "out", "over", "own",
    "same", "she", "should", "so", "some", "such", "than", "that", "the", "their", "them", "then",
    "there", "these", "they", "this", "those", "through", "to", "too", "under", "until", "up",
    "very", "was", "we", "were", "what", "when", "where", "which", "while", "who", "whom", "why",
    "with", "would", "you", "your", "yours", "tell", "please", "give", "hi", "hello", "hey",
    "thanks", "thank", "bye", "goodbye", "good", "morning", "evening", "night"
}

# Score threshold below which a query is considered non-matching (e.g. small talk / off-topic)
DEFAULT_MIN_SCORE = 2.0


class KnowledgeStore:
    """Loads markdown files from the knowledge directory, chunks by ## headers,
    and provides BM25-based retrieval with score thresholding."""

    def __init__(self, knowledge_dir="knowledge"):
        self.knowledge_dir = knowledge_dir
        self.chunks = []
        self.bm25 = None
        self._mtimes = {}
        self._load()

    def _get_mtimes(self):
        """Get modification times of all knowledge files."""
        mtimes = {}
        pattern = os.path.join(self.knowledge_dir, "*.md")
        for filepath in glob.glob(pattern):
            mtimes[filepath] = os.path.getmtime(filepath)
        return mtimes

    def _needs_reload(self):
        """Check if any knowledge files have changed since last load."""
        current = self._get_mtimes()
        return current != self._mtimes

    def _load(self):
        """Parse all markdown files into chunks, build BM25 index."""
        self.chunks = []
        pattern = os.path.join(self.knowledge_dir, "*.md")

        for filepath in glob.glob(pattern):
            filename = os.path.basename(filepath).lower()
            source = "discord" if "discord" in filename else "website"

            try:
                with open(filepath, encoding="utf-8") as f:
                    text = f.read()
            except (IOError, OSError) as e:
                print(f"Warning: Could not read {filepath}: {e}")
                continue

            # Split by ## headers (keep the header with its content)
            sections = re.split(r'\n(?=## )', text)

            for section in sections:
                section = section.strip()
                # Only keep actual content sections starting with ##
                if not section.startswith("## "):
                    continue
                if len(section) < 30:
                    continue
                if section.startswith("<!--"):
                    continue

                # Extract title from ## header
                title_match = re.match(r'##\s+(.+)', section)
                if title_match:
                    title = title_match.group(1).strip()
                    title = title[:100]  # Cap title length
                else:
                    title = "General"

                self.chunks.append({
                    "text": section,
                    "source": source,
                    "title": title,
                    "file": os.path.basename(filepath),
                })

        # Build BM25 index with positive IDF floor
        if self.chunks:
            tokenized = [self._tokenize(c["text"]) for c in self.chunks]
            self.bm25 = BM25Okapi(tokenized)
            # Ensure every term has a strictly positive IDF floor (prevents 0.0 idf on small corpora)
            for word in self.bm25.idf:
                if self.bm25.idf[word] <= 0:
                    self.bm25.idf[word] = 0.5
        else:
            self.bm25 = None

        self._mtimes = self._get_mtimes()

    def _tokenize(self, text):
        """Simple whitespace + punctuation tokenizer. Preserves µ and normalizes mulearn variants."""
        text = text.lower()
        # Normalize mulearn / ulearn variants to µlearn so both forms match
        text = text.replace('mulearn', 'µlearn').replace('ulearn', 'µlearn')
        # Remove markdown syntax
        text = re.sub(r'[#*_\[\]()>`~|]', ' ', text)
        # Remove URLs
        text = re.sub(r'https?://\S+', ' ', text)
        # Split on non-alphanumeric (keep µ)
        tokens = re.findall(r'[a-zµ0-9]+', text)
        return tokens

    def retrieve(self, query, top_k=5, min_score=DEFAULT_MIN_SCORE):
        """Retrieve the top-k most relevant chunks for a query.

        If the query contains only stopwords or the highest BM25 score
        is below min_score, returns an empty list [] so small talk and
        unrelated queries do not receive forced µLearn context.
        """
        # Auto-reload if files changed
        if self._needs_reload():
            self._load()

        if not self.bm25 or not self.chunks:
            return []

        tokens = self._tokenize(query)
        if not tokens:
            return []

        # Filter out stopwords for scoring
        content_tokens = [t for t in tokens if t not in STOPWORDS]
        if not content_tokens:
            return []

        scores = list(self.bm25.get_scores(content_tokens))

        # Add section title boost: if a content token matches the chunk's title,
        # grant a relevance boost to ensure canonical sections rank #1
        for i, chunk in enumerate(self.chunks):
            title_tokens = set(self._tokenize(chunk["title"]))
            if any(t in title_tokens for t in content_tokens):
                scores[i] += 4.0

        # Pair indices with scores, sort descending
        ranked = sorted(enumerate(scores), key=lambda x: x[1], reverse=True)

        results = []
        for idx, score in ranked[:top_k]:
            if score >= min_score:
                chunk = self.chunks[idx].copy()
                chunk["score"] = round(float(score), 4)
                results.append(chunk)

        return results

    def get_all_sources(self):
        """Return a summary of loaded knowledge sources."""
        sources = {}
        for chunk in self.chunks:
            key = chunk["file"]
            if key not in sources:
                sources[key] = {"source": chunk["source"], "chunks": 0}
            sources[key]["chunks"] += 1
        return sources


# Module-level singleton (lazy init)
_store = None


def get_store():
    """Get or create the global KnowledgeStore instance."""
    global _store
    if _store is None:
        _store = KnowledgeStore()
    return _store


def retrieve(query, top_k=5, min_score=DEFAULT_MIN_SCORE):
    """Convenience function: retrieve top-k chunks for a query exceeding min_score."""
    return get_store().retrieve(query, top_k=top_k, min_score=min_score)
