# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.ry(0, 1.5707963267948966)
circuit.ry(1, 1.5707963267948966)
circuit.h(2)
circuit.ry(3, -1.5707963267948966)
circuit.x(3, control=[0])
circuit.ry(0, -1.5707963267948966)
circuit.x(3, control=[1])
circuit.ry(1, -1.5707963267948966)
circuit.x(3, control=[2])
circuit.h(2)
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
