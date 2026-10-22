# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(2)
circuit.h(4)
circuit.z(2)
circuit.h(0)
circuit.x(0)
circuit.x(1, control=[0])
circuit.x(0)
circuit.h(0)
circuit.h(2)
circuit.x(2)
circuit.x(3, control=[2])
circuit.x(2)
circuit.h(2)
circuit.h(4)
circuit.x(4)
circuit.x(5, control=[4])
circuit.x(4)
circuit.h(4)
circuit.h(0)
circuit.h(2)
circuit.h(4)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
circuit.measure([5])
