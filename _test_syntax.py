import json, sys
sys.path.insert(0, '..')

from utils.qutils import quirk_to_qasm, quirk_circuit_info
from IPython.display import display, Markdown

ALGORITHMS = {
    '1. Shor': {
        'desc': 'test',
        'url': "https://algassert.com/quirk#circuit={'cols':[['H'],['Measure']]}",
        'offset': 0,
    },
}


def describe_algorithms():
    md = '| # | Algoritmo | Qubits | Descripci\u00f3n |\n|---|---|---|---|\n'
    for k, v in ALGORITHMS.items():
        info = quirk_circuit_info(v['url'])
        nq = info['n_qubits']
        md += f'| {k.split(".")[0]} | **{k.split(". ")[1]}** | {nq} | {v["desc"]} |\n'
    print(md)


describe_algorithms()
print('Syntax OK')
