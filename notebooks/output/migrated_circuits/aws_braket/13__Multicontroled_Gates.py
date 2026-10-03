# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
circuit.h(4)
circuit.x(3, control=[0, 1])
circuit.y(3, control=[1, 2])
circuit.z(4, control=[2, 3])
circuit.x(3, control=[0, 1, 2])
circuit.y(4, control=[1, 2, 3])
circuit.z(4, control=[0, 2, 3])
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
