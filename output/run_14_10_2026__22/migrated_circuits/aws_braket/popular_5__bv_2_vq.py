# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.x(1)
circuit.h(1)
circuit.x(1, control=[0])
circuit.h(0)
circuit.h(1)
