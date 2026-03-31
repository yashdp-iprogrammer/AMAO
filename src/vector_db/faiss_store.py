import os
import json
from src.vector_db.base import BaseVectorStore
from langchain_community.vectorstores import FAISS
from transformers import logging
logging.set_verbosity_error()


class FaissVectorStore(BaseVectorStore):
    
    def __init__(self):
        super().__init__()
        self.embedding = self._get_embedding()
    
    def _get_vector_path(self, client_id):

        client_root = self._get_client_root(client_id)
        faiss_path = os.path.join(client_root, "faiss")
        
        docs_path = os.path.join(faiss_path, "hashes")
        os.makedirs(faiss_path, exist_ok=True)
        os.makedirs(docs_path, exist_ok=True)

        return faiss_path, docs_path


    # def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

    #     faiss_path, docs_path = self._get_vector_path(client_id)

    #     hash_path = os.path.join(docs_path, f"{document_name}.hashes")

    #     new_hash_map = {p["hash"]: p["text"] for p in paragraphs}

    #     if os.path.exists(hash_path):
    #         with open(hash_path, "r") as f:
    #             old_hash_map = json.load(f)
    #     else:
    #         old_hash_map = {}

    #     new_hashes = set(new_hash_map.keys())
    #     old_hashes = set(old_hash_map.keys())

    #     added = new_hashes - old_hashes
    #     deleted = old_hashes - new_hashes
        
    #     if not added and not deleted:
    #         print("[VectorDB] No document changes detected")
    #         return "No changes detected"

    #     print("\n========= DIFF SUMMARY =========")
    #     print(f"New paragraphs detected: {len(added)}")
    #     print(f"Deleted paragraphs detected: {len(deleted)}")
    #     print("================================\n")

    #     index_file = os.path.join(faiss_path, "index.faiss")

    #     vector_store = None
    #     before_count = 0

    #     if os.path.exists(index_file):
            
    #         print("[VectorDB] Loading existing FAISS index...")

    #         vector_store = FAISS.load_local(
    #             faiss_path,
    #             embeddings=self.embedding,
    #             allow_dangerous_deserialization=True
    #         )
            
    #         before_count = vector_store.index.ntotal

    #         print(f"[VectorDB] Embeddings BEFORE update: {before_count}")

    #         # if deleted:
    #         #     vector_store.delete(ids=list(deleted))
            
    #         try:
    #             print(f"[VectorDB] Stored IDs: {list(vector_store.docstore._dict.keys())}")
    #         except Exception:
    #             pass
            
    #         if deleted and vector_store:
    #             print(f"Deleting {len(deleted)} embeddings from {document_name}")
    #             vector_store.delete(ids=list(deleted))

    #     else:
    #         vector_store = None
    #         print("[VectorDB] No existing index found")


    #     if added:

    #         texts = [new_hash_map[h] for h in added]
    #         ids = list(added)
    #         metadatas = [{"doc": document_name, "para_hash": h} for h in added]

    #         if vector_store:
    #             print(f"[VectorDB] Adding {len(texts)} embeddings")
    #             vector_store.add_texts(texts=texts, ids=ids, metadatas=metadatas)

    #         else:
    #             print("[VectorDB] Creating new FAISS store")

    #             vector_store = FAISS.from_texts(
    #                 texts,
    #                 embedding=self.embedding,
    #                 ids=ids,
    #                 metadatas=metadatas
    #             )

    #     if vector_store:
    #         after_count = vector_store.index.ntotal

    #         print(f"[VectorDB] Embeddings AFTER update: {after_count}")

    #         change = after_count - before_count
    #         print(f"[VectorDB] Net embedding change: {change}")

    #         vector_store.save_local(faiss_path)

    #         print("[VectorDB] FAISS index saved successfully")

    #     with open(hash_path, "w") as f:
    #         json.dump(new_hash_map, f)
            
    #     print("\n===== FAISS UPDATE COMPLETE =====\n")

    #     return "Incremental update complete"
    
    
    def append_to_store(self, client_id: str, document_name: str, paragraphs: list):

        faiss_path, docs_path = self._get_vector_path(client_id)

        hash_path = os.path.join(docs_path, f"{document_name}.hashes")

        new_hash_map = {p["hash"]: p["text"] for p in paragraphs}
        new_hashes = set(new_hash_map.keys())

        index_file = os.path.join(faiss_path, "index.faiss")

        vector_store = None
        before_count = 0

        if os.path.exists(index_file):

            print("[VectorDB] Loading existing FAISS index...")

            vector_store = FAISS.load_local(
                faiss_path,
                embeddings=self.embedding,
                allow_dangerous_deserialization=True
            )

            before_count = vector_store.index.ntotal
            print(f"[VectorDB] Embeddings BEFORE update: {before_count}")

        else:
            print("[VectorDB] No existing index found")

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

            if deleted and vector_store:
                print(f"Deleting {len(deleted)} embeddings from {document_name}")
                vector_store.delete(ids=list(deleted))

        # -----------------------------
        # CASE 2: NEW FILENAME
        # -----------------------------
        else:

            print("[VectorDB] New document name detected")

            if vector_store:
                existing_hashes = set(vector_store.docstore._dict.keys())
            else:
                existing_hashes = set()

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

            if vector_store:
                print(f"[VectorDB] Adding {len(texts)} embeddings")
                vector_store.add_texts(texts=texts, ids=ids, metadatas=metadatas)

            else:
                print("[VectorDB] Creating new FAISS store")

                vector_store = FAISS.from_texts(
                    texts,
                    embedding=self.embedding,
                    ids=ids,
                    metadatas=metadatas
                )

        # -----------------------------
        # SAVE INDEX
        # -----------------------------
        if vector_store:

            after_count = vector_store.index.ntotal

            print(f"[VectorDB] Embeddings AFTER update: {after_count}")

            change = after_count - before_count
            print(f"[VectorDB] Net embedding change: {change}")

            vector_store.save_local(faiss_path)

            print("[VectorDB] FAISS index saved successfully")

        # -----------------------------
        # SAVE DOCUMENT STRUCTURE
        # -----------------------------
        with open(hash_path, "w") as f:
            json.dump(new_hash_map, f)

        print("\n===== FAISS UPDATE COMPLETE =====\n")

        return "Incremental update complete"


    def retrieve(self, client_id, query, top_k=5):

        faiss_path, _ = self._get_vector_path(client_id)
        index_file = os.path.join(faiss_path, "index.faiss")

        print(f"[VectorDB] Faiss Retrieval - Client: {client_id}")
        print(f"[VectorDB] Question: '{query}'")

        if not os.path.exists(index_file):
            print(f"[VectorDB] FAISS index not found for client {client_id}")
            return []

        try:

            vector_db = FAISS.load_local(
                faiss_path,
                embeddings=self.embedding,
                allow_dangerous_deserialization=True
            )

            docs = vector_db.similarity_search(query, k=top_k)

            print(f"[VectorDB] Retrieved {len(docs)} documents from faiss")
            # print("docs:", docs)

            return docs

        except Exception as e:
            print(f"[VectorDB] Error loading FAISS: {e}")
            return []
