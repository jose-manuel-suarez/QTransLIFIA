import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.qutils import quirk_to_qasm

url = "https://algassert.com/quirk#circuit={%22cols%22:[[%22X%22,%22Y%22],[%22~s9d2%22],[%22Swap%22,%22Swap%22],[%22~a62g%22],[%22~q7uq%22]],%22gates%22:[{%22id%22:%22~s9d2%22,%22name%22:%22uno%22,%22circuit%22:{%22cols%22:[[%22%E2%80%A2%22,%22X%22]]}},{%22id%22:%22~a62g%22,%22name%22:%22dos%22,%22circuit%22:{%22cols%22:[[%22Swap%22,%22Swap%22,%22%E2%80%A2%22]]}},{%22id%22:%22~q7uq%22,%22name%22:%22tres%22,%22circuit%22:{%22cols%22:[[%22H%22,%22%E2%80%A2%22]]}}]}"
qasm = quirk_to_qasm(url, 0)
print(qasm)
