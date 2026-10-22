# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(2, 'q')
creg_c = ClassicalRegister(2, 'c')
creg_ps = ClassicalRegister(2, 'ps')

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c, creg_ps)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
circuit.p(math.pi/2, qreg_q[0])
circuit.p(math.pi/2, qreg_q[1])
circuit.sdg(qreg_q[0])
circuit.h(qreg_q[0])
circuit.measure(qreg_q[0], creg_ps[0])
circuit.sdg(qreg_q[1])
circuit.h(qreg_q[1])
circuit.measure(qreg_q[1], creg_ps[1])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
