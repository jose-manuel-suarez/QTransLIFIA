# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.x(1)
circuit.x(2)
circuit.h(0)
circuit.z(0, control=[1])
circuit.cphaseshift([2], 0, 1.5707963267948966)
circuit.h(1)
circuit.z(1, control=[2])
circuit.h(2)
