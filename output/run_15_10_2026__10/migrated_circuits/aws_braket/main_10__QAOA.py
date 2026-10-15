# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.x(1, control=[0])
circuit.x(1, control=[0])

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
