# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def p_gate(circuit, w0):
    circuit.u(w0, 0, 0, -math.pi/2)

def sdg_gate(circuit, w0):
    p_gate(circuit, w0)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
circuit.h(4)
circuit.h(5)
circuit.h(6)
circuit.h(7)
circuit.h(8)
circuit.h(9)
p_gate(circuit, 0)
p_gate(circuit, 1)
p_gate(circuit, 2)
p_gate(circuit, 3)
p_gate(circuit, 4)
p_gate(circuit, 5)
p_gate(circuit, 6)
p_gate(circuit, 7)
p_gate(circuit, 8)
p_gate(circuit, 9)
sdg_gate(circuit, 0)
circuit.h(0)
sdg_gate(circuit, 1)
circuit.h(1)
sdg_gate(circuit, 2)
circuit.h(2)
sdg_gate(circuit, 3)
circuit.h(3)
sdg_gate(circuit, 4)
circuit.h(4)
sdg_gate(circuit, 5)
circuit.h(5)
sdg_gate(circuit, 6)
circuit.h(6)
sdg_gate(circuit, 7)
circuit.h(7)
sdg_gate(circuit, 8)
circuit.h(8)
sdg_gate(circuit, 9)
circuit.h(9)

# Mediciones en orden clásico, diferidas al final
# Qubit(s) 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 medido(s) más de una vez en OpenQASM: Braket admite una sola medición por qubit
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
circuit.measure([5])
circuit.measure([6])
circuit.measure([7])
circuit.measure([8])
circuit.measure([9])
