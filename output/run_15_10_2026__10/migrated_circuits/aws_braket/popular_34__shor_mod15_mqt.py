# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.x(2)
circuit.x(3)
circuit.x(4)
circuit.x(1)
circuit.x(2)
circuit.x(3)
circuit.x(4)
circuit.x(2, control=[3])
circuit.x(3, control=[2])
circuit.x(2, control=[3])
circuit.x(1, control=[2])
circuit.x(2, control=[1])
circuit.x(1, control=[2])
circuit.x(1, control=[4])
circuit.x(4, control=[1])
circuit.x(1, control=[4])

# Mediciones en orden clásico, diferidas al final
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
