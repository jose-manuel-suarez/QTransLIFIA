# Importación de paquetes requeridos
import math
import pennylane as qml

device = qml.device('default.qubit', wires=10, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Hadamard(wires=3)
    qml.Hadamard(wires=4)
    qml.Hadamard(wires=5)
    qml.Hadamard(wires=6)
    qml.Hadamard(wires=7)
    qml.Hadamard(wires=8)
    qml.Hadamard(wires=9)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    measurement_3_3 = qml.measure(wires=3)
    measurement_4_4 = qml.measure(wires=4)
    measurement_5_5 = qml.measure(wires=5)
    measurement_6_6 = qml.measure(wires=6)
    measurement_7_7 = qml.measure(wires=7)
    measurement_8_8 = qml.measure(wires=8)
    measurement_9_9 = qml.measure(wires=9)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
        qml.sample(measurement_3_3),
        qml.sample(measurement_4_4),
        qml.sample(measurement_5_5),
        qml.sample(measurement_6_6),
        qml.sample(measurement_7_7),
        qml.sample(measurement_8_8),
        qml.sample(measurement_9_9),
    )
