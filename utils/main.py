import os
import sys

sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from utils.qutils import quirk_to_qasm, parse_quirk_url, quirk_circuit_info, encode_quirk_url


url = "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"•\",1,1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"•\",\"~16c9\"],[1,\"H\"],[\"•\",1,\"~gf1o\"],[1,\"•\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,√½-√½i}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"},{\"id\":\"~rvcr\",\"name\":\"MultiX\",\"circuit\":{\"cols\":[[\"•\",\"•\",\"X\",\"•\"]]}}]}"
qasm = quirk_to_qasm(url, 0)
print(qasm)
