# Importación de paquetes requeridos
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(10, 'q')
creg_c = ClassicalRegister(10, 'c')

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.ccx(qreg_q[1], qreg_q[2], qreg_q[3])
circuit.cx(qreg_q[1], qreg_q[2])
circuit.ccx(qreg_q[4], qreg_q[5], qreg_q[6])
circuit.cx(qreg_q[4], qreg_q[5])
circuit.ccx(qreg_q[7], qreg_q[8], qreg_q[9])
circuit.cx(qreg_q[7], qreg_q[8])
circuit.ccx(qreg_q[0], qreg_q[2], qreg_q[3])
circuit.ccx(qreg_q[3], qreg_q[5], qreg_q[6])
circuit.ccx(qreg_q[6], qreg_q[8], qreg_q[9])
circuit.cx(qreg_q[0], qreg_q[2])
circuit.cx(qreg_q[3], qreg_q[5])
circuit.cx(qreg_q[6], qreg_q[8])
