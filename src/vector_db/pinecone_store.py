import os
import json
import asyncio
from pinecone import Pinecone, ServerlessSpec
from src.vector_db.base import BaseVectorStore
from src.utils.logger import logger


class PineconeVectorStore(BaseVectorStore):

    def __init__(self, db_config: dict):
        super().__init__()

        cfg = db_config

        self.api_key = cfg.get("vectordb_api_key")
        self.index_name = cfg.get("index_name")
        self.dimension = cfg.get("dimension", 384)
        self.metric = cfg.get("metric", "cosine")
        self.region = cfg.get("region", "us-east-1")

        if not self.api_key:
            raise ValueError("Pinecone API key is required")

        if not self.index_name:
            raise ValueError("Pinecone index_name is required")

        self.pc = Pinecone(api_key=self.api_key)
        self._ensure_index()
        self.index = self.pc.Index(self.index_name)


    def _ensure_index(self):
        existing_indexes = [i.name for i in self.pc.list_indexes()]

        if self.index_name not in existing_indexes:
            logger.info(f"[Pinecone] Creating index: {self.index_name}")

            self.pc.create_index(
                name=self.index_name,
                dimension=self.dimension,
                metric=self.metric,
                spec=ServerlessSpec(
                    cloud="aws",
                    region=self.region
                )
            )


    def _get_vector_path(self, client_id):
        client_root = self._get_client_root(client_id)

        pinecone_path = os.path.join(client_root, "pinecone")
        hashes_path = os.path.join(pinecone_path, "hashes")

        os.makedirs(pinecone_path, exist_ok=True)
        os.makedirs(hashes_path, exist_ok=True)

        return pinecone_path, hashes_path

    def _get_doc_hash_path(self, client_id, document_name):
        _, hashes_path = self._get_vector_path(client_id)
        return os.path.join(hashes_path, f"{document_name}.hashes")

    def _get_global_hash_path(self, client_id):
        pinecone_path, _ = self._get_vector_path(client_id)
        return os.path.join(pinecone_path, "global_hashes.json")



    def _load_json(self, path):
        if not os.path.exists(path):
            return {}
        try:
            with open(path, "r") as f:
                return json.load(f)
        except Exception:
            logger.exception(f"[Pinecone] Failed to load JSON: {path}")
            return {}

    def _save_json(self, path, data):
        try:
            with open(path, "w") as f:
                json.dump(data, f)
        except Exception:
            logger.exception(f"[Pinecone] Failed to save JSON: {path}")

    # -------------------------
    # APPEND WITH DIFF
    # -------------------------
    async def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        logger.info(f"[Pinecone] Append start | client_id={client_id}, document={document_name}")

        if paragraphs is None:
            return "File already processed"

        # -----------------------------
        # PREPARE HASHES
        # -----------------------------
        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        doc_hash_path = self._get_doc_hash_path(client_id, document_name)
        
        global_hash_path = self._get_global_hash_path(client_id)
        global_hash_map = self._load_json(global_hash_path)
        global_hashes = set(global_hash_map.keys())

        # -----------------------------
        # EXISTING FILE → FILE DIFF
        # -----------------------------
        if os.path.exists(doc_hash_path):

            logger.info("[Pinecone] Existing document detected, running incremental diff")

            old_doc_hash_map = self._load_json(doc_hash_path)
            old_hashes = set(old_doc_hash_map.keys())

            added = new_hashes - old_hashes
            deleted = old_hashes - new_hashes

            if not added and not deleted:
                logger.info("[Pinecone] No document changes detected")
                return "No changes detected"

            logger.info(f"[Pinecone] Diff | added={len(added)}, deleted={len(deleted)}")

            # DELETE FROM PINECONE
            if deleted:
                logger.info(f"[Pinecone] Deleting {len(deleted)} vectors")

                try:
                    await asyncio.to_thread(
                        self.index.delete,
                        ids=list(deleted),
                        namespace=client_id
                    )
                except Exception:
                    logger.exception("[Pinecone] Delete failed")

                # remove from global registry
                for h in deleted:
                    global_hash_map.pop(h, None)

            # GLOBAL DEDUP AFTER FILE DIFF
            final_to_add = added - global_hashes

        # -----------------------------
        # NEW FILE → GLOBAL DEDUP ONLY
        # -----------------------------
        else:

            logger.info("[Pinecone] New document detected, running global dedup")

            added = new_hashes - global_hashes
            deleted = set()

            logger.info(f"[Pinecone] New file | to_add={len(added)}")

            final_to_add = added

        logger.info(f"[Pinecone] After dedup | to_add={len(final_to_add)}")

        # -----------------------------
        # ADD TO PINECONE
        # -----------------------------
        if final_to_add:

            embedding_model = self._get_embedding()

            texts = [new_hash_map[h] for h in final_to_add]
            vectors = await asyncio.to_thread(embedding_model.embed_documents, texts)

            try:
                await asyncio.to_thread(
                        self.index.upsert,
                        vectors=[
                            {
                                "id": h,
                                "values": vectors[i],
                                "metadata": {
                                    "text": texts[i],
                                    "document": document_name
                                }
                            }
                            for i, h in enumerate(final_to_add)
                        ],
                        namespace=client_id
                    )
            except Exception:
                logger.exception("[Pinecone] Upsert failed")

            # update global registry
            for h in final_to_add:
                global_hash_map[h] = True

        # -----------------------------
        # UPDATE HASH FILES
        # -----------------------------
        self._save_json(doc_hash_path, new_hash_map)
        self._save_json(global_hash_path, global_hash_map)

        logger.info("[Pinecone] Incremental update complete")

        return "Incremental update complete"

    # -------------------------
    # RETRIEVE
    # -------------------------
    async def retrieve(self, client_id, query, top_k=5):

        logger.info(f"[Pinecone] Retrieve | client_id={client_id}, top_k={top_k}")

        embedding_model = self._get_embedding()

        query_vector = await asyncio.to_thread(embedding_model.embed_query, query)

        try:
            results = await asyncio.to_thread(
                    self.index.query,
                    vector=query_vector,
                    top_k=top_k,
                    include_metadata=True,
                    namespace=client_id
                )
        except Exception:
            logger.exception("[Pinecone] Query failed")
            return []

        return [
            match["metadata"]["text"]
            for match in results.get("matches", [])
        ]