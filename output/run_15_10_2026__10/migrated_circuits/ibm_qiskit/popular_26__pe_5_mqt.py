# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(5, 'q')
creg_c = ClassicalRegister(5, 'c')

# Compuertas personalizadas (funciones locales)
def mcphase(circuit, w0, w1):
    circuit.cp(-7*math.pi/8, w0, w1)

def ccp_7_pi_8(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def ccp_pi_8(circuit, w0, w1):
    mcphase(circuit, w0, w1)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
circuit.h(qreg_q[2])
circuit.h(qreg_q[3])
circuit.x(qreg_q[4])
ccp_7_pi_8(circuit, qreg_q[4], qreg_q[0])
circuit.cp(math.pi/4, qreg_q[4], qreg_q[1])
circuit.cp(math.pi/2, qreg_q[4], qreg_q[2])
circuit.swap(qreg_q[1], qreg_q[2])
circuit.cz(qreg_q[4], qreg_q[3])
circuit.swap(qreg_q[0], qreg_q[3])
circuit.h(qreg_q[0])
circuit.cp(-math.pi/2, qreg_q[1], qreg_q[0])
circuit.h(qreg_q[1])
circuit.cp(-math.pi/4, qreg_q[2], qreg_q[0])
circuit.cp(-math.pi/2, qreg_q[2], qreg_q[1])
circuit.h(qreg_q[2])
ccp_pi_8(circuit, qreg_q[3], qreg_q[0])
circuit.cp(-math.pi/4, qreg_q[3], qreg_q[1])
circuit.cp(-math.pi/2, qreg_q[3], qreg_q[2])
circuit.h(qreg_q[3])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
circuit.measure(qreg_q[3], creg_c[3])
