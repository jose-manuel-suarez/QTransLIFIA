# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def ccu1_pi_8(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/8)

def ccu1_pi_16(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/16)

def ccu1_pi_32(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/32)

def ccu1_pi_64(circuit, w0, w1):
    circuit.cphaseshift([w0], w1, math.pi/64)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.cphaseshift([0], 1, math.pi/2)
circuit.cphaseshift([0], 2, math.pi/4)
ccu1_pi_8(circuit, 0, 3)
ccu1_pi_16(circuit, 0, 4)
ccu1_pi_32(circuit, 0, 5)
ccu1_pi_64(circuit, 0, 6)
circuit.h(1)
circuit.cphaseshift([1], 2, math.pi/2)
circuit.cphaseshift([1], 3, math.pi/4)
ccu1_pi_8(circuit, 1, 4)
ccu1_pi_16(circuit, 1, 5)
ccu1_pi_32(circuit, 1, 6)
circuit.h(2)
circuit.cphaseshift([2], 3, math.pi/2)
circuit.cphaseshift([2], 4, math.pi/4)
ccu1_pi_8(circuit, 2, 5)
ccu1_pi_16(circuit, 2, 6)
circuit.h(3)
circuit.cphaseshift([3], 4, math.pi/2)
circuit.cphaseshift([3], 5, math.pi/4)
ccu1_pi_8(circuit, 3, 6)
circuit.h(4)
circuit.cphaseshift([4], 5, math.pi/2)
circuit.cphaseshift([4], 6, math.pi/4)
circuit.h(5)
circuit.cphaseshift([5], 6, math.pi/2)
circuit.h(6)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
circuit.measure([5])
circuit.measure([6])
