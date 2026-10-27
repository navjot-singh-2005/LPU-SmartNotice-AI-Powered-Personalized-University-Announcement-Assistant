import re
from typing import List, Dict, Any, Optional, Tuple
from app.services.embedding_service import EmbeddingService
from app.services.vector_store_service import VectorStoreService
from app.models.announcement import RawAnnouncement, ExtractedAnnouncementMetadata, AnnouncementDetail
from app.core.logging_config import logger

STOPWORDS = {
    "a", "about", "above", "after", "again", "all", "am", "an", "and", "any", "are",
    "as", "at", "be", "because", "been", "before", "being", "below", "between", "both",
    "but", "by", "can", "could", "did", "do", "does", "doing", "down", "during", "each",
    "few", "for", "from", "further", "had", "has", "have", "having", "he", "her", "here",
    "hers", "herself", "him", "himself", "his", "how", "i", "if", "in", "into", "is",
    "it", "its", "itself", "just", "me", "more", "most", "my", "myself", "no", "nor",
    "not", "now", "of", "off", "on", "once", "only", "or", "other", "our", "ours",
    "ourselves", "out", "over", "own", "s", "same", "she", "should", "so", "some",
    "such", "t", "than", "that", "the", "their", "theirs", "them", "themselves",
    "then", "there", "these", "they", "this", "those", "through", "to", "too", "under",
    "until", "up", "very", "was", "we", "were", "what", "when", "where", "which",
    "while", "who", "whom", "why", "will", "with", "you", "your", "yours", "yourself",
    "yourselves", "hello", "hi", "hey", "please", "thanks", "thank"
}

