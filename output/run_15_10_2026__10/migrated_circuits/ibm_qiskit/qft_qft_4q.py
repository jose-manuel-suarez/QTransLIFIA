# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(4, 'q')
creg_c = ClassicalRegister(4, 'c')

# Compuertas personalizadas (funciones locales)
def QFT4(circuit, w0, w1, w2, w3):
    circuit.h(w3)
    circuit.cp(math.pi/2, w3, w2)
    circuit.cp(math.pi/4, w3, w1)
    circuit.cp(math.pi/8, w3, w0)
    circuit.h(w2)
    circuit.cp(math.pi/2, w2, w1)
    circuit.cp(math.pi/4, w2, w0)
    circuit.h(w1)
    circuit.cp(math.pi/2, w1, w0)
    circuit.h(w0)
    circuit.swap(w0, w3)
    circuit.swap(w1, w2)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
circuit.h(qreg_q[2])
circuit.h(qreg_q[3])
QFT4(circuit, qreg_q[0], qreg_q[1], qreg_q[2], qreg_q[3])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
circuit.measure(qreg_q[3], creg_c[3])
