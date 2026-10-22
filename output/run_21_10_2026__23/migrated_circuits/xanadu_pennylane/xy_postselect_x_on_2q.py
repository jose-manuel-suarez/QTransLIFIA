# Importación de paquetes requeridos
import math
import pennylane as qml

device = qml.device('default.qubit', wires=2, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.PauliZ(wires=0)
    qml.PauliZ(wires=1)
    qml.Hadamard(wires=0)
    measurement_2_0 = qml.measure(wires=0)
    qml.Hadamard(wires=1)
    measurement_3_1 = qml.measure(wires=1)
    measurement_0_2 = qml.measure(wires=0)
    measurement_1_3 = qml.measure(wires=1)
    return (
        qml.sample(measurement_0_2),
        qml.sample(measurement_1_3),
        qml.sample(measurement_2_0),
        qml.sample(measurement_3_1),
    )
