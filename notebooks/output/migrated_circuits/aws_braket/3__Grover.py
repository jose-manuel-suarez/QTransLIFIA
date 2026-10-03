# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.h(0)
circuit.h(1)
circuit.x(1)
circuit.h(1)
circuit.x(1, control=[0])
circuit.h(1)
circuit.x(1)
circuit.h(1)
circuit.measure([1])
