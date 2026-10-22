# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
circuit.h(4)
circuit.h(5)
circuit.h(6)
circuit.h(7)
circuit.h(8)
circuit.h(9)
circuit.z(0)
circuit.z(1)
circuit.z(2)
circuit.z(3)
circuit.z(4)
circuit.z(5)
circuit.z(6)
circuit.z(7)
circuit.z(8)
circuit.z(9)
circuit.h(0)
circuit.h(1)
circuit.h(2)
circuit.h(3)
circuit.h(4)
circuit.h(5)
circuit.h(6)
circuit.h(7)
circuit.h(8)
circuit.h(9)

# Mediciones en orden clásico, diferidas al final
# Qubit(s) 0, 1, 2, 3, 4, 5, 6, 7, 8, 9 medido(s) más de una vez en OpenQASM: Braket admite una sola medición por qubit
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
circuit.measure([4])
circuit.measure([5])
circuit.measure([6])
circuit.measure([7])
circuit.measure([8])
circuit.measure([9])
