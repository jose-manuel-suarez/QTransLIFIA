# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.h(2)
circuit.cphaseshift([2], 1, 1.5707963267948966)
circuit.h(1)
circuit.cphaseshift([2], 0, 0.7853981633974483)
circuit.cphaseshift([1], 0, 1.5707963267948966)
circuit.h(0)
circuit.swap(0, 2)
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
