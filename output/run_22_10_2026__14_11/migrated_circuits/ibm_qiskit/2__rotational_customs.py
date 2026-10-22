# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(2, 'q')
creg_c = ClassicalRegister(2, 'c')

# Compuertas personalizadas (funciones locales)
def gate_4x4(circuit, w0, w1):
    circuit.p(math.pi, w0)
    circuit.rz(-math.pi, w0)
    circuit.u(math.pi/2, math.pi/2, 7*math.pi/8, w0)
    circuit.u(3*math.pi/4, math.pi/2, 5*math.pi/8, w1)
    circuit.cx(w0, w1)
    circuit.u(3*math.pi/4, -math.pi, -math.pi/2, w0)
    circuit.u(1.717771517458402, 2.100699116543823, -2.100699116543823, w1)
    circuit.cx(w0, w1)
    circuit.u(math.pi/2, -7*math.pi/8, -math.pi, w0)
    circuit.u(math.pi/4, 3*math.pi/8, math.pi/2, w1)

def x20(circuit, w0):
    circuit.rz(math.pi/2, w0)
    circuit.ry(0.3490658780677359, w0)
    circuit.rz(-math.pi/2, w0)

def xy20(circuit, w0):
    circuit.rz(math.pi/4, w0)
    circuit.ry(0.3490658230247752, w0)
    circuit.rz(-math.pi/4, w0)

def xyz20(circuit, w0):
    circuit.rz(0.8868510524774622, w0)
    circuit.ry(0.28452497409551086, w0)
    circuit.rz(-0.6839452743174339, w0)

def y20(circuit, w0):
    circuit.ry(0.3490658780677359, w0)

def z20(circuit, w0):
    circuit.rz(0.17453293903386796, w0)
    circuit.rz(0.17453293903386796, w0)

def xz20(circuit, w0):
    circuit.rz(1.6948381952856677, w0)
    circuit.ry(0.24619689757124866, w0)
    circuit.rz(-1.4467544583041254, w0)

def yz20(circuit, w0):
    circuit.rz(0.12404186849077121, w0)
    circuit.ry(0.24619689757124866, w0)
    circuit.rz(0.12404186849077121, w0)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
gate_4x4(circuit, qreg_q[0], qreg_q[1])
