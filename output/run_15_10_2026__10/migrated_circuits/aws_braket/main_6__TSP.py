# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.x(1)
circuit.x(2)
circuit.x(0, control=[1])
circuit.x(0, control=[2])
circuit.h(0)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
