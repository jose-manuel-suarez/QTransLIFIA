# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.h(0)
circuit.x(1, control=[0])
circuit.x(2, control=[1])
circuit.x(3, control=[2])
circuit.x(4, control=[3])
circuit.x(5, control=[4])
circuit.x(6, control=[5])
circuit.rz(6, 1.5707963267948966)
circuit.h(0)
circuit.measure([0])
