# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.x(3, control=[1, 2])
circuit.x(2, control=[1])
circuit.x(3, control=[0, 2])
circuit.x(2, control=[0])
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
