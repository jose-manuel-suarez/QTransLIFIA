# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=16, shots=1000)

@qml.qnode(device)
def circuit():
    qml.ctrl(qml.PauliX, control=[1, 2])(wires=3)
    qml.ctrl(qml.PauliX, control=[1])(wires=2)
    qml.ctrl(qml.PauliX, control=[4, 5])(wires=6)
    qml.ctrl(qml.PauliX, control=[4])(wires=5)
    qml.ctrl(qml.PauliX, control=[7, 8])(wires=9)
    qml.ctrl(qml.PauliX, control=[7])(wires=8)
    qml.ctrl(qml.PauliX, control=[10, 11])(wires=12)
    qml.ctrl(qml.PauliX, control=[10])(wires=11)
    qml.ctrl(qml.PauliX, control=[13, 14])(wires=15)
    qml.ctrl(qml.PauliX, control=[13])(wires=14)
    qml.ctrl(qml.PauliX, control=[0, 2])(wires=3)
    qml.ctrl(qml.PauliX, control=[3, 5])(wires=6)
    qml.ctrl(qml.PauliX, control=[6, 8])(wires=9)
    qml.ctrl(qml.PauliX, control=[9, 11])(wires=12)
    qml.ctrl(qml.PauliX, control=[12, 14])(wires=15)
    qml.ctrl(qml.PauliX, control=[0])(wires=2)
    qml.ctrl(qml.PauliX, control=[3])(wires=5)
    qml.ctrl(qml.PauliX, control=[6])(wires=8)
    qml.ctrl(qml.PauliX, control=[9])(wires=11)
    qml.ctrl(qml.PauliX, control=[12])(wires=14)
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
    measurement_10_10 = qml.measure(wires=10)
    measurement_11_11 = qml.measure(wires=11)
    measurement_12_12 = qml.measure(wires=12)
    measurement_13_13 = qml.measure(wires=13)
    measurement_14_14 = qml.measure(wires=14)
    measurement_15_15 = qml.measure(wires=15)
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
        qml.sample(measurement_10_10),
        qml.sample(measurement_11_11),
        qml.sample(measurement_12_12),
        qml.sample(measurement_13_13),
        qml.sample(measurement_14_14),
        qml.sample(measurement_15_15),
    )
