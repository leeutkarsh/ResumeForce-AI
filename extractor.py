import pymupdf

def extract_resume_text(source) -> str:
    if isinstance(source, (bytes, bytearray)):
        document = pymupdf.open(stream=source, filetype="pdf")
    else:
        document = pymupdf.open(source)

    with document:
        pages = [page.get_text("text", sort=True) for page in document]
        links = dict.fromkeys(
            link["uri"]
            for page in document
            for link in page.get_links()
            if link.get("uri")
        )

    text = "\n".join(pages).strip()

    if not text:
        raise ValueError("No readable text found. The resume may be a scanned image.")

    if links:
        text += "\n\nLinks:\n" + "\n".join(links)

    return text