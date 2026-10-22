# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(1)
circuit.cphaseshift([1], 0, math.pi/2)
circuit.h(0)
circuit.swap(0, 1)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
