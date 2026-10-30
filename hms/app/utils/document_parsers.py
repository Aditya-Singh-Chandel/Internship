import io
import re
from typing import List, Dict, Any, Optional
import pypdf
import docx
import openpyxl

def parse_pdf(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses a PDF file from bytes using pypdf.
    Returns a list of dicts: [{"page": 1, "text": "..."}]
    """
    results = []
    reader = pypdf.PdfReader(io.BytesIO(file_bytes))
    for idx, page in enumerate(reader.pages, start=1):
        try:
            page_text = page.extract_text() or ""
            cleaned = _clean_text(page_text)
            if cleaned:
                results.append({"page": idx, "text": cleaned})
        except Exception:
            continue

    if not results:
        raise ValueError("The provided PDF contains no extractable text or is empty/scanned.")
    return results


def parse_docx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses a Word (.docx) file from bytes using python-docx.
    Extracts paragraphs, headers, and structured tables.
    Returns a list of dicts: [{"section": "content", "text": "..."}]
    """
    doc = docx.Document(io.BytesIO(file_bytes))
    sections = []

    # 1. Paragraphs
    paragraph_texts = []
    for p in doc.paragraphs:
        txt = p.text.strip()
        if txt:
            paragraph_texts.append(txt)

    if paragraph_texts:
        sections.append({
            "section": "body",
            "text": _clean_text("\n\n".join(paragraph_texts))
        })

    # 2. Tables
    for t_idx, table in enumerate(doc.tables, start=1):
        headers = []
        table_rows = []
        for r_idx, row in enumerate(table.rows):
            cells = [cell.text.strip().replace("\n", " ") for cell in row.cells]
            if r_idx == 0:
                headers = cells
            else:
                if headers and len(headers) == len(cells):
                    row_str = " | ".join(f"{h}: {c}" for h, c in zip(headers, cells) if c)
                else:
                    row_str = " | ".join(c for c in cells if c)
                if row_str:
                    table_rows.append(row_str)

        if table_rows:
            sections.append({
                "section": f"table_{t_idx}",
                "text": _clean_text("\n".join(table_rows))
            })

    if not sections:
        raise ValueError("The provided Word document contains no readable text or tables.")
    return sections


def parse_xlsx(file_bytes: bytes) -> List[Dict[str, Any]]:
    """
    Parses an Excel spreadsheet (.xlsx, .xls) from bytes using openpyxl.
    Converts tabular rows into descriptive semantic statements.
    Returns a list of dicts: [{"sheet": "Sheet1", "text": "..."}]
    """
    wb = openpyxl.load_workbook(io.BytesIO(file_bytes), data_only=True)
    sheets_data = []

    for sheet_name in wb.sheetnames:
        sheet = wb[sheet_name]
        headers = []
        sheet_rows = []

        for r_idx, row in enumerate(sheet.iter_rows(values_only=True), start=1):
            row_vals = [str(v).strip() if v is not None else "" for v in row]
            if not any(row_vals):
                continue

            if not headers:
                # First non-empty row serves as header
                headers = row_vals
            else:
                pairs = []
                for h, val in zip(headers, row_vals):
                    if val and h:
                        pairs.append(f"{h}: {val}")
                    elif val:
                        pairs.append(val)
                if pairs:
                    sheet_rows.append(" | ".join(pairs))

        if sheet_rows:
            sheets_data.append({
                "sheet": sheet_name,
                "text": f"--- Sheet: {sheet_name} ---\n" + "\n".join(sheet_rows)
            })

    if not sheets_data:
        raise ValueError("The provided Excel spreadsheet contains no valid tabular data.")
    return sheets_data


def parse_text_file(file_bytes: bytes) -> str:
    """
    Decodes raw text/markdown file bytes to a cleaned string.
    """
    for encoding in ("utf-8", "utf-8-sig", "latin-1", "cp1252"):
        try:
            raw = file_bytes.decode(encoding)
            cleaned = _clean_text(raw)
            if cleaned:
                return cleaned
        except UnicodeDecodeError:
            continue
    raise ValueError("Unable to decode text file. Ensure it is UTF-8 or standard ASCII text.")


def _clean_text(text: str) -> str:
    """
    Removes excessive whitespace, null bytes, and normalizes line breaks.
    """
    text = text.replace("\x00", " ")
    text = re.sub(r"\r\n", "\n", text)
    text = re.sub(r"[ \t]+", " ", text)
    text = re.sub(r"\n{3,}", "\n\n", text)
    return text.strip()


def chunk_text(
    text: str,
    metadata: Optional[Dict[str, Any]] = None,
    chunk_size: int = 600,
    chunk_overlap: int = 80
) -> List[Dict[str, Any]]:
    """
    Structure-aware semantic chunking.
    Splits text along paragraphs and sentences, aiming for chunks around `chunk_size` characters,
    preserving overlapping context between adjacent chunks.
    """
    if not text or not text.strip():
        return []

    base_meta = metadata or {}
    text = _clean_text(text)

    # If the text is already short enough, return as a single chunk
    if len(text) <= chunk_size:
        return [{
            "chunk_index": 0,
            "content": text,
            "metadata": base_meta
        }]

    # Split into paragraphs
    paragraphs = text.split("\n\n")
    units: List[str] = []

    for para in paragraphs:
        para = para.strip()
        if not para:
            continue
        if len(para) <= chunk_size:
            units.append(para)
        else:
            # Paragraph is too long: split by sentence
            sentences = re.split(r"(?<=[.!?])\s+", para)
            current_sentence_group = []
            current_len = 0
            for sent in sentences:
                sent = sent.strip()
                if not sent:
                    continue
                if current_len + len(sent) > chunk_size and current_sentence_group:
                    units.append(" ".join(current_sentence_group))
                    current_sentence_group = [sent]
                    current_len = len(sent)
                else:
                    current_sentence_group.append(sent)
                    current_len += len(sent)
            if current_sentence_group:
                units.append(" ".join(current_sentence_group))

    chunks: List[Dict[str, Any]] = []
    current_chunk = ""
    chunk_idx = 0

    for unit in units:
        if not current_chunk:
            current_chunk = unit
        elif len(current_chunk) + len(unit) + 2 <= chunk_size:
            current_chunk += "\n\n" + unit
        else:
            # Save current chunk
            chunks.append({
                "chunk_index": chunk_idx,
                "content": current_chunk.strip(),
                "metadata": base_meta
            })
            chunk_idx += 1

            # Prepare overlap
            if chunk_overlap > 0 and len(current_chunk) > chunk_overlap:
                overlap_seed = current_chunk[-chunk_overlap:].strip()
                # Find start of a word
                first_space = overlap_seed.find(" ")
                if first_space != -1:
                    overlap_seed = overlap_seed[first_space:].strip()
                current_chunk = overlap_seed + "\n\n" + unit
            else:
                current_chunk = unit

    if current_chunk.strip():
        chunks.append({
            "chunk_index": chunk_idx,
            "content": current_chunk.strip(),
            "metadata": base_meta
        })

    return chunks
