import json
from models import Model

EXTRACT_PROMPT = """You are a data extraction assistant. Extract structured information from the following content.

Return ONLY valid JSON in this exact format:
{
    "entities": ["list of key entities, organizations, people mentioned"],
    "statistics": [
        {"metric": "name", "value": 0, "unit": "unit", "context": "full date with year, source, and what the number specifically measures"}
    ],
    "claims": [
        {"statement": "a key claim made", "evidence_quote": "supporting quote from text"}
    ],
    "summary": "2-3 sentence summary of this content"
}

RULES:
- Always include the FULL YEAR in any date (e.g. "September 6, 2021" not "week of Sep 6th")
- Be specific about what each metric measures — include who, what, where, when
- If the source is vague about a date or metric, note that in the context field

Content:
"""

TABLE_PROMPT = """You are a data extraction assistant. Analyze this table data and extract key statistics and insights.

Return ONLY valid JSON in the same format as above.

Table data:
"""

REDUCE_PROMPT = """You are given extractions from multiple chunks of the same document.
Consolidate into a single extraction:
- Deduplicate entities
- Merge statistics (flag contradictions)
- Keep only well-supported claims
- Write one overall document summary

Return ONLY valid JSON in the same structured format.

Chunk extractions:
"""

#map: extract key info from each chunk individually
#reduce: if combined extractions exceed token limit, recursively split and reduce groups, then merge results up the chain
#final reduce consolidates everything into one extraction, this way LLM gets full document context since the compressed extractions now fit within the token limit
#and we can handle arbitrarily long documents without losing key info or context
class Extractor:
    def __init__(self, model=None, max_tokens=2000, verbose=False):
        self.model = model or Model()
        self.max_tokens = max_tokens
        self.verbose = verbose


    # handline individual chunk
    def extract_chunk(self, chunk):
        if chunk["chunk_type"] == "table":
            prompt = TABLE_PROMPT + json.dumps(chunk["content"])
        else:
            prompt = EXTRACT_PROMPT + chunk["content"]
        return self.model.call(prompt)
    

    #go through all chunks, extract info, then reduce results
    def extract_all(self, chunks):
        extractions = []
        for i, chunk in enumerate(chunks, 1):
            if self.verbose:
                print(f"    Chunk {i}/{len(chunks)}...", end=" ", flush=True)
            result = self.extract_chunk(chunk)
            result["chunk_index"] = chunk["chunk_index"]
            extractions.append(result)
            if self.verbose:
                print("done")
        return extractions
    
    
    def _safe_call(self, prompt, retries=2):
        """Call model with retry on JSON parse errors."""
        for attempt in range(retries):
            try:
                return self.model.call(prompt)
            except json.JSONDecodeError:
                if attempt < retries - 1:
                    # Add instruction to keep response shorter
                    prompt = prompt + "\n\nIMPORTANT: Keep the JSON response concise. Limit each list to the top 10 most important items."
                else:
                    raise

    #final run through of everything, reduce document and get the final key information
    def reduce(self, extractions):
        text = json.dumps(extractions, indent=2)

        # if it fits, do the final reduce in one call
        if len(text.split()) <= self.max_tokens:
            prompt = REDUCE_PROMPT + text
            return self._safe_call(prompt)

        # too big — batch reduce: group into chunks of batch_size, reduce each group, then recurse
        batch_size = 4
        batches = [extractions[i:i+batch_size] for i in range(0, len(extractions), batch_size)]
        reduced = []
        for i, batch in enumerate(batches, 1):
            if self.verbose:
                print(f"    Reduce batch {i}/{len(batches)} ({len(batch)} items)...", end=" ", flush=True)
            batch_text = json.dumps(batch, indent=2)
            if len(batch_text.split()) <= self.max_tokens:
                prompt = REDUCE_PROMPT + batch_text
                reduced.append(self._safe_call(prompt))
            else:
                # batch still too big, halve it
                #hey divide and conquer from csci311 mentioned
                mid = len(batch) // 2
                left = self.reduce(batch[:mid])
                right = self.reduce(batch[mid:])
                reduced.append(self.reduce([left, right]))
            if self.verbose:
                print("done")

        # if we're down to one result, we're done
        if len(reduced) == 1:
            return reduced[0]

        # otherwise recurse on the reduced results
        if self.verbose:
            print(f"    Final merge of {len(reduced)} batches...")
        return self.reduce(reduced)

    def run(self, chunks):
        extractions = self.extract_all(chunks)  # map
        if self.verbose:
            print(f"  Reducing {len(extractions)} extractions...")
        consolidated = self.reduce(extractions)  # reduce
        return consolidated