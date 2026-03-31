# import os
# import hashlib
# from langchain_community.document_loaders import PyPDFLoader
# from tempfile import NamedTemporaryFile


# class DocumentProcessor:

#     def _split_paragraphs(self, text: str):
#         paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
#         return paragraphs

#     def _hash_paragraph(self, document_name:str,  paragraph: str):
#         # return hashlib.sha256(paragraph.encode()).hexdigest()
#         return hashlib.sha256(f"{document_name}:{paragraph}".encode()).hexdigest()

#     async def process_file(self, document_name:str, file):

#         filename = file.filename.lower()

#         if filename.endswith(".txt"):
#             content = await file.read()

#             try:
#                 text = content.decode("utf-8")
#             except UnicodeDecodeError:
#                 text = content.decode("latin-1")

#         elif filename.endswith(".pdf"):

#             with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
#                 tmp.write(await file.read())
#                 tmp_path = tmp.name

#             loader = PyPDFLoader(tmp_path)
#             pages = loader.load()

#             text = "\n".join([page.page_content for page in pages])

#             os.remove(tmp_path)

#         else:
#             raise ValueError("Unsupported file type")

#         paragraphs = self._split_paragraphs(text)

#         results = []
#         for para in paragraphs:
#             para_hash = self._hash_paragraph(document_name, para)
#             results.append({
#                 "text": para,
#                 "hash": para_hash
#             })

#         return results


import os
import re
import hashlib
import pymupdf  # PyMuPDF
from tempfile import NamedTemporaryFile

