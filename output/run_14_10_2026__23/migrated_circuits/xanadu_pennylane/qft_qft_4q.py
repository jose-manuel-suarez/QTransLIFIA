# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def QFT4(w0, w1, w2, w3):
    qml.Hadamard(wires=w3)
    qml.ctrl(qml.PhaseShift, control=[w3])(math.pi/2, wires=w2)
    qml.ctrl(qml.PhaseShift, control=[w3])(math.pi/4, wires=w1)
    qml.ctrl(qml.PhaseShift, control=[w3])(math.pi/8, wires=w0)
    qml.Hadamard(wires=w2)
    qml.ctrl(qml.PhaseShift, control=[w2])(math.pi/2, wires=w1)
    qml.ctrl(qml.PhaseShift, control=[w2])(math.pi/4, wires=w0)
    qml.Hadamard(wires=w1)
    qml.ctrl(qml.PhaseShift, control=[w1])(math.pi/2, wires=w0)
    qml.Hadamard(wires=w0)
    qml.SWAP(wires=[w0, w3])
    qml.SWAP(wires=[w1, w2])

device = qml.device('default.qubit', wires=4, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Hadamard(wires=3)
    QFT4(0, 1, 2, 3)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    measurement_3_3 = qml.measure(wires=3)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
        qml.sample(measurement_3_3),
    )
