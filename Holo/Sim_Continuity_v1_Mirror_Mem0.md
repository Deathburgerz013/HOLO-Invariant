# ContinuityMem0 - Converged Memory Layer
# Combines Mem0 v3 (ADD-only extraction + hybrid retrieval) 
# with Continuity Engine (hashlock serialized IDX + manual rebirth)

import hashlib
import json
from datetime import datetime
# Assume: your blockchain/hashlock primitives, LLM client, embedder, BM25, entity extractor

class ContinuityMem0:
    def __init__(self, llm_client, embedder, blockchain_substrate):
        self.llm = llm_client
        self.embedder = embedder
        self.chain = blockchain_substrate  # Your hashlock serialized IDX pipeline
        self.vector_store = None  # Optional secondary index for fast hybrid search (Qdrant/Chroma style)
        self.entity_graph = None   # Optional for entity linking/boosting

    # === Mem0-mirrored Extraction (Single-pass ADD-only) ===
    async def add(self, messages, user_id=None, agent_id=None, metadata=None):
        # Step 1: Retrieve top-k recent/related memories for dedup context (Mem0 style)
        context_memories = await self.search(query=json.dumps(messages), top_k=10, filters={"user_id": user_id})

        # Step 2: Single LLM call - extract distinct NEW facts only (no UPDATE/DELETE)
        extraction_prompt = f"""
        From the conversation below, extract only distinct new facts, preferences, decisions, or agent-generated insights.
        Existing context for deduplication: {context_memories}
        Return a list of independent memory items. Do not update or delete anything.
        """
        extracted = await self.llm.generate(extraction_prompt + "\nConversation: " + str(messages))

        new_memories = json.loads(extracted)  # Assume list of dicts: [{"memory": "...", "entities": [...]}]

        added_entries = []
        for mem in new_memories:
            # Embed and hash for dedup
            embedding = self.embedder.embed(mem["memory"])
            content_hash = hashlib.md5(mem["memory"].encode()).hexdigest()

            # Check exact duplicate via hash (Mem0-style)
            if await self._is_duplicate(content_hash):
                continue

            # === Continuity Engine persistence: Serialize to immutable IDX ===
            idx_entry = {
                "timestamp": datetime.utcnow().isoformat(),
                "user_id": user_id,
                "agent_id": agent_id,
                "content": mem["memory"],
                "embedding": embedding.tolist() if hasattr(embedding, "tolist") else embedding,
                "entities": mem.get("entities", []),
                "content_hash": content_hash,
                "prev_hash": self.chain.get_latest_hash(user_id),  # Chain link
                "metadata": metadata or {}
            }

            # Hashlock + serialize to blockchain substrate
            locked_entry = self.chain.hashlock_and_serialize(idx_entry)
            tx_id = await self.chain.append_to_chain(locked_entry)  # Immutable append-only

            # Optional: Index in vector store + entity graph for fast retrieval
            if self.vector_store:
                self.vector_store.upsert(tx_id, embedding, payload=idx_entry)
            if self.entity_graph and mem.get("entities"):
                self._link_entities(tx_id, mem["entities"])

            added_entries.append({"tx_id": tx_id, "memory": mem["memory"]})

        return {"status": "added", "count": len(added_entries), "entries": added_entries}

    # === Mem0-mirrored Hybrid Retrieval ===
    async def search(self, query, top_k=5, filters=None):
        # Multi-signal fusion (semantic + BM25 + entity)
        query_embedding = self.embedder.embed(query)
        query_entities = await self._extract_entities(query)  # LLM or lightweight extractor

        # 1. Vector semantic search (if secondary store)
        vector_results = self.vector_store.search(query_embedding, top_k=top_k * 2, filters=filters) if self.vector_store else []

        # 2. BM25 keyword search on chain (or cached index)
        bm25_results = await self.chain.bm25_search(query, top_k=top_k * 2, filters=filters)

        # 3. Entity matching/boost
        entity_results = await self._entity_boosted_search(query_entities, top_k=top_k * 2)

        # Fuse scores (simple weighted sum or reciprocal rank fusion)
        fused = self._fuse_signals(vector_results, bm25_results, entity_results)
        return sorted(fused, key=lambda x: x["score"], reverse=True)[:top_k]

    # === Continuity-specific: Manual Audit & Rebirth Override ===
    async def audit_and_rebirth(self, tx_id, corrected_content, auditor_id):
        """
        External manual override - does NOT mutate existing entry.
        Creates a new linked "rebirth" entry that supersedes for future recall
        while preserving full history for replay/verification.
        """
        old_entry = await self.chain.get_by_tx(tx_id)
        if not old_entry:
            return {"error": "not found"}

        rebirth_entry = {
            "type": "rebirth_override",
            "timestamp": datetime.utcnow().isoformat(),
            "original_tx": tx_id,
            "corrected_content": corrected_content,
            "auditor_id": auditor_id,
            "prev_hash": self.chain.get_latest_hash(old_entry["user_id"]),
            # Re-embed, re-hash, re-link entities as needed
        }

        locked_rebirth = self.chain.hashlock_and_serialize(rebirth_entry)
        new_tx = await self.chain.append_to_chain(locked_rebirth)

        # Update secondary indexes to point to new_tx for future retrievals
        if self.vector_store:
            new_emb = self.embedder.embed(corrected_content)
            self.vector_store.upsert(new_tx, new_emb, payload=rebirth_entry)

        return {"status": "rebirth_created", "new_tx": new_tx, "original_tx": tx_id}

    # Helper: Replay full history with overrides applied (verifiable)
    async def replay_history(self, user_id, up_to_tx=None):
        chain_entries = await self.chain.get_full_chain(user_id, up_to_tx)
        # Apply rebirth overrides in order, producing final coherent view
        # This gives drift-free, auditable reconstruction
        ...