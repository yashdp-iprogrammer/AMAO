import os
import json
from langchain_chroma import Chroma
from src.vector_db.base import BaseVectorStore
from transformers import logging
logging.set_verbosity_error()

class ChromaVectorStore(BaseVectorStore):
    
    def __init__(self):
        super().__init__()
        self.embedding = self._get_embedding()

    def _get_vector_path(self, client_id):
        client_root = self._get_client_root(client_id)
        
        chroma_path = os.path.join(client_root, "chroma")
        docs_path = os.path.join(chroma_path, "hashes")
        
        os.makedirs(docs_path, exist_ok=True)
        os.makedirs(chroma_path, exist_ok=True)
        
        return chroma_path, docs_path
    

    def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        chroma_path, docs_path = self._get_vector_path(client_id)
        hash_path = os.path.join(docs_path, f"{document_name}.hashes")

        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        # Initialize Chroma
        vector_store = Chroma(
            persist_directory=chroma_path,
            embedding_function=self.embedding
        )

        before_count = vector_store._collection.count()
        print(f"[VectorDB] Embeddings BEFORE update: {before_count}")

        # -----------------------------
        # CASE 1: SAME FILENAME UPDATE
        # -----------------------------
        if os.path.exists(hash_path):

            print("[VectorDB] Existing document detected. Running incremental diff.")

            with open(hash_path, "r") as f:
                old_hash_map = json.load(f)

            old_hashes = set(old_hash_map.keys())

            added = new_hashes - old_hashes
            deleted = old_hashes - new_hashes

            if not added and not deleted:
                print("[VectorDB] No document changes detected")
                return "No changes detected"

            print("\n========= DIFF SUMMARY =========")
            print(f"New paragraphs detected: {len(added)}")
            print(f"Deleted paragraphs detected: {len(deleted)}")
            print("================================\n")

            if deleted:
                print(f"[VectorDB] Deleting {len(deleted)} embeddings")
                vector_store.delete(ids=list(deleted))

        # -----------------------------
        # CASE 2: NEW FILENAME
        # -----------------------------
        else:

            print("[VectorDB] New document name detected")

            # Fetch existing IDs from Chroma
            existing = vector_store._collection.get(include=[])
            existing_hashes = set(existing["ids"])

            added = new_hashes - existing_hashes
            deleted = set()

            print("\n========= DUPLICATE CHECK =========")
            print(f"Total paragraphs in document: {len(new_hashes)}")
            print(f"New embeddings required: {len(added)}")
            print(f"Already existing paragraphs: {len(new_hashes - added)}")
            print("===================================\n")

        # -----------------------------
        # ADD NEW EMBEDDINGS
        # -----------------------------
        if added:

            texts = [new_hash_map[h] for h in added]
            ids = list(added)
            metadatas = [{"doc": document_name, "para_hash": h} for h in added]

            print(f"[VectorDB] Adding {len(texts)} embeddings")

            vector_store.add_texts(
                texts=texts,
                ids=ids,
                metadatas=metadatas
            )


        after_count = vector_store._collection.count()

        print(f"[VectorDB] Embeddings AFTER update: {after_count}")
        print(f"[VectorDB] Net change: {after_count - before_count}")

        # -----------------------------
        # SAVE HASH FILE
        # -----------------------------
        with open(hash_path, "w") as f:
            json.dump(new_hash_map, f)

        print("\n===== CHROMA UPDATE COMPLETE =====\n")

        return "Incremental update complete"



    def retrieve(self, client_id, query, top_k):
        chroma_path, _ = self._get_vector_path(client_id)
        
        print(f"[VectorDB] Chroma Retrieval - Client: {client_id}")
        print(f"[VectorDB] Query: {query}")

        vector_store = Chroma(
            persist_directory=chroma_path,
            embedding_function=self.embedding
        )

        docs = vector_store.similarity_search(query, k=top_k)
        print(f"[VectorDB] Retrieved {len(docs)} relevant chunks from chroma db")
        return docs