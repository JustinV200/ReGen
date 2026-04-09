def chunker(parsed_data, chunk_size=1500, overlap=200):
    text = parsed_data.get("text", "")
    tables = parsed_data.get("tables", [])
    metadata = parsed_data.get("metadata", {})

    chunks = []
    chunk_index = 0

    # Split text on paragraphs, then accumulate into chunks
    paragraphs = text.split("\n\n")
    current_chunk = ""

    for para in paragraphs:
        # if adding this paragraph would exceed chunk size, emit current chunk
        if len(current_chunk.split()) + len(para.split()) > chunk_size and current_chunk:
            chunks.append({
                "chunk_index": chunk_index,
                "chunk_type": "text",
                "content": current_chunk.strip(),
                "metadata": metadata
            })
            chunk_index += 1
            # overlap: keep the last ~overlap words
            words = current_chunk.split()
            current_chunk = " ".join(words[-overlap:]) + "\n\n"

        current_chunk += para + "\n\n"

    #last chunk
    if current_chunk.strip():
        chunks.append({
            "chunk_index": chunk_index,
            "chunk_type": "text",
            "content": current_chunk.strip(),
            "metadata": metadata
        })
        chunk_index += 1

    # each table is its own chunk
    for table in tables:
        chunks.append({
            "chunk_index": chunk_index,
            "chunk_type": "table",
            "content": table,
            "metadata": metadata
        })
        chunk_index += 1

    return chunks