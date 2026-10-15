# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(3, 'q')
creg_c = ClassicalRegister(3, 'c')

# Compuertas personalizadas (funciones locales)
def mcphase(circuit, w0, w1):
    circuit.cp(math.pi/512, w0, w1)

def ccu1_pi_512(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def ccu1_pi_256(circuit, w0, w1):
    mcphase(circuit, w0, w1)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
ccu1_pi_512(circuit, qreg_q[1], qreg_q[2])
ccu1_pi_256(circuit, qreg_q[0], qreg_q[2])
circuit.h(qreg_q[0])
circuit.cp(-math.pi/2, qreg_q[0], qreg_q[1])
circuit.h(qreg_q[1])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
