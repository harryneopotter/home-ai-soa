import sys
import os

sys.path.append(os.path.join(os.getcwd(), "home_ai/soa1"))
from models import _ENDPOINTS

print(f"Nemotron model: {_ENDPOINTS['nemotron'].model_name}")
print(f"Phinance model: {_ENDPOINTS['phinance'].model_name}")
