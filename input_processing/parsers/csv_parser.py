import pandas as pd

def csvParser(file_path, encoding="utf-8"):
    df = pd.read_csv(file_path, encoding=encoding)
    text = df.to_string(index=False)
    tables = [df.to_dict(orient="records")]
    metadata = {
        "num_rows": len(df),
        "num_columns": len(df.columns),
        "columns": list(df.columns)
    }
    return {
        "text": text,
        "tables": tables,
        "metadata": metadata
    }