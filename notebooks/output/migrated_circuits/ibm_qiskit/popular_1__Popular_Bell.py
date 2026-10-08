# Importación de paquetes requeridos
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(1, 'q')
creg_c = ClassicalRegister(1, 'c')

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.measure(qreg_q[0], creg_c[0])
