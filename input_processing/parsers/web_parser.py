import trafilatura

def webParser(file_path):
    with open(file_path, 'r', encoding='utf-8') as f:
        raw_html = f.read()
    text = trafilatura.extract(raw_html)
    metadata = trafilatura.bare_extraction(raw_html)
    return {
        "text": text,
        "tables": [],
        "metadata": {
            "title": metadata.get("title", ""),
            "author": metadata.get("author", ""),
            "date": metadata.get("date", ""),
            "sitename": metadata.get("sitename", ""),
        } if metadata else {}
    }