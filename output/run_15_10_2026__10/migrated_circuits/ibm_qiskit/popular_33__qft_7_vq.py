# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(7, 'q')
creg_c = ClassicalRegister(7, 'c')

# Compuertas personalizadas (funciones locales)
def mcphase(circuit, w0, w1):
    circuit.cp(math.pi/8, w0, w1)

def ccu1_pi_8(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def ccu1_pi_16(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def ccu1_pi_32(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def ccu1_pi_64(circuit, w0, w1):
    mcphase(circuit, w0, w1)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.cp(math.pi/2, qreg_q[0], qreg_q[1])
circuit.cp(math.pi/4, qreg_q[0], qreg_q[2])
ccu1_pi_8(circuit, qreg_q[0], qreg_q[3])
ccu1_pi_16(circuit, qreg_q[0], qreg_q[4])
ccu1_pi_32(circuit, qreg_q[0], qreg_q[5])
ccu1_pi_64(circuit, qreg_q[0], qreg_q[6])
circuit.h(qreg_q[1])
circuit.cp(math.pi/2, qreg_q[1], qreg_q[2])
circuit.cp(math.pi/4, qreg_q[1], qreg_q[3])
ccu1_pi_8(circuit, qreg_q[1], qreg_q[4])
ccu1_pi_16(circuit, qreg_q[1], qreg_q[5])
ccu1_pi_32(circuit, qreg_q[1], qreg_q[6])
circuit.h(qreg_q[2])
circuit.cp(math.pi/2, qreg_q[2], qreg_q[3])
circuit.cp(math.pi/4, qreg_q[2], qreg_q[4])
ccu1_pi_8(circuit, qreg_q[2], qreg_q[5])
ccu1_pi_16(circuit, qreg_q[2], qreg_q[6])
circuit.h(qreg_q[3])
circuit.cp(math.pi/2, qreg_q[3], qreg_q[4])
circuit.cp(math.pi/4, qreg_q[3], qreg_q[5])
ccu1_pi_8(circuit, qreg_q[3], qreg_q[6])
circuit.h(qreg_q[4])
circuit.cp(math.pi/2, qreg_q[4], qreg_q[5])
circuit.cp(math.pi/4, qreg_q[4], qreg_q[6])
circuit.h(qreg_q[5])
circuit.cp(math.pi/2, qreg_q[5], qreg_q[6])
circuit.h(qreg_q[6])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
circuit.measure(qreg_q[3], creg_c[3])
circuit.measure(qreg_q[4], creg_c[4])
circuit.measure(qreg_q[5], creg_c[5])
circuit.measure(qreg_q[6], creg_c[6])
