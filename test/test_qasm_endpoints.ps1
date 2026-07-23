$BASE = "http://localhost:8081"
$TMP = "C:\Users\palob\AppData\Local\Temp\opencode"

function Test-Circuit {
    param($Name, $Endpoint, $Body)
    Write-Host "=== $Name ===" -ForegroundColor Green
    $Body | Out-File "$TMP\_test.json" -Encoding utf8 -NoNewline
    $resp = curl.exe -s -X POST "$BASE$Endpoint" -H "Content-Type: application/json" -d "@$TMP\_test.json"
    $resp | python -c "import sys,json; d=json.load(sys.stdin); print(d.get('qasm', json.dumps(d,indent=2)))"
}

# ===== QASM INDIVIDUAL =====
Test-Circuit "1. QASM Individual: Shor (d=0)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"•\",\"X\"],[1,\"X\",\"•\"],[1,\"•\",\"X\"],[1,1,\"•\",\"X\"],[1,1,\"X\",\"•\"],[1,1,\"•\",\"X\"],[\"•\",1,1,\"X\"],[\"X\",1,1,\"•\"],[\"•\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}","d":0}'
Test-Circuit "2. QASM Individual: BernsteinVazirani (d=1)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}","d":1}'
Test-Circuit "3. QASM Individual: Grover (d=2)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}","d":2}'
Test-Circuit "4. QASM Individual: DeutschJozsa (d=0)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,\"X\"],[1,1,\"•\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}","d":0}'
Test-Circuit "5. QASM Individual: Simon (d=1)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,1,\"•\",1,1,\"X\"],[1,\"•\",1,1,\"X\"],[1,\"•\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}","d":1}'
Test-Circuit "6. QASM Individual: TSP (d=2)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"•\"],[\"X\",1,\"•\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}","d":2}'
Test-Circuit "7. QASM Individual: Teleportation (d=0)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}","d":0}'
Test-Circuit "8. QASM Individual: PhaseEstimation (d=1)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"•\",1,1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,\"•\",1,\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[1,1,\"•\",\"Z^¼\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"•\",\"~16c9\"],[1,\"H\"],[\"•\",1,\"~gf1o\"],[1,\"•\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,√½-√½i}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}","d":1}'
Test-Circuit "9. QASM Individual: QFT (d=2)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}","d":2}'
Test-Circuit "10. QASM Individual: QAOA (d=0)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"•\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}","d":0}'
Test-Circuit "11. QASM Individual: Kickback (d=1)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"•\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}","d":1}'
Test-Circuit "12. QASM Individual: FullAdder (d=2)" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"•\",\"•\",1,\"X\"],[\"•\",\"X\"],[1,\"•\",\"•\",\"X\"],[1,\"•\",\"X\"],[\"•\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}","d":2}'

# ===== QASM BATCH =====
Test-Circuit "13. QASM Batch: Todos los circuitos" -Endpoint "/code/qasm" -Body '{"Shor":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"•\",\"X\"],[1,\"X\",\"•\"],[1,\"•\",\"X\"],[1,1,\"•\",\"X\"],[1,1,\"X\",\"•\"],[1,1,\"•\",\"X\"],[\"•\",1,1,\"X\"],[\"X\",1,1,\"•\"],[\"•\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}","Grover":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}","Teleportation":"https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}"}'
Test-Circuit "14. QASM Batch: Subconjunto basico" -Endpoint "/code/qasm" -Body '{"Grover":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"•\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}","QFT":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"•\"],[\"Z^½\",1,\"•\"],[1,\"H\"],[1,\"Z\",\"•\"],[1,1,\"H\"]]}","Teleportation":"https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"•\",1,1,\"X\"],[\"H\"],[\"•\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"•\",1,1,\"X\"],[\"•\",1,1,1,\"Z\"]]}"}'

# ===== CASOS BORDE =====
Test-Circuit "15. Borde: H+controles sin target" -Endpoint "/code/qasm/individual" -Body '{"url":"https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"•\",\"•\"]]}","d":0}'

Write-Host "`n=== 15 PRUEBAS COMPLETADAS ===" -ForegroundColor Yellow
Remove-Item "$TMP\_test.json" -ErrorAction SilentlyContinue
