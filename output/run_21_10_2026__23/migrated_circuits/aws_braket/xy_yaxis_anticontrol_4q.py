# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def p_gate(circuit, w0):
    circuit.u(w0, 0, 0, math.pi/2)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(2)
p_gate(circuit, 0)
p_gate(circuit, 2)
circuit.rx(0, math.pi/2)
circuit.x(0)
circuit.x(1, control=[0])
circuit.x(0)
circuit.rx(0, -math.pi/2)
circuit.rx(2, math.pi/2)
circuit.x(2)
circuit.x(3, control=[2])
circuit.x(2)
circuit.rx(2, -math.pi/2)
p_gate(circuit, 0)
p_gate(circuit, 2)
circuit.h(0)
circuit.h(2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
