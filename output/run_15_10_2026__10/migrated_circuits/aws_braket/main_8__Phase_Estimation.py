# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def cU_pi_2(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, -math.pi/2)

def cU_pi_4(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, -math.pi/4)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.x(3)
circuit.cphaseshift([0], 3, math.pi/4)
circuit.cphaseshift([1], 3, math.pi/4)
circuit.cphaseshift([1], 3, math.pi/4)
circuit.cphaseshift([2], 3, math.pi/4)
circuit.cphaseshift([2], 3, math.pi/4)
circuit.cphaseshift([2], 3, math.pi/4)
circuit.cphaseshift([2], 3, math.pi/4)
circuit.swap(0, 2)
circuit.h(0)
cU_pi_2(circuit, 0, 1)
circuit.h(1)
cU_pi_4(circuit, 0, 2)
cU_pi_2(circuit, 1, 2)
circuit.h(2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