class DocumentProcessor:

    def _clean_text(self, text: str):
        """Removes internal newlines and extra whitespace for hash stability."""
        # Replace newlines with spaces, then collapse multiple spaces into one
        return " ".join(text.replace("\n", " ").split()).strip()


    def _hash_paragraph(self, document_name: str, paragraph: str):
        # We hash the cleaned paragraph salted with the document name
        # return hashlib.sha256(f"{document_name}:{paragraph}".encode()).hexdigest()
        return hashlib.sha256(paragraph.encode()).hexdigest()
    
    
    def _is_reference_heading(self, text: str):
        """Detects headings like 'References', 'Bibliography', etc."""
        text = text.lower().strip()

        return text in [
            "references",
            "bibliography",
            "reference",
            "works cited",
            "literature cited"
        ]


    def _looks_like_reference(self, text: str):
        """Detects numbered bibliography entries."""

        text = text.strip()

        # [1] Author ...
        if re.match(r"^\[\d+\]\s+", text):
            return True

        # 1. Author ...
        if re.match(r"^\d+\.\s+[A-Z]", text):
            return True

        # 1) Author ...
        if re.match(r"^\d+\)\s+[A-Z]", text):
            return True

        return False
    

    async def process_file(self, document_name: str, file):
        filename = file.filename.lower()
        results = []

        if filename.endswith(".txt"):
            content = await file.read()
            try:
                text = content.decode("utf-8")
            except UnicodeDecodeError:
                text = content.decode("latin-1")
            
            # For TXT, we still rely on double newlines as the "block" separator
            paragraphs = [p.strip() for p in text.split("\n\n") if p.strip()]
            for para in paragraphs:
                clean_para = self._clean_text(para)
                results.append({
                    "text": clean_para,
                    "hash": self._hash_paragraph(document_name, clean_para)
                })

        # elif filename.endswith(".pdf"):
        #     # FastAPI UploadFile needs to be written to a temp file for PyMuPDF to open
        #     with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
        #         tmp.write(await file.read())
        #         tmp_path = tmp.name

        #     try:
        #         doc = pymupdf.open(tmp_path)
        #         for page in doc:
        #             # 'blocks' returns (x0, y0, x1, y1, "text", block_no, block_type)
        #             blocks = page.get_text("blocks")
        #             for b in blocks:
        #                 text = b[4].strip()
        #                 block_type = b[6]  # 0 is text, 1 is image
                        
        #                 # Filter out images and very short noise (like page numbers)
        #                 if block_type == 0 and len(text) > 5:
        #                     clean_para = self._clean_text(text)
        #                     print("clean doc", clean_para)
        #                     results.append({
        #                         "text": clean_para,
        #                         "hash": self._hash_paragraph(document_name, clean_para)
        #                     })
        #         doc.close()
        #     finally:
        #         if os.path.exists(tmp_path):
        #             os.remove(tmp_path)
        
        elif filename.endswith(".pdf"):

            with NamedTemporaryFile(delete=False, suffix=".pdf") as tmp:
                tmp.write(await file.read())
                tmp_path = tmp.name

            # try:
            #     doc = pymupdf.open(tmp_path)

            #     for page in doc:

            #         blocks = page.get_text("blocks")

            #         # sort blocks by vertical position
            #         blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

            #         paragraph_buffer = ""
            #         prev_bottom = None

            #         for b in blocks:

            #             x0, y0, x1, y1, text, _, block_type = b

            #             if block_type != 0:
            #                 continue

            #             text = text.strip()

            #             if len(text) < 5:
            #                 continue

            #             clean_text = self._clean_text(text)

            #             if prev_bottom is None:
            #                 paragraph_buffer = clean_text
            #                 prev_bottom = y1
            #                 continue

            #             vertical_gap = y0 - prev_bottom

            #             # threshold determines paragraph break
            #             if vertical_gap > 10:
            #                 clean_para = self._clean_text(paragraph_buffer)

            #                 results.append({
            #                     "text": clean_para,
            #                     "hash": self._hash_paragraph(document_name, clean_para)
            #                 })

            #                 print("clean doc", clean_para)

            #                 paragraph_buffer = clean_text
            #             else:
            #                 paragraph_buffer += " " + clean_text

            #             prev_bottom = y1

            #         if paragraph_buffer:
            #             clean_para = self._clean_text(paragraph_buffer)

            #             results.append({
            #                 "text": clean_para,
            #                 "hash": self._hash_paragraph(document_name, clean_para)
            #             })

            #             print("clean doc", clean_para)

            #     doc.close()

            # finally:
            #     if os.path.exists(tmp_path):
            #         os.remove(tmp_path)
            
            try:
                doc = pymupdf.open(tmp_path)

                current_heading = None
                
                reference_heading_seen = False
                reference_streak = 0
                REFERENCE_THRESHOLD = 3

                for page in doc:

                    blocks = page.get_text("blocks")

                    # sort blocks by vertical position
                    blocks = sorted(blocks, key=lambda b: (b[1], b[0]))

                    paragraph_buffer = ""
                    prev_bottom = None

                    for b in blocks:

                        x0, y0, x1, y1, text, _, block_type = b

                        if block_type != 0:
                            continue

                        text = text.strip()

                        if len(text) < 5:
                            continue
                        
                        if "©" in text:
                            continue

                        clean_text = self._clean_text(text)
                        
                        # ---------- REFERENCE HEADING DETECTION ----------

                        if self._is_reference_heading(clean_text):
                            reference_heading_seen = True
                            reference_streak = 0
                            paragraph_buffer = ""
                            continue
                        
                        # ---------- REFERENCE ENTRY DETECTION ----------

                        if reference_heading_seen:

                            if self._looks_like_reference(clean_text):
                                reference_streak += 1
                            else:
                                reference_streak = 0

                            if reference_streak >= REFERENCE_THRESHOLD:
                                print("Reference section detected. Stopping ingestion.")
                                break

                        # ---------- REMOVE PAGE NUMBERS ----------
                        if re.match(r"^(page\s*\d+|\d+)$", clean_text.lower()):
                            continue

                        # calculate vertical gap first
                        if prev_bottom is None:
                            vertical_gap = 0
                        else:
                            vertical_gap = y0 - prev_bottom

                        # ---------- HEADING DETECTION ----------
                        is_heading = (
                            len(clean_text.split()) <= 6
                            and len(clean_text) < 60
                            and not clean_text.endswith(".")
                            and vertical_gap > 15
                        )

                        if is_heading and current_heading is None:
                            current_heading = clean_text
                            continue

                        # ---------- PARAGRAPH BUILDING ----------
                        if prev_bottom is None:
                            paragraph_buffer = clean_text
                            prev_bottom = y1
                            continue

                        vertical_gap = y0 - prev_bottom

                        if vertical_gap > 10:

                            clean_para = self._clean_text(paragraph_buffer)
                            
                            if current_heading:
                                final_text = f"{current_heading}: {clean_para}"
                                current_heading = None  # reset after using
                            else:
                                final_text = clean_para

                            results.append({
                                "text": final_text,
                                "hash": self._hash_paragraph(document_name, final_text)
                            })

                            print("clean doc", final_text)

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

                        print("clean doc", final_text)
                        
                    if reference_streak >= REFERENCE_THRESHOLD:
                        break

                doc.close()

            finally:
                if os.path.exists(tmp_path):
                    os.remove(tmp_path)

        else:
            raise ValueError("Unsupported file type")

        return results
    
    
document_processor = DocumentProcessor()