# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.x(3)
circuit.z(0, control=[3])
circuit.swap(0, 2)
circuit.h(0)
circuit.cphaseshift([1], 0, -math.pi/2)
circuit.h(1)
circuit.cphaseshift([2], 0, -math.pi/4)
circuit.cphaseshift([2], 1, -math.pi/2)
circuit.h(2)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
