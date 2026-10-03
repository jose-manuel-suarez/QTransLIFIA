# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=5, shots=1000)

@qml.qnode(device)
def circuit():
    qml.PauliX(wires=2)
    qml.PauliX(wires=3)
    qml.PauliX(wires=4)
    qml.PauliX(wires=1)
    qml.PauliX(wires=2)
    qml.PauliX(wires=3)
    qml.PauliX(wires=4)
    qml.ctrl(qml.PauliX, control=[3])(wires=2)
    qml.ctrl(qml.PauliX, control=[2])(wires=3)
    qml.ctrl(qml.PauliX, control=[3])(wires=2)
    qml.ctrl(qml.PauliX, control=[2])(wires=1)
    qml.ctrl(qml.PauliX, control=[1])(wires=2)
    qml.ctrl(qml.PauliX, control=[2])(wires=1)
    qml.ctrl(qml.PauliX, control=[4])(wires=1)
    qml.ctrl(qml.PauliX, control=[1])(wires=4)
    qml.ctrl(qml.PauliX, control=[4])(wires=1)
    measurement_1_0 = qml.measure(wires=1)
    measurement_2_1 = qml.measure(wires=2)
    measurement_3_2 = qml.measure(wires=3)
    measurement_4_3 = qml.measure(wires=4)
    return (
        qml.sample(measurement_1_0),
        qml.sample(measurement_2_1),
        qml.sample(measurement_3_2),
        qml.sample(measurement_4_3),
    )
