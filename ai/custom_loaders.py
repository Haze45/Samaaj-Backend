"""
Custom document loaders for DOCX and PPTX files.

Uses python-docx and python-pptx directly instead of LangChain's
built-in loaders, because:
  - python-docx preserves table structure (rows/columns) properly,
    whereas docx2txt flattens everything into plain text and loses
    table layout — important for community documents like fee
    schedules, rule tables, etc.
  - python-pptx gives full control over reading text from every
    shape on every slide, including text boxes and tables.

Both loaders return a list of langchain_core.documents.Document
objects, exactly like LangChain's built-in loaders, so they plug
into the same RecursiveCharacterTextSplitter pipeline used for PDFs.
"""

from docx import Document as DocxDocument
from pptx import Presentation
from langchain_core.documents import Document


def load_docx(file_path: str) -> list[Document]:
    """
    Load a .docx file using python-docx.
    Extracts paragraphs AND tables (preserving row structure).
    Returns one Document per "page" — since .docx has no real page
    breaks, the whole file is treated as a single page (page 1),
    matching the metadata shape used by PyPDFLoader.
    """
    docx_file = DocxDocument(file_path)
    text_parts = []

    # Walk through the document body in order, extracting both
    # paragraphs and tables as they appear
    for element in docx_file.element.body:
        tag = element.tag.split("}")[-1]  # strip XML namespace

        if tag == "p":
            # Find the matching paragraph object by text content
            for para in docx_file.paragraphs:
                if para._element is element and para.text.strip():
                    text_parts.append(para.text.strip())
                    break

        elif tag == "tbl":
            # Find the matching table object and render as readable rows
            for table in docx_file.tables:
                if table._element is element:
                    text_parts.append(_table_to_text(table))
                    break

    full_text = "\n\n".join(text_parts)

    return [Document(
        page_content=full_text,
        metadata={"page": 0}
    )]


def _table_to_text(table) -> str:
    """
    Converts a python-docx Table object into readable pipe-separated text,
    preserving the row/column structure so the LLM can understand
    tabular data like fee schedules or rule matrices.
    """
    rows_text = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows_text.append(" | ".join(cells))
    return "\n".join(rows_text)


def load_pptx(file_path: str) -> list[Document]:
    """
    Load a .pptx file using python-pptx.
    Extracts text from every shape (text boxes, titles, bullet points)
    and every table on every slide.
    Returns one Document per slide, with metadata["page"] set to the
    slide number — so source citations can reference "Slide 3" etc.
    """
    prs = Presentation(file_path)
    documents = []

    for slide_num, slide in enumerate(prs.slides, start=1):
        slide_text_parts = []

        for shape in slide.shapes:
            # Regular text boxes, titles, bullet points
            if shape.has_text_frame:
                for paragraph in shape.text_frame.paragraphs:
                    text = "".join(run.text for run in paragraph.runs).strip()
                    if text:
                        slide_text_parts.append(text)

            # Tables on the slide
            if shape.has_table:
                slide_text_parts.append(_pptx_table_to_text(shape.table))

        slide_text = "\n".join(slide_text_parts)

        if slide_text.strip():
            documents.append(Document(
                page_content=slide_text,
                metadata={"page": slide_num}
            ))

    return documents


def _pptx_table_to_text(table) -> str:
    """
    Converts a python-pptx Table object into readable pipe-separated text.
    """
    rows_text = []
    for row in table.rows:
        cells = [cell.text.strip() for cell in row.cells]
        rows_text.append(" | ".join(cells))
    return "\n".join(rows_text)