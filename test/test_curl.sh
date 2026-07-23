#!/bin/bash
# ============================================================
# Curl tests for Quirk Translator - IBM y AWS
# Endpoints: /code/ibm, /code/ibm/individual, /code/aws, /code/aws/individual
# Base URL: http://localhost:8081
# ============================================================

BASE="http://localhost:8081"

echo "===== 1. IBM Individual: Shor (d=0) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"•\",\"X\"],[1,\"X\",\"•\"],[1,\"•\",\"X\"],[1,1,\"•\",\"X\"],[1,1,\"X\",\"•\"],[1,1,\"•\",\"X\"],[\"•\",1,1,\"X\"],[\"X\",1,1,\"•\"],[\"•\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 2. IBM Individual: BernsteinVazirani (d=1) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 3. IBM Individual: Grover (d=2) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n===== 4. IBM Individual: DeutschJozsa (d=0) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 5. IBM Individual: Simon (d=1) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,1,\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,\"•\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 6. IBM Individual: TSP (d=2) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"•\"],[\"X\",1,\"•\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n===== 7. IBM Individual: Teleportation (d=0) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 8. IBM Individual: PhaseEstimation (d=1) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"•\",1,1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"•\",\"~16c9\"],[1,\"H\"],[\"•\",1,\"~gf1o\"],[1,\"•\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,√½-√½i}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 9. IBM Individual: QFT (d=2) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n===== 10. IBM Individual: QAOA (d=0) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 11. IBM Individual: Kickback (d=1) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"•\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 12. IBM Individual: FullAdder (d=2) ====="
curl -s -X POST "$BASE/code/ibm/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",\"•\",1,\"X\"],[\"•\",\"X\"],[1,\"•\",\"•\",\"X\"],[1,\"•\",\"X\"],[\"•\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n\n========================================"
echo "     AWS INDIVIDUAL ENDPOINTS"
echo "========================================"

echo -e "\n===== 13. AWS Individual: Shor (d=0) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"•\",\"X\"],[1,\"X\",\"•\"],[1,\"•\",\"X\"],[1,1,\"•\",\"X\"],[1,1,\"X\",\"•\"],[1,1,\"•\",\"X\"],[\"•\",1,1,\"X\"],[\"X\",1,1,\"•\"],[\"•\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 14. AWS Individual: BernsteinVazirani (d=1) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 15. AWS Individual: Grover (d=2) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n===== 16. AWS Individual: DeutschJozsa (d=0) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 17. AWS Individual: Simon (d=1) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,1,\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,\"•\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 18. AWS Individual: TSP (d=2) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"•\"],[\"X\",1,\"•\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n===== 19. AWS Individual: Teleportation (d=0) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 20. AWS Individual: PhaseEstimation (d=1) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"•\",1,1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"•\",\"~16c9\"],[1,\"H\"],[\"•\",1,\"~gf1o\"],[1,\"•\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,√½-√½i}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 21. AWS Individual: QFT (d=2) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n===== 22. AWS Individual: QAOA (d=0) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
    "d": 0
  }' | python -m json.tool

echo -e "\n===== 23. AWS Individual: Kickback (d=1) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"•\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
    "d": 1
  }' | python -m json.tool

echo -e "\n===== 24. AWS Individual: FullAdder (d=2) ====="
curl -s -X POST "$BASE/code/aws/individual" \
  -H "Content-Type: application/json" \
  -d '{
    "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",\"•\",1,\"X\"],[\"•\",\"X\"],[1,\"•\",\"•\",\"X\"],[1,\"•\",\"X\"],[\"•\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}",
    "d": 2
  }' | python -m json.tool

echo -e "\n\n========================================"
echo "     BATCH ENDPOINTS"
echo "========================================"

echo -e "\n===== 25. IBM Batch: Todos los circuitos ====="
curl -s -X POST "$BASE/code/ibm" \
  -H "Content-Type: application/json" \
  -d '{
    "Shor": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"•\",\"X\"],[1,\"X\",\"•\"],[1,\"•\",\"X\"],[1,1,\"•\",\"X\"],[1,1,\"X\",\"•\"],[1,1,\"•\",\"X\"],[\"•\",1,1,\"X\"],[\"X\",1,1,\"•\"],[\"•\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
    "BernsteinVazirani": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
    "DeutschJozsa": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "Simon": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,1,\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,\"•\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "TSP": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"•\"],[\"X\",1,\"•\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}",
    "PhaseEstimation": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"•\",1,1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"•\",\"~16c9\"],[1,\"H\"],[\"•\",1,\"~gf1o\"],[1,\"•\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,√½-√½i}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
    "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}",
    "QAOA": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
    "Kickback": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"•\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
    "FullAdder": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",\"•\",1,\"X\"],[\"•\",\"X\"],[1,\"•\",\"•\",\"X\"],[1,\"•\",\"X\"],[\"•\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}"
  }' | python -m json.tool

echo -e "\n===== 26. AWS Batch: Todos los circuitos ====="
curl -s -X POST "$BASE/code/aws" \
  -H "Content-Type: application/json" \
  -d '{
    "Shor": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"•\",\"X\"],[1,\"X\",\"•\"],[1,\"•\",\"X\"],[1,1,\"•\",\"X\"],[1,1,\"X\",\"•\"],[1,1,\"•\",\"X\"],[\"•\",1,1,\"X\"],[\"X\",1,1,\"•\"],[\"•\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
    "BernsteinVazirani": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
    "DeutschJozsa": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "Simon": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,1,\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,\"•\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "TSP": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"•\"],[\"X\",1,\"•\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
    "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}",
    "PhaseEstimation": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"•\",1,1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"•\",\"~16c9\"],[1,\"H\"],[\"•\",1,\"~gf1o\"],[1,\"•\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,√½-√½i}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
    "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}",
    "QAOA": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
    "Kickback": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"•\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
    "FullAdder": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",\"•\",1,\"X\"],[\"•\",\"X\"],[1,\"•\",\"•\",\"X\"],[1,\"•\",\"X\"],[\"•\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}"
  }' | python -m json.tool

echo -e "\n===== 27. IBM Batch: Subconjunto básico (Grover + QFT + Teleportation) ====="
curl -s -X POST "$BASE/code/ibm" \
  -H "Content-Type: application/json" \
  -d '{
    "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
    "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}",
    "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}"
  }' | python -m json.tool

echo -e "\n===== 28. AWS Batch: Subconjunto básico (Grover + QFT + Teleportation) ====="
curl -s -X POST "$BASE/code/aws" \
  -H "Content-Type: application/json" \
  -d '{
    "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
    "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}",
    "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}"
  }' | python -m json.tool

echo -e "\n\n========================================"
echo "     ALL TESTS COMPLETE"
echo "========================================"
