# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.ry(0, math.pi/2)
circuit.ry(1, math.pi/2)
circuit.h(2)
circuit.ry(3, math.pi/2)
circuit.ry(4, -math.pi/2)
circuit.x(4, control=[0])
circuit.ry(0, -math.pi/2)
circuit.x(4, control=[1])
circuit.ry(1, -math.pi/2)
circuit.x(4, control=[2])
circuit.h(2)
circuit.x(4, control=[3])
circuit.ry(3, -math.pi/2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
