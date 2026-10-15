# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def QFT2(circuit, w0, w1):
    circuit.h(w1)
    circuit.cphaseshift([w1], w0, math.pi/2)
    circuit.h(w0)
    circuit.swap(w0, w1)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
QFT2(circuit, 0, 1)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
