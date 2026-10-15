# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def ccp_7_pi_8(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, -7*math.pi/8)

def ccp_pi_8(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, -math.pi/8)

def ccp_pi_16(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, -math.pi/16)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
circuit.h(4)
circuit.x(5)
ccp_7_pi_8(circuit, 5, 0)
circuit.swap(0, 4)
circuit.h(0)
circuit.cphaseshift([5], 1, math.pi/4)
circuit.cphaseshift([5], 2, math.pi/2)
circuit.z(3, control=[5])
circuit.swap(1, 3)
circuit.cphaseshift([1], 0, -math.pi/2)
circuit.h(1)
circuit.cphaseshift([2], 0, -math.pi/4)
circuit.cphaseshift([2], 1, -math.pi/2)
circuit.h(2)
ccp_pi_8(circuit, 3, 0)
circuit.cphaseshift([3], 1, -math.pi/4)
circuit.cphaseshift([3], 2, -math.pi/2)
circuit.h(3)
ccp_pi_16(circuit, 4, 0)
ccp_pi_8(circuit, 4, 1)
circuit.cphaseshift([4], 2, -math.pi/4)
circuit.cphaseshift([4], 3, -math.pi/2)
circuit.h(4)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
