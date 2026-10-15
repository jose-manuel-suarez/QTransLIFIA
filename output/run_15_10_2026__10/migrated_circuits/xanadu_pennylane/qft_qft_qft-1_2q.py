# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def QFT2(w0, w1):
    qml.Hadamard(wires=w1)
    qml.ctrl(qml.PhaseShift, control=[w1])(math.pi/2, wires=w0)
    qml.Hadamard(wires=w0)
    qml.SWAP(wires=[w0, w1])

def QFT2_dg(w0, w1):
    qml.SWAP(wires=[w0, w1])
    qml.Hadamard(wires=w0)
    qml.ctrl(qml.PhaseShift, control=[w1])(-math.pi/2, wires=w0)
    qml.Hadamard(wires=w1)

device = qml.device('default.qubit', wires=2, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    QFT2(0, 1)
    QFT2_dg(0, 1)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
    )
