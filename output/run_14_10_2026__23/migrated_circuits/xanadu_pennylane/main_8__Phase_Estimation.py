# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def cU_pi_2(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(-math.pi/2, wires=w1)

def cU_pi_4(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(-math.pi/4, wires=w1)

device = qml.device('default.qubit', wires=4, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.PauliX(wires=3)
    qml.ctrl(qml.PhaseShift, control=[0])(math.pi/4, wires=3)
    qml.ctrl(qml.PhaseShift, control=[1])(math.pi/4, wires=3)
    qml.ctrl(qml.PhaseShift, control=[1])(math.pi/4, wires=3)
    qml.ctrl(qml.PhaseShift, control=[2])(math.pi/4, wires=3)
    qml.ctrl(qml.PhaseShift, control=[2])(math.pi/4, wires=3)
    qml.ctrl(qml.PhaseShift, control=[2])(math.pi/4, wires=3)
    qml.ctrl(qml.PhaseShift, control=[2])(math.pi/4, wires=3)
    qml.SWAP(wires=[0, 2])
    qml.Hadamard(wires=0)
    cU_pi_2(0, 1)
    qml.Hadamard(wires=1)
    cU_pi_4(0, 2)
    cU_pi_2(1, 2)
    qml.Hadamard(wires=2)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
    )
