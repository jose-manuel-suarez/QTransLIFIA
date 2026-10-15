# Importación de paquetes requeridos
import math
import pennylane as qml

device = qml.device('default.qubit', wires=2, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PhaseShift, control=[1])(math.pi/2, wires=0)
    qml.Hadamard(wires=0)
    qml.SWAP(wires=[0, 1])
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
    )
