# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def QFT4(circuit, w0, w1, w2, w3):
    circuit.h(w3)
    circuit.cphaseshift([w3], w2, math.pi/2)
    circuit.cphaseshift([w3], w1, math.pi/4)
    circuit.cphaseshift([w3], w0, math.pi/8)
    circuit.h(w2)
    circuit.cphaseshift([w2], w1, math.pi/2)
    circuit.cphaseshift([w2], w0, math.pi/4)
    circuit.h(w1)
    circuit.cphaseshift([w1], w0, math.pi/2)
    circuit.h(w0)
    circuit.swap(w0, w3)
    circuit.swap(w1, w2)

def QFT4_dg(circuit, w0, w1, w2, w3):
    circuit.swap(w0, w3)
    circuit.swap(w1, w2)
    circuit.h(w0)
    circuit.cphaseshift([w1], w0, -math.pi/2)
    circuit.h(w1)
    circuit.cphaseshift([w2], w0, -math.pi/4)
    circuit.cphaseshift([w2], w1, -math.pi/2)
    circuit.h(w2)
    circuit.cphaseshift([w3], w0, -math.pi/8)
    circuit.cphaseshift([w3], w1, -math.pi/4)
    circuit.cphaseshift([w3], w2, -math.pi/2)
    circuit.h(w3)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
QFT4(circuit, 0, 1, 2, 3)
QFT4_dg(circuit, 0, 1, 2, 3)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
