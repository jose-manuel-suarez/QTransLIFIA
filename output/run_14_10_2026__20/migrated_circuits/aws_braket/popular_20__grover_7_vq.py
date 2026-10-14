# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
circuit.h(6)
circuit.x(4, control=[0, 1])
circuit.x(5, control=[2, 4])
circuit.x(6, control=[3, 5])
circuit.x(5, control=[2, 4])
circuit.h(6)
circuit.x(4, control=[0, 1])
circuit.h(2)
circuit.h(3)
circuit.h(0)
circuit.h(1)
circuit.x(2)
circuit.x(3)
circuit.x(0)
circuit.x(1)
circuit.h(3)
circuit.x(4, control=[0, 1])
circuit.x(3, control=[2, 4])
circuit.x(4, control=[0, 1])
circuit.h(3)
circuit.x(0)
circuit.x(1)
circuit.x(2)
circuit.x(3)
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
circuit.measure([5])
circuit.measure([6])
