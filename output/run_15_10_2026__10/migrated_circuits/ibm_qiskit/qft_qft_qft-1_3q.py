# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(3, 'q')
creg_c = ClassicalRegister(3, 'c')

# Compuertas personalizadas (funciones locales)
def QFT3(circuit, w0, w1, w2):
    circuit.h(w2)
    circuit.cp(math.pi/2, w2, w1)
    circuit.cp(math.pi/4, w2, w0)
    circuit.h(w1)
    circuit.cp(math.pi/2, w1, w0)
    circuit.h(w0)
    circuit.swap(w0, w2)

def QFT3_dg(circuit, w0, w1, w2):
    circuit.swap(w0, w2)
    circuit.h(w0)
    circuit.cp(-math.pi/2, w1, w0)
    circuit.h(w1)
    circuit.cp(-math.pi/4, w2, w0)
    circuit.cp(-math.pi/2, w2, w1)
    circuit.h(w2)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
circuit.h(qreg_q[2])
QFT3(circuit, qreg_q[0], qreg_q[1], qreg_q[2])
QFT3_dg(circuit, qreg_q[0], qreg_q[1], qreg_q[2])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
