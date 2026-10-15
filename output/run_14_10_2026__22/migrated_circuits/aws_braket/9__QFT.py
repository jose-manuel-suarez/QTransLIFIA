# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.x(1)
circuit.x(2)
circuit.h(0)
circuit.z(0, control=[1])
circuit.cphaseshift([2], 0, math.pi/2)
circuit.h(1)
circuit.z(1, control=[2])
circuit.h(2)
