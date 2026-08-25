@echo off
REM ============================================================
REM Curl tests for Quirk Translator - IBM y AWS
REM Espejo de test\test_curl.sh (28 tests)
REM Endpoints: /code/ibm, /code/ibm/individual, /code/aws, /code/aws/individual
REM Base URL: http://localhost:8081
REM Requiere: servidor Flask corriendo en el puerto 8081
REM Nota: unicode emitido como escapes JSON \uXXXX (archivo ASCII)
REM ============================================================

setlocal

set BASE=http://localhost:8081
set PY=python
if exist "%~dp0.venv\Scripts\python.exe" set PY=%~dp0.venv\Scripts\python.exe

set TMPD=%TEMP%\qtranslifia_tests
if not exist "%TMPD%" mkdir "%TMPD%"

echo ===== 1. IBM Individual: Shor (d=0) =====
set P=%TMPD%\p01.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"\u2022\",\"X\"],[1,\"X\",\"\u2022\"],[1,\"\u2022\",\"X\"],[1,1,\"\u2022\",\"X\"],[1,1,\"X\",\"\u2022\"],[1,1,\"\u2022\",\"X\"],[\"\u2022\",1,1,\"X\"],[\"X\",1,1,\"\u2022\"],[\"\u2022\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 2. IBM Individual: BernsteinVazirani (d=1) =====
set P=%TMPD%\p02.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 3. IBM Individual: Grover (d=2) =====
set P=%TMPD%\p03.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"\u2022\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 4. IBM Individual: DeutschJozsa (d=0) =====
set P=%TMPD%\p04.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 5. IBM Individual: Simon (d=1) =====
set P=%TMPD%\p05.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 6. IBM Individual: TSP (d=2) =====
set P=%TMPD%\p06.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"\u2022\"],[\"X\",1,\"\u2022\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 7. IBM Individual: Teleportation (d=0) =====
set P=%TMPD%\p07.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"\u2022\",1,1,\"X\"],[\"H\"],[\"\u2022\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"\u2022\",1,1,\"X\"],[\"\u2022\",1,1,1,\"Z\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 8. IBM Individual: PhaseEstimation (d=1) =====
set P=%TMPD%\p08.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"\u2022\",1,1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"\u2022\",\"~16c9\"],[1,\"H\"],[\"\u2022\",1,\"~gf1o\"],[1,\"\u2022\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,\u221a\u00bd-\u221a\u00bdi}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 9. IBM Individual: QFT (d=2) =====
set P=%TMPD%\p09.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"\u2022\"],[\"Z^^\u00bd\",1,\"\u2022\"],[1,\"H\"],[1,\"Z\",\"\u2022\"],[1,1,\"H\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 10. IBM Individual: QAOA (d=0) =====
set P=%TMPD%\p10.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 11. IBM Individual: Kickback (d=1) =====
set P=%TMPD%\p11.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"\u2022\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 12. IBM Individual: FullAdder (d=2) =====
set P=%TMPD%\p12.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",\"\u2022\",1,\"X\"],[\"\u2022\",\"X\"],[1,\"\u2022\",\"\u2022\",\"X\"],[1,\"\u2022\",\"X\"],[\"\u2022\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.


echo ========================================
echo      AWS INDIVIDUAL ENDPOINTS
echo ========================================

