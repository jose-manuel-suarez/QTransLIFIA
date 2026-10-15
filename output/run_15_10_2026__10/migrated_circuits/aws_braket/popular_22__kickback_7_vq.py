# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def rz_pi_2(circuit, w0):
    circuit.rz(w0, math.pi/2)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.x(1, control=[0])
circuit.x(2, control=[1])
circuit.x(3, control=[2])
circuit.x(4, control=[3])
circuit.x(5, control=[4])
circuit.x(6, control=[5])
rz_pi_2(circuit, 6)
circuit.h(0)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
