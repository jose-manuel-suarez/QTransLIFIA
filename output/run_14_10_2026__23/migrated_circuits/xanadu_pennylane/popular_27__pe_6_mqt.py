# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def ccp_7_pi_8(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(-7*math.pi/8, wires=w1)

def ccp_pi_8(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(-math.pi/8, wires=w1)

def ccp_pi_16(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(-math.pi/16, wires=w1)

device = qml.device('default.qubit', wires=6, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Hadamard(wires=3)
    qml.Hadamard(wires=4)
    qml.PauliX(wires=5)
    ccp_7_pi_8(5, 0)
    qml.SWAP(wires=[0, 4])
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PhaseShift, control=[5])(math.pi/4, wires=1)
    qml.ctrl(qml.PhaseShift, control=[5])(math.pi/2, wires=2)
    qml.ctrl(qml.PauliZ, control=[5])(wires=3)
    qml.SWAP(wires=[1, 3])
    qml.ctrl(qml.PhaseShift, control=[1])(-math.pi/2, wires=0)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PhaseShift, control=[2])(-math.pi/4, wires=0)
    qml.ctrl(qml.PhaseShift, control=[2])(-math.pi/2, wires=1)
    qml.Hadamard(wires=2)
    ccp_pi_8(3, 0)
    qml.ctrl(qml.PhaseShift, control=[3])(-math.pi/4, wires=1)
    qml.ctrl(qml.PhaseShift, control=[3])(-math.pi/2, wires=2)
    qml.Hadamard(wires=3)
    ccp_pi_16(4, 0)
    ccp_pi_8(4, 1)
    qml.ctrl(qml.PhaseShift, control=[4])(-math.pi/4, wires=2)
    qml.ctrl(qml.PhaseShift, control=[4])(-math.pi/2, wires=3)
    qml.Hadamard(wires=4)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    measurement_3_3 = qml.measure(wires=3)
    measurement_4_4 = qml.measure(wires=4)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
        qml.sample(measurement_3_3),
        qml.sample(measurement_4_4),
    )
