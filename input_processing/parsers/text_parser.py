def textParser(file_path, encoding="utf-8"):
    with open(file_path, 'r', encoding=encoding) as file:
        text = file.read()
    return {
        "text": text,
        "tables": [],
        "metadata": {}
    }