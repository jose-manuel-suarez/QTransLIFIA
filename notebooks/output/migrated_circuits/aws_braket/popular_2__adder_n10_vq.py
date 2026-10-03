# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.x(3, control=[1, 2])
circuit.x(2, control=[1])
circuit.x(6, control=[4, 5])
circuit.x(5, control=[4])
circuit.x(9, control=[7, 8])
circuit.x(8, control=[7])
circuit.x(3, control=[0, 2])
circuit.x(6, control=[3, 5])
circuit.x(9, control=[6, 8])
circuit.x(2, control=[0])
circuit.x(5, control=[3])
circuit.x(8, control=[6])
