# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def ccu1_pi_512(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/512)

def ccu1_pi_256(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/256)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
ccu1_pi_512(circuit, 1, 2)
ccu1_pi_256(circuit, 0, 2)
circuit.h(0)
circuit.cphaseshift([0], 1, -math.pi/2)
circuit.h(1)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