class RetrievalService:
    """Hybrid Retrieval Service combining Semantic Embeddings + Lexical Scoring + RRF Candidate Merging."""

    def __init__(self):
        self.embedding_service = EmbeddingService()
        self.vector_store = VectorStoreService()

    def lexical_score(self, query: str, document_text: str) -> float:
        """Compute term-frequency based lexical relevance score for exact matches (course codes, rooms, dates, ref numbers)."""
        raw_terms = re.findall(r"\w+", query.lower())
        # Filter out common stopwords unless they are part of a specific phrase or identifier
        query_terms = [t for t in set(raw_terms) if len(t) >= 2 and t not in STOPWORDS]
        if not query_terms:
            return 0.0

        doc_lower = document_text.lower()
        score = 0.0

        for term in query_terms:
            count = doc_lower.count(term)
            if count > 0:
                # Give higher weight to exact term matches
                score += (1.0 + 0.5 * min(count, 5))

        # Bonus for exact query phrase match (if query contains substantive non-stopwords)
        clean_q = " ".join(query_terms)
        if len(clean_q) > 3 and clean_q in doc_lower:
            score += 3.0

        return score

    def reciprocal_rank_fusion(
        self,
        semantic_results: List[Tuple[str, float]],
        lexical_results: List[Tuple[str, float]],
        k: int = 60
    ) -> List[Tuple[str, float]]:
        """Combine two ranked lists using Reciprocal Rank Fusion (RRF)."""
        scores: Dict[str, float] = {}

        # Semantic ranks
        for rank, (doc_id, _) in enumerate(semantic_results):
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))

        # Lexical ranks
        for rank, (doc_id, _) in enumerate(lexical_results):
            scores[doc_id] = scores.get(doc_id, 0.0) + (1.0 / (k + rank + 1))

        sorted_docs = sorted(scores.items(), key=lambda x: x[1], reverse=True)
        return sorted_docs

    def search(
        self,
        query: str,
        top_k: int = 5,
        category_filter: Optional[str] = None,
        raw_announcements: Optional[List[RawAnnouncement]] = None
    ) -> List[Dict[str, Any]]:
        """Hybrid search returning ranked announcement evidence records with similarity scores."""
        if not query or not query.strip():
            return []

        # 1. Semantic Vector Search via ChromaDB
        semantic_tuples: List[Tuple[str, float]] = []
        doc_map: Dict[str, Dict[str, Any]] = {}

        collection_count = self.vector_store.collection.count()
        if collection_count > 0:
            try:
                query_vector = self.embedding_service.embed_text(query)
                chroma_filter = {"category": category_filter} if category_filter else None

                chroma_res = self.vector_store.collection.query(
                    query_embeddings=[query_vector],
                    n_results=min(top_k * 3, collection_count),
                    where=chroma_filter,
                    include=["documents", "metadatas", "distances"]
                )

                if chroma_res and chroma_res["ids"] and chroma_res["ids"][0]:
                    ids = chroma_res["ids"][0]
                    docs = chroma_res["documents"][0] if chroma_res["documents"] else []
                    metas = chroma_res["metadatas"][0] if chroma_res["metadatas"] else []
                    distances = chroma_res["distances"][0] if chroma_res["distances"] else []

                    for i, doc_id in enumerate(ids):
                        dist = distances[i] if i < len(distances) else 1.0
                        # Convert distance to similarity score in [0, 1]
                        sim_score = max(0.0, 1.0 - dist)
                        semantic_tuples.append((doc_id, sim_score))

                        doc_map[doc_id] = {
                            "announcement_id": doc_id,
                            "document": docs[i] if i < len(docs) else "",
                            "metadata": metas[i] if i < len(metas) else {},
                            "semantic_score": sim_score
                        }
            except Exception as e:
                logger.warning("Vector search query encountered error (%s); falling back to lexical search.", e)

        # 2. Lexical scoring across candidate pool (or provided raw announcements)
        candidate_docs = list(doc_map.values())

        # If raw_announcements are supplied, add any matching exact ref/title to pool
        if raw_announcements:
            raw_by_id = {ann.announcement_id: ann for ann in raw_announcements}
            for ann_id, ann in raw_by_id.items():
                if ann_id not in doc_map:
                    doc_text = f"Title: {ann.title}\nRef: {ann.reference_number}\nContent: {ann.full_content}"
                    l_score = self.lexical_score(query, doc_text)
                    if l_score > 1.0:
                        doc_map[ann_id] = {
                            "announcement_id": ann_id,
                            "document": doc_text,
                            "metadata": {
                                "announcement_id": ann.announcement_id,
                                "title": ann.title,
                                "publication_date": ann.publication_date,
                                "reference_number": ann.reference_number or "",
                                "attachment_present": ann.attachment_present,
                                "attachment_names": ", ".join(ann.attachment_names),
                                "category": "GENERAL",
                                "decision_completeness": "ATTACHMENT_MISSING" if ann.attachment_present else "COMPLETE",
                                "source": getattr(ann, "source", "historical"),
                                "source_url": getattr(ann, "source_url", None)
                            },
                            "semantic_score": 0.0
                        }

        lexical_tuples: List[Tuple[str, float]] = []
        for doc_id, data in doc_map.items():
            l_score = self.lexical_score(query, data["document"])
            if l_score > 0:
                lexical_tuples.append((doc_id, l_score))

        lexical_tuples.sort(key=lambda x: x[1], reverse=True)

        # 3. Candidate Merging via RRF
        rrf_ranked = self.reciprocal_rank_fusion(semantic_tuples, lexical_tuples)

        # 4. Format top_k output
        final_results = []
        for doc_id, rrf_score in rrf_ranked[:top_k]:
            item = doc_map[doc_id]
            meta = item["metadata"]
            raw_att = meta.get("attachment_names", [])
            if isinstance(raw_att, list):
                att_names = [str(x) for x in raw_att if str(x).strip()]
            else:
                att_names = [x.strip() for x in str(raw_att).split(",") if x.strip()]

            final_results.append({
                "announcement_id": doc_id,
                "title": meta.get("title", ""),
                "publication_date": meta.get("publication_date", ""),
                "reference_number": meta.get("reference_number") or None,
                "document": item["document"],
                "full_content": item["document"],
                "is_detail_complete": bool(meta.get("is_detail_complete", True)),
                "attachment_present": bool(meta.get("attachment_present", False)),
                "attachment_names": att_names,
                "attachment_content_available": False,
                "decision_completeness": meta.get("decision_completeness", "COMPLETE"),
                "category": meta.get("category", "GENERAL"),
                "urgency": meta.get("urgency", "LOW"),
                "source": meta.get("source", "historical"),
                "source_url": meta.get("source_url") or None,
                "rrf_score": round(rrf_score, 4),
                "semantic_score": round(item["semantic_score"], 4)
            })

        return final_results
