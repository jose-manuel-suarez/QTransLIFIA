# Importación de paquetes requeridos
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(7, 'q')
creg_c = ClassicalRegister(7, 'c')

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.cx(qreg_q[0], qreg_q[1])
circuit.cx(qreg_q[1], qreg_q[2])
circuit.cx(qreg_q[2], qreg_q[3])
circuit.cx(qreg_q[3], qreg_q[4])
circuit.cx(qreg_q[4], qreg_q[5])
circuit.cx(qreg_q[5], qreg_q[6])
circuit.rz(1.5707963267948966, qreg_q[6])
circuit.h(qreg_q[0])
circuit.measure(qreg_q[0], creg_c[0])