echo ===== 13. AWS Individual: Shor (d=0) =====
set P=%TMPD%\p13.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"\u2022\",\"X\"],[1,\"X\",\"\u2022\"],[1,\"\u2022\",\"X\"],[1,1,\"\u2022\",\"X\"],[1,1,\"X\",\"\u2022\"],[1,1,\"\u2022\",\"X\"],[\"\u2022\",1,1,\"X\"],[\"X\",1,1,\"\u2022\"],[\"\u2022\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 14. AWS Individual: BernsteinVazirani (d=1) =====
set P=%TMPD%\p14.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 15. AWS Individual: Grover (d=2) =====
set P=%TMPD%\p15.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"\u2022\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 16. AWS Individual: DeutschJozsa (d=0) =====
set P=%TMPD%\p16.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 17. AWS Individual: Simon (d=1) =====
set P=%TMPD%\p17.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 18. AWS Individual: TSP (d=2) =====
set P=%TMPD%\p18.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"\u2022\"],[\"X\",1,\"\u2022\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 19. AWS Individual: Teleportation (d=0) =====
set P=%TMPD%\p19.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"\u2022\",1,1,\"X\"],[\"H\"],[\"\u2022\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"\u2022\",1,1,\"X\"],[\"\u2022\",1,1,1,\"Z\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 20. AWS Individual: PhaseEstimation (d=1) =====
set P=%TMPD%\p20.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"\u2022\",1,1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"\u2022\",\"~16c9\"],[1,\"H\"],[\"\u2022\",1,\"~gf1o\"],[1,\"\u2022\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,\u221a\u00bd-\u221a\u00bdi}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 21. AWS Individual: QFT (d=2) =====
set P=%TMPD%\p21.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"\u2022\"],[\"Z^^\u00bd\",1,\"\u2022\"],[1,\"H\"],[1,\"Z\",\"\u2022\"],[1,1,\"H\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 22. AWS Individual: QAOA (d=0) =====
set P=%TMPD%\p22.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
>> "%P%" echo     "d": 0
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 23. AWS Individual: Kickback (d=1) =====
set P=%TMPD%\p23.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"\u2022\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
>> "%P%" echo     "d": 1
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 24. AWS Individual: FullAdder (d=2) =====
set P=%TMPD%\p24.json
> "%P%" echo {
>> "%P%" echo     "url": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",\"\u2022\",1,\"X\"],[\"\u2022\",\"X\"],[1,\"\u2022\",\"\u2022\",\"X\"],[1,\"\u2022\",\"X\"],[\"\u2022\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}",
>> "%P%" echo     "d": 2
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws/individual" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.


echo ========================================
echo      BATCH ENDPOINTS
echo ========================================

echo ===== 25. IBM Batch: Todos los circuitos =====
set P=%TMPD%\p25.json
> "%P%" echo {
>> "%P%" echo     "Shor": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"\u2022\",\"X\"],[1,\"X\",\"\u2022\"],[1,\"\u2022\",\"X\"],[1,1,\"\u2022\",\"X\"],[1,1,\"X\",\"\u2022\"],[1,1,\"\u2022\",\"X\"],[\"\u2022\",1,1,\"X\"],[\"X\",1,1,\"\u2022\"],[\"\u2022\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "BernsteinVazirani": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"\u2022\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
>> "%P%" echo     "DeutschJozsa": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "Simon": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "TSP": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"\u2022\"],[\"X\",1,\"\u2022\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"\u2022\",1,1,\"X\"],[\"H\"],[\"\u2022\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"\u2022\",1,1,\"X\"],[\"\u2022\",1,1,1,\"Z\"]]}",
>> "%P%" echo     "PhaseEstimation": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"\u2022\",1,1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"\u2022\",\"~16c9\"],[1,\"H\"],[\"\u2022\",1,\"~gf1o\"],[1,\"\u2022\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,\u221a\u00bd-\u221a\u00bdi}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
>> "%P%" echo     "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"\u2022\"],[\"Z^^\u00bd\",1,\"\u2022\"],[1,\"H\"],[1,\"Z\",\"\u2022\"],[1,1,\"H\"]]}",
>> "%P%" echo     "QAOA": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
>> "%P%" echo     "Kickback": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"\u2022\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
>> "%P%" echo     "FullAdder": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",\"\u2022\",1,\"X\"],[\"\u2022\",\"X\"],[1,\"\u2022\",\"\u2022\",\"X\"],[1,\"\u2022\",\"X\"],[\"\u2022\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}"
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 26. AWS Batch: Todos los circuitos =====
set P=%TMPD%\p26.json
> "%P%" echo {
>> "%P%" echo     "Shor": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\",\"H\"],[\"X\"],[\"X\",\"X\",\"X\",\"X\"],[1,\"\u2022\",\"X\"],[1,\"X\",\"\u2022\"],[1,\"\u2022\",\"X\"],[1,1,\"\u2022\",\"X\"],[1,1,\"X\",\"\u2022\"],[1,1,\"\u2022\",\"X\"],[\"\u2022\",1,1,\"X\"],[\"X\",1,1,\"\u2022\"],[\"\u2022\",1,1,\"X\"],[\"Measure\",\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "BernsteinVazirani": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"\u2022\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
>> "%P%" echo     "DeutschJozsa": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"X\",1,\"X\",\"X\"],[1,1,1,\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,\"X\"],[1,1,\"\u2022\",\"X\"],[\"X\",1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "Simon": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,\"X\"],[1,\"\u2022\",1,1,1,\"X\"],[\"H\",\"H\",\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "TSP": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\"],[1,\"X\",\"X\"],[\"X\",\"\u2022\"],[\"X\",1,\"\u2022\"],[\"H\"],[\"Measure\",\"Measure\",\"Measure\"]]}",
>> "%P%" echo     "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"\u2022\",1,1,\"X\"],[\"H\"],[\"\u2022\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"\u2022\",1,1,\"X\"],[\"\u2022\",1,1,1,\"Z\"]]}",
>> "%P%" echo     "PhaseEstimation": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,1,1,\"X\"],[\"\u2022\",1,1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,\"\u2022\",1,\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[1,1,\"\u2022\",\"Z^^\u00bc\"],[\"Swap\",1,\"Swap\"],[\"H\"],[\"\u2022\",\"~16c9\"],[1,\"H\"],[\"\u2022\",1,\"~gf1o\"],[1,\"\u2022\",\"~16c9\"],[1,1,\"H\"],[\"Measure\",\"Measure\",\"Measure\"]],\"gates\":[{\"id\":\"~gf1o\",\"name\":\"U(-pi/4)\",\"matrix\":\"{{1,0},{0,\u221a\u00bd-\u221a\u00bdi}}\"},{\"id\":\"~16c9\",\"name\":\"U(-pi/2)\",\"matrix\":\"{{1,0},{0,-i}}\"}]}",
>> "%P%" echo     "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"\u2022\"],[\"Z^^\u00bd\",1,\"\u2022\"],[1,\"H\"],[1,\"Z\",\"\u2022\"],[1,1,\"H\"]]}",
>> "%P%" echo     "QAOA": "https://algassert.com/quirk#circuit={\"cols\":[[\"Rxft\",\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\",\"Rxft\"],[],[1,\"Rxft\"],[],[\"\u2022\",\"X\"],[\"Rxft\"],[],[1,\"Measure\"],[\"Measure\"]]}",
>> "%P%" echo     "Kickback": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"X\"],[\"H\",\"H\"],[\"\u2022\",\"X\"],[\"H\",\"H\"],[\"Measure\"],[1,\"Measure\"]]}",
>> "%P%" echo     "FullAdder": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[\"\u2022\",\"\u2022\",1,\"X\"],[\"\u2022\",\"X\"],[1,\"\u2022\",\"\u2022\",\"X\"],[1,\"\u2022\",\"X\"],[\"\u2022\",\"X\"],[\"Measure\"],[1,\"Measure\"],[1,1,\"Measure\"],[1,1,1,\"Measure\"]]}"
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 27. IBM Batch: Subconjunto basico (Grover + QFT + Teleportation) =====
set P=%TMPD%\p27.json
> "%P%" echo {
>> "%P%" echo     "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"\u2022\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
>> "%P%" echo     "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"\u2022\"],[\"Z^^\u00bd\",1,\"\u2022\"],[1,\"H\"],[1,\"Z\",\"\u2022\"],[1,1,\"H\"]]}",
>> "%P%" echo     "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"\u2022\",1,1,\"X\"],[\"H\"],[\"\u2022\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"\u2022\",1,1,\"X\"],[\"\u2022\",1,1,1,\"Z\"]]}"
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/ibm" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

echo ===== 28. AWS Batch: Subconjunto basico (Grover + QFT + Teleportation) =====
set P=%TMPD%\p28.json
> "%P%" echo {
>> "%P%" echo     "Grover": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\"],[1,\"X\"],[1,\"H\"],[\"\u2022\",\"X\"],[1,\"H\"],[1,\"X\"],[1,\"H\"],[1,\"Measure\"]]}",
>> "%P%" echo     "QFT": "https://algassert.com/quirk#circuit={\"cols\":[[\"H\",\"H\",\"H\"],[1,\"X\",\"X\"],[\"H\"],[\"Z\",\"\u2022\"],[\"Z^^\u00bd\",1,\"\u2022\"],[1,\"H\"],[1,\"Z\",\"\u2022\"],[1,1,\"H\"]]}",
>> "%P%" echo     "Teleportation": "https://algassert.com/quirk#circuit={\"cols\":[[1,\"H\"],[1,\"\u2022\",1,1,\"X\"],[\"H\"],[\"\u2022\",\"X\"],[\"H\"],[\"Measure\",\"Measure\"],[1,\"\u2022\",1,1,\"X\"],[\"\u2022\",1,1,1,\"Z\"]]}"
>> "%P%" echo }
curl.exe -s -X POST "%BASE%/code/aws" -H "Content-Type: application/json" -d @"%P%" | "%PY%" -m json.tool
echo.

rd /s /q "%TMPD%" 2>nul

echo ========================================
echo      ALL TESTS COMPLETE
echo ========================================
