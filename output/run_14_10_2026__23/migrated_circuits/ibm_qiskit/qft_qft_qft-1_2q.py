# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(2, 'q')
creg_c = ClassicalRegister(2, 'c')

# Compuertas personalizadas (funciones locales)
def QFT2(circuit, w0, w1):
    circuit.h(w1)
    circuit.cp(math.pi/2, w1, w0)
    circuit.h(w0)
    circuit.swap(w0, w1)

def QFT2_dg(circuit, w0, w1):
    circuit.swap(w0, w1)
    circuit.h(w0)
    circuit.cp(-math.pi/2, w1, w0)
    circuit.h(w1)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
QFT2(circuit, qreg_q[0], qreg_q[1])
QFT2_dg(circuit, qreg_q[0], qreg_q[1])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
