import json
import os
from litellm import completion

class Model:
    def __init__(self, model_name="gpt-3.5-turbo"):
        self.model_name = model_name

    def call(self, prompt):
        response = completion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        return json.loads(response.choices[0].message.content)
    
    def call_raw(self, prompt):
        response = completion(
            model=self.model_name,
            messages=[{"role": "user", "content": prompt}]
        )
        return response.choices[0].message.content