# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.x(2, control=[0, 1])
circuit.h(0)
circuit.h(1)
circuit.x(0)
circuit.x(1)
circuit.h(1)
circuit.x(1, control=[0])
circuit.h(1)
circuit.x(0)
circuit.x(1)
circuit.h(0)
circuit.h(1)
circuit.h(2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
