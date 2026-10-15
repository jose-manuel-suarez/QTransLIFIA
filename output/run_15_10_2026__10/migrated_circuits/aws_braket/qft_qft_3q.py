# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def QFT3(circuit, w0, w1, w2):
    circuit.h(w2)
    circuit.cphaseshift([w2], w1, math.pi/2)
    circuit.cphaseshift([w2], w0, math.pi/4)
    circuit.h(w1)
    circuit.cphaseshift([w1], w0, math.pi/2)
    circuit.h(w0)
    circuit.swap(w0, w2)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
QFT3(circuit, 0, 1, 2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
