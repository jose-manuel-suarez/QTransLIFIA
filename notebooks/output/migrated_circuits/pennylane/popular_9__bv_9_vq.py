# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=9, shots=1000)

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
    qml.PauliX(wires=8)
    qml.Hadamard(wires=8)
    qml.ctrl(qml.PauliX, control=[0])(wires=8)
    qml.ctrl(qml.PauliX, control=[1])(wires=8)
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PauliX, control=[2])(wires=8)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PauliX, control=[3])(wires=8)
    qml.Hadamard(wires=2)
    qml.ctrl(qml.PauliX, control=[4])(wires=8)
    qml.Hadamard(wires=3)
    qml.ctrl(qml.PauliX, control=[5])(wires=8)
    qml.Hadamard(wires=4)
    qml.ctrl(qml.PauliX, control=[6])(wires=8)
    qml.Hadamard(wires=5)
    measurement_5_0 = qml.measure(wires=5)
    qml.ctrl(qml.PauliX, control=[7])(wires=8)
    qml.Hadamard(wires=6)
    qml.Hadamard(wires=7)
    qml.Hadamard(wires=8)
    measurement_0_1 = qml.measure(wires=0)
    measurement_1_2 = qml.measure(wires=1)
    measurement_2_3 = qml.measure(wires=2)
    measurement_3_4 = qml.measure(wires=3)
    measurement_4_5 = qml.measure(wires=4)
    measurement_6_6 = qml.measure(wires=6)
    measurement_7_7 = qml.measure(wires=7)
    measurement_8_8 = qml.measure(wires=8)
    return (
        qml.sample(measurement_0_1),
        qml.sample(measurement_1_2),
        qml.sample(measurement_2_3),
        qml.sample(measurement_3_4),
        qml.sample(measurement_4_5),
        qml.sample(measurement_5_0),
        qml.sample(measurement_6_6),
        qml.sample(measurement_7_7),
        qml.sample(measurement_8_8),
    )
