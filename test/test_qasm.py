import sys
sys.path.insert(0, '..')
from utils.qutils import quirk_to_qasm


def test(desc, url, offset=0):
    qasm = quirk_to_qasm(url, offset)
    print(f'\n=== {desc} ===')
    print(qasm)


test("Bell state",
     "https://algassert.com/quirk#circuit={'cols':[['H'],['•','X'],['Measure','Measure']]}")

test("Complex circuit",
     "https://algassert.com/quirk#circuit={'cols':[['H','H','H','H'],['X'],['X','X','X','X'],[1,'•','X'],[1,'X','•'],[1,1,'•','X'],[1,1,'X','•'],['Swap',1,1,'Swap'],['X^½','Y^-¼','Z^-½','Measure']]}")

test("Offset d=5",
     "https://algassert.com/quirk#circuit={'cols':[['H'],['•','X'],['Measure','Measure']]}",
     offset=5)

test("Toffoli (CCX)",
     "https://algassert.com/quirk#circuit={'cols':[[1,'•','•','X']]}")

test("Placeholders",
     "https://algassert.com/quirk#circuit={'cols':[[1,1,1,1],['H',1,'H',1],[1,'Z',1,'X']]}")

print('\nTests completados')
