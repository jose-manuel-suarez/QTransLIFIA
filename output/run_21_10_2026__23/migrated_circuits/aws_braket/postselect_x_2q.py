# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def p_gate(circuit, w0):
    circuit.u(w0, 0, 0, math.pi/2)

def sdg_gate(circuit, w0):
    p_gate(circuit, w0)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
p_gate(circuit, 0)
p_gate(circuit, 1)
sdg_gate(circuit, 0)
circuit.h(0)
sdg_gate(circuit, 1)
circuit.h(1)

# Mediciones en orden clásico, diferidas al final
# Qubit(s) 0, 1 medido(s) más de una vez en OpenQASM: Braket admite una sola medición por qubit
circuit.measure([0])
circuit.measure([1])
