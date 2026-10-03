# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=14, shots=1000)

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
    qml.Hadamard(wires=10)
    qml.Hadamard(wires=11)
    qml.Hadamard(wires=12)
    qml.PauliX(wires=13)
    qml.Hadamard(wires=13)
    qml.ctrl(qml.PauliX, control=[0])(wires=13)
    qml.ctrl(qml.PauliX, control=[1])(wires=13)
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PauliX, control=[2])(wires=13)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PauliX, control=[3])(wires=13)
    qml.Hadamard(wires=2)
    qml.ctrl(qml.PauliX, control=[4])(wires=13)
    qml.Hadamard(wires=3)
    qml.ctrl(qml.PauliX, control=[5])(wires=13)
    qml.Hadamard(wires=4)
    qml.ctrl(qml.PauliX, control=[6])(wires=13)
    qml.Hadamard(wires=5)
    qml.ctrl(qml.PauliX, control=[7])(wires=13)
    qml.Hadamard(wires=6)
    qml.ctrl(qml.PauliX, control=[8])(wires=13)
    qml.Hadamard(wires=7)
    qml.ctrl(qml.PauliX, control=[9])(wires=13)
    qml.Hadamard(wires=8)
    qml.ctrl(qml.PauliX, control=[10])(wires=13)
    qml.Hadamard(wires=9)
    measurement_9_0 = qml.measure(wires=9)
    qml.ctrl(qml.PauliX, control=[11])(wires=13)
    qml.Hadamard(wires=10)
    measurement_10_1 = qml.measure(wires=10)
    qml.ctrl(qml.PauliX, control=[12])(wires=13)
    qml.Hadamard(wires=11)
    measurement_11_2 = qml.measure(wires=11)
    qml.Hadamard(wires=12)
    qml.Hadamard(wires=13)
    measurement_0_3 = qml.measure(wires=0)
    measurement_1_4 = qml.measure(wires=1)
    measurement_2_5 = qml.measure(wires=2)
    measurement_3_6 = qml.measure(wires=3)
    measurement_4_7 = qml.measure(wires=4)
    measurement_6_8 = qml.measure(wires=6)
    measurement_7_9 = qml.measure(wires=7)
    measurement_8_10 = qml.measure(wires=8)
    measurement_12_11 = qml.measure(wires=12)
    measurement_13_12 = qml.measure(wires=13)
    return (
        qml.sample(measurement_0_3),
        qml.sample(measurement_1_4),
        qml.sample(measurement_2_5),
        qml.sample(measurement_3_6),
        qml.sample(measurement_4_7),
        qml.sample(measurement_6_8),
        qml.sample(measurement_7_9),
        qml.sample(measurement_8_10),
        qml.sample(measurement_9_0),
        qml.sample(measurement_10_1),
        qml.sample(measurement_11_2),
        qml.sample(measurement_12_11),
        qml.sample(measurement_13_12),
    )
