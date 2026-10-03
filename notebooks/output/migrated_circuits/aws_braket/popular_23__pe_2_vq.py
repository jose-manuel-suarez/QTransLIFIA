# Importación de paquetes requeridos
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas y mediciones migradas desde OpenQASM 3.0
circuit.h(0)
circuit.h(1)
circuit.cphaseshift([1], 2, 0.006135923151542565)
circuit.cphaseshift([0], 2, 0.01227184630308513)
circuit.h(0)
circuit.cphaseshift([0], 1, -1.5707963267948966)
circuit.h(1)
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
