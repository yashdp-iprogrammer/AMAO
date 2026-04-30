import os
import re
import json
import asyncio
import hashlib
import pymupdf
import pytesseract
from pdf2image import convert_from_path
from tempfile import NamedTemporaryFile
from src.utils.logger import logger


class DocumentProcessor:

    # ---------------- HASH STORE HELPERS ---------------- #

    def _get_hash_store_path(self, client_id: str, vector_db: str):
        return f"src/vector_stores/client_id_{client_id}/{vector_db}/file_hashes.json"

    def _load_hash_store(self, client_id: str, vector_db: str):
        logger.info(f"Loading hash store for client={client_id}, db={vector_db}")
        path = self._get_hash_store_path(client_id, vector_db)

        if not os.path.exists(path):
            return {}

        try:
            with open(path, "r") as f:
                content = f.read().strip()
                return json.loads(content) if content else {}
        except json.JSONDecodeError:
            logger.warning("Corrupted hash store. Resetting...")
            return {}

    def _save_hash_store(self, client_id: str, vector_db: str, data: dict):
        logger.info(f"Saving hash store for client={client_id}, db={vector_db}")
        path = self._get_hash_store_path(client_id, vector_db)

        os.makedirs(os.path.dirname(path), exist_ok=True)

        temp_path = path + ".tmp"

        with open(temp_path, "w") as f:
            json.dump(data, f)

        os.replace(temp_path, path)

    def _compute_file_hash(self, file_bytes: bytes):
        return hashlib.sha256(file_bytes).hexdigest()

    # ---------------- TEXT HELPERS ---------------- #

    def _clean_text(self, text: str):
        return " ".join(text.replace("\n", " ").split()).strip()

    def _hash_paragraph(self, document_name: str, paragraph: str):
        return hashlib.sha256(paragraph.encode()).hexdigest()

    def _is_reference_heading(self, text: str):
        text = text.lower().strip()
        return text in [
            "references",
            "bibliography",
            "reference",
            "works cited",
            "literature cited"
        ]

    def _looks_like_reference(self, text: str):
        text = text.strip()

        if re.match(r"^\[\d+\]\s+", text):
            return True
        if re.match(r"^\d+\.\s+[A-Z]", text):
            return True
        if re.match(r"^\d+\)\s+[A-Z]", text):
            return True

        return False

    # ---------------- OCR ---------------- #

    def _ocr_page(self, file_path: str, page_number: int):
        logger.info(f"OCR processing page {page_number}")
        images = convert_from_path(
            file_path,
            first_page=page_number,
            last_page=page_number
        )
        return pytesseract.image_to_string(images[0])

    
    def _is_low_text(self, text: str, page_number: int = None) -> bool:
        """
        Production-grade OCR decision engine.
        Returns True → OCR needed
        """

        if not text:
            logger.info(f"Page {page_number}: Empty text → OCR")
            return True

        text = text.strip()

        score = 0
        reasons = []

        # ---------------- SIGNAL 1: TEXT LENGTH ---------------- #
        if len(text) < 30:
            score += 2
            reasons.append("LOW_TEXT")

        # ---------------- SIGNAL 2: WEIRD CHAR RATIO ---------------- #
        weird_chars = sum(
            1 for c in text if not c.isalnum() and not c.isspace()
        )
        weird_ratio = weird_chars / max(len(text), 1)

        if weird_ratio > 0.3:
            score += 1
            reasons.append("HIGH_NOISE")

        # ---------------- SIGNAL 3: WORD QUALITY ---------------- #
        words = text.split()
        valid_words = [w for w in words if w.isalpha() and len(w) > 2]

        word_ratio = len(valid_words) / max(len(words), 1)

        if word_ratio < 0.5:
            score += 1
            reasons.append("LOW_WORD_QUALITY")

        # ---------------- SIGNAL 4: AVG WORD LENGTH ---------------- #
        avg_word_len = (
            sum(len(w) for w in words) / max(len(words), 1)
            if words else 0
        )

        if avg_word_len < 3:
            score += 1
            reasons.append("SHORT_WORDS")

        # ---------------- FINAL DECISION ---------------- #
        needs_ocr = score >= 2

        logger.info({
            "page": page_number,
            "ocr": needs_ocr,
            "score": score,
            "reasons": reasons,
            "text_length": len(text),
            "weird_ratio": round(weird_ratio, 3),
            "word_ratio": round(word_ratio, 3),
            "avg_word_len": round(avg_word_len, 2)
        })

        return needs_ocr

    # ---------------- MAIN ---------------- #

    async def process_file(self, client_id: str, vector_db: str, document_name: str, file):

        filename = file.filename.lower()
        logger.info(f"Processing file: {document_name} for client: {client_id}")

        file_bytes = await file.read()

        # ⚠️ Reset pointer for downstream use
        file.file.seek(0)

        file_hashes = self._load_hash_store(client_id, vector_db)

        file_hash = self._compute_file_hash(file_bytes)

        if file_hash in file_hashes:
            logger.info(f"Skipping already processed file: {document_name}")
            return None

        results = []
        ocr_used = False

        # ---------------- TXT ---------------- #
        if filename.endswith(".txt"):
            logger.info(f"TXT file detected: {document_name}")

            try:
                text = file_bytes.decode("utf-8")
            except UnicodeDecodeError:
                logger.warning(f"UTF-8 decode failed, using latin-1 for {document_name}")
                text = file_bytes.decode("latin-1")

            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]

            for para in paragraphs:
                clean_para = self._clean_text(para)
                results.append({
                    "text": clean_para,
                    "hash": self._hash_paragraph(document_name, clean_para)
                })

        # ---------------- PDF ---------------- #
        elif filename.endswith(".pdf"):
            logger.info(f"PDF file detected: {document_name}")

            with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(file_bytes)
                tmp_path = tmp.name

            try:
                doc = pymupdf.open(tmp_path)

                current_heading = None
                reference_heading_seen = False
                reference_streak = 0
                REFERENCE_THRESHOLD = 3

                # -------------------------
                # PASS 1: DETECT OCR PAGES
                # -------------------------
                ocr_pages = []
                page_text_map = {}

                for page_index, page in enumerate(doc, start=1):
                    raw_text = page.get_text()
                    page_text_map[page_index] = raw_text

                    if self._is_low_text(raw_text, page_index):
                        ocr_pages.append(page_index)

                # -------------------------
                # PASS 2: PARALLEL OCR
                # -------------------------
                ocr_map = {}

                if ocr_pages:
                    ocr_used = True
                    logger.info(f"Running parallel OCR for {len(ocr_pages)} pages")

                    semaphore = asyncio.Semaphore(4)  # limit concurrency

                    async def run_ocr(page_num):
                        async with semaphore:
                            return await asyncio.to_thread(self._ocr_page, tmp_path, page_num)

                    tasks = [run_ocr(p) for p in ocr_pages]
                    results_ocr = await asyncio.gather(*tasks)

                    ocr_map = dict(zip(ocr_pages, results_ocr))

                # -------------------------
                # PASS 3: NORMAL PROCESSING
                # -------------------------
                for page_index, page in enumerate(doc, start=1):

                    logger.info(f"Processing page {page_index} of {document_name}")

                    # Use OCR result if exists
                    if page_index in ocr_map:
                        logger.info(f"OCR applied on page {page_index} for {document_name}")
                        raw_text = ocr_map[page_index]

                        paragraphs = [
                            p.strip() for p in raw_text.split("\n\n") if p.strip()
                        ]

                        for para in paragraphs:
                            clean_para = self._clean_text(para)
                            results.append({
                                "text": clean_para,
                                "hash": self._hash_paragraph(document_name, clean_para)
                            })

                        continue

                    # ---------------- NORMAL PIPELINE ---------------- #

                    blocks = page.get_text("blocks")
                    blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

                    paragraph_buffer = ""
                    prev_bottom = None

                    for b in blocks:

                        x0, y0, x1, y1, text, _, block_type = b

                        if block_type != 0:
                            continue

                        text = text.strip()

                        if len(text) < 5 or "©" in text:
                            continue

                        clean_text = self._clean_text(text)

                        # REFERENCES
                        if self._is_reference_heading(clean_text):
                            logger.info(f"Reference section started in {document_name}")
                            reference_heading_seen = True
                            reference_streak = 0
                            paragraph_buffer = ""
                            continue

                        if reference_heading_seen:

                            if self._looks_like_reference(clean_text):
                                reference_streak += 1
                            else:
                                reference_streak = 0

                            if reference_streak >= REFERENCE_THRESHOLD:
                                logger.info(f"Reference section detected, stopping ingestion for {document_name}")
                                break

                        # PAGE NUMBERS
                        if re.match(r"^(page\s*\d+|\d+)$", clean_text.lower()):
                            continue

                        # GAP
                        if prev_bottom is None:
                            vertical_gap = 0
                        else:
                            vertical_gap = y0 - prev_bottom

                        # HEADING
                        is_heading = (
                            len(clean_text.split()) <= 6
                            and len(clean_text) < 60
                            and not clean_text.endswith(".")
                            and vertical_gap > 15
                        )

                        if is_heading and current_heading is None:
                            current_heading = clean_text
                            continue

                        # PARAGRAPH
                        if prev_bottom is None:
                            paragraph_buffer = clean_text
                            prev_bottom = y1
                            continue

                        vertical_gap = y0 - prev_bottom

                        if vertical_gap > 10:

                            clean_para = self._clean_text(paragraph_buffer)

                            if current_heading:
                                final_text = f"{current_heading}: {clean_para}"
                                current_heading = None
                            else:
                                final_text = clean_para

                            results.append({
                                "text": final_text,
                                "hash": self._hash_paragraph(document_name, final_text)
                            })

                            paragraph_buffer = clean_text

                        else:
                            paragraph_buffer += " " + clean_text

                        prev_bottom = y1

                    if paragraph_buffer and reference_streak < REFERENCE_THRESHOLD:

                        clean_para = self._clean_text(paragraph_buffer)

                        if current_heading:
                            final_text = f"{current_heading}: {clean_para}"
                        else:
                            final_text = clean_para

                        results.append({
                            "text": final_text,
                            "hash": self._hash_paragraph(document_name, final_text)
                        })

                    if reference_streak >= REFERENCE_THRESHOLD:
                        break

                doc.close()

            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        else:
            logger.warning(f"Unsupported file type: {document_name}")
            raise ValueError("Unsupported file type")

        if ocr_used:
            logger.info(f"Storing hash (OCR file): {document_name}")
            file_hashes[file_hash] = document_name
            self._save_hash_store(client_id, vector_db, file_hashes)
        else:
            logger.info(f"Skipping hash store (non-OCR file): {document_name}")

        logger.info(f"Completed processing file: {document_name}, chunks: {len(results)}")

        return results


document_processor = DocumentProcessor()