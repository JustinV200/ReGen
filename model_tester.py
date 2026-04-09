# test_api.py
from dotenv import load_dotenv
load_dotenv()
from extractor.model import Model

model = Model()
result = model.call("Extract info from this as json: The WHO reported a 3.2% mortality rate in 2025.")
print(result)