# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(6, 'q')
creg_c = ClassicalRegister(6, 'c')
creg_ps = ClassicalRegister(6, 'ps')

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c, creg_ps)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
circuit.h(qreg_q[2])
circuit.h(qreg_q[3])
circuit.h(qreg_q[4])
circuit.h(qreg_q[5])
circuit.h(qreg_q[0])
circuit.measure(qreg_q[0], creg_ps[0])
circuit.h(qreg_q[1])
circuit.measure(qreg_q[1], creg_ps[1])
circuit.h(qreg_q[2])
circuit.measure(qreg_q[2], creg_ps[2])
circuit.h(qreg_q[3])
circuit.measure(qreg_q[3], creg_ps[3])
circuit.h(qreg_q[4])
circuit.measure(qreg_q[4], creg_ps[4])
circuit.h(qreg_q[5])
circuit.measure(qreg_q[5], creg_ps[5])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
circuit.measure(qreg_q[3], creg_c[3])
circuit.measure(qreg_q[4], creg_c[4])
circuit.measure(qreg_q[5], creg_c[5])
