# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def ccp_pi_8(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/8)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(3)
circuit.cphaseshift([3], 2, math.pi/2)
circuit.h(2)
circuit.cphaseshift([3], 1, math.pi/4)
circuit.cphaseshift([2], 1, math.pi/2)
circuit.h(1)
ccp_pi_8(circuit, 3, 0)
circuit.cphaseshift([2], 0, math.pi/4)
circuit.cphaseshift([1], 0, math.pi/2)
circuit.h(0)
circuit.swap(0, 3)
circuit.swap(1, 2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
