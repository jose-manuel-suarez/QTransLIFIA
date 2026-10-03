# Importación de paquetes requeridos
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(3, 'q')
creg_c = ClassicalRegister(3, 'c')

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
circuit.x(qreg_q[2])
circuit.cz(qreg_q[2], qreg_q[0])
circuit.swap(qreg_q[0], qreg_q[1])
circuit.h(qreg_q[0])
circuit.cp(-1.5707963267948966, qreg_q[1], qreg_q[0])
circuit.h(qreg_q[1])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
