# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def mia(w0, w1):
    qml.PhaseShift(1.022086548338751, wires=w0)
    qml.RZ(-1.022086548338751, wires=w0)
    qml.U3(2.6572556550648576, -0.7494504172766678, 1.6303968037558327, wires=w0)
    qml.U3(1.7722832659115826, 1.7993318097017053, -0.15769545148268982, wires=w1)
    qml.ctrl(qml.PauliX, control=[w0])(wires=w1)
    qml.U3(0.6610620143917973, -math.pi/2, math.pi/2, wires=w0)
    qml.U3(1.146322550785802, -0.6825452469363378, -0.4689493306248971, wires=w1)
    qml.ctrl(qml.PauliX, control=[w0])(wires=w1)
    qml.U3(0.4249056861253225, 0, -math.pi/2, wires=w0)
    qml.U3(1.047197551196598, 2.526112944919406, -0.6154797086703869, wires=w1)
    qml.ctrl(qml.PauliX, control=[w0])(wires=w1)
    qml.U3(1.661438225728421, -1.939568706812894, 0.7979501493332246, wires=w0)
    qml.U3(0.899625573385694, 0.41532997728071486, -1.6762487268948827, wires=w1)

def ccu1_pi_512(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/512, wires=w1)

def ccu1_pi_256(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/256, wires=w1)

def jo(w0):
    qml.PhaseShift(0.34906596460815587, wires=w0)
    qml.RZ(-0.34906596460815587, wires=w0)
    qml.RZ(math.pi/2, wires=w0)
    qml.RY(0.5235988043049772, wires=w0)
    qml.RZ(-math.pi/2, wires=w0)

def gate_3ejes(w0):
    qml.RZ(1.020135819677448, wires=w0)
    qml.RY(0.6355626524430418, wires=w0)
    qml.RZ(-0.5506605071174487, wires=w0)

device = qml.device('default.qubit', wires=2, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    mia(0, 1)
    ccu1_pi_512(1, 0)
    ccu1_pi_256(0, 1)
    jo(0)
    gate_3ejes(1)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
    )
