# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(2, 'q')
creg_c = ClassicalRegister(2, 'c')

# Compuertas personalizadas (funciones locales)
def mia(circuit, w0, w1):
    circuit.p(1.022086548338751, w0)
    circuit.rz(-1.022086548338751, w0)
    circuit.u(2.6572556550648576, -0.7494504172766678, 1.6303968037558327, w0)
    circuit.u(1.7722832659115826, 1.7993318097017053, -0.15769545148268982, w1)
    circuit.cx(w0, w1)
    circuit.u(0.6610620143917973, -math.pi/2, math.pi/2, w0)
    circuit.u(1.146322550785802, -0.6825452469363378, -0.4689493306248971, w1)
    circuit.cx(w0, w1)
    circuit.u(0.4249056861253225, 0, -math.pi/2, w0)
    circuit.u(1.047197551196598, 2.526112944919406, -0.6154797086703869, w1)
    circuit.cx(w0, w1)
    circuit.u(1.661438225728421, -1.939568706812894, 0.7979501493332246, w0)
    circuit.u(0.899625573385694, 0.41532997728071486, -1.6762487268948827, w1)

def mcphase(circuit, w0, w1):
    circuit.cp(math.pi/512, w0, w1)

def ccu1_pi_512(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def ccu1_pi_256(circuit, w0, w1):
    mcphase(circuit, w0, w1)

def jo(circuit, w0):
    circuit.p(0.34906596460815587, w0)
    circuit.rz(-0.34906596460815587, w0)
    circuit.rz(math.pi/2, w0)
    circuit.ry(0.5235988043049772, w0)
    circuit.rz(-math.pi/2, w0)

def gate_3ejes(circuit, w0):
    circuit.rz(1.020135819677448, w0)
    circuit.ry(0.6355626524430418, w0)
    circuit.rz(-0.5506605071174487, w0)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

circuit.h(qreg_q[0])
circuit.h(qreg_q[1])
mia(circuit, qreg_q[0], qreg_q[1])
ccu1_pi_512(circuit, qreg_q[1], qreg_q[0])
ccu1_pi_256(circuit, qreg_q[0], qreg_q[1])
jo(circuit, qreg_q[0])
gate_3ejes(circuit, qreg_q[1])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
