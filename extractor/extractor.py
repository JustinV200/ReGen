import json
from .model import Model

#map: extract key info from each chunk individually
#reduce: if combined extractions exceed token limit, recursively split and reduce groups, then merge results up the chain
#final reduce consolidates everything into one extraction, this way LLM gets full document context since the compressed extractions now fit within the token limit
#and we can handle arbitrarily long documents without losing key info or context
class Extractor:
    def __init__(self, model=None, max_tokens=3000):
        self.model = model or Model()
        self.max_tokens = max_tokens


    # handline individual chunk
    def extract_chunk(self, chunk):
        if chunk["chunk_type"] == "table":
            prompt = self.model.table_prompt + json.dumps(chunk["content"])
        else:
            prompt = self.model.extract_prompt + chunk["content"]
        return self.model.call(prompt)
    

    #go through all chunks, extract info, then reduce results
    def extract_all(self, chunks):
        extractions = []
        for chunk in chunks:
            result = self.extract_chunk(chunk)
            result["chunk_index"] = chunk["chunk_index"]
            extractions.append(result)
        return extractions
    
    
    #final run through of everything, reduce document and get the final key information
    def reduce(self, extractions):
        text = json.dumps(extractions, indent=2)

        # if it fits, do the final reduce
        if len(text.split()) <= self.max_tokens:
            prompt = self.model.reduce_prompt + text
            return self.model.call(prompt)

        # too big — split extractions into groups, reduce each group, then reduce again
        #divide and conquor algorithm to handle large documents: recursively split extractions until they fit within token limit, then merge results up the chain
        #straight from csci 311 so thats kinda cool ngl
        mid = len(extractions) // 2
        left = self.reduce(extractions[:mid])
        right = self.reduce(extractions[mid:])
        return self.reduce([left, right])

    def run(self, chunks):
        extractions = self.extract_all(chunks)  # map
        consolidated = self.reduce(extractions)  # reduce
        return consolidated