import sys
sys.path.insert(0, r'..')
from utils.qutils import parse_quirk_url, quirk_col_to_qasm

def build_qasm(circuito, offset=0):
    n = max(len(c) for c in circuito['cols'])
    lines = ['OPENQASM 2.0;', 'include "qelib1.inc";', f'qreg q[{n}];', f'creg c[{n}];', '']
    for col in circuito['cols']:
        lines.extend(quirk_col_to_qasm(col, offset))
    return '\n'.join(lines)


def test(desc, url, offset=0):
    circ = parse_quirk_url(url)
    print(f'\n=== {desc} ===')
    print(build_qasm(circ, offset))


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
