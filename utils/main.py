import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.qutils import quirk_to_qasm, parse_quirk_url, quirk_circuit_info, encode_quirk_url


url = "https://algassert.com/quirk#circuit={%22cols%22:[[%22~hseh%22],[1,%22%E2%80%A2%22,%22~cu10000%22],[%22%E2%80%A2%22,1,%22~cu10001%22],[%22H%22],[%22%E2%80%A2%22,%22Z^-%C2%BD%22],[1,%22H%22],[%22Measure%22],[1,%22Measure%22],[1,1,%22Measure%22]],%22gates%22:[{%22id%22:%22~cu10000%22,%22name%22:%22cu1(pi%20/%20512)%22,%22matrix%22:%22{{1,0},{0,0.9999811753+0.006135884649i}}%22},{%22id%22:%22~cu10001%22,%22name%22:%22cu1(pi%20/%20256)%22,%22matrix%22:%22{{1,0},{0,0.9999247018+0.01227153829i}}%22},{%22id%22:%22~hseh%22,%22circuit%22:{%22cols%22:[[%22H%22],[1,%22H%22]]}}]}"

qasm = quirk_to_qasm(url, 0)
print(qasm)
