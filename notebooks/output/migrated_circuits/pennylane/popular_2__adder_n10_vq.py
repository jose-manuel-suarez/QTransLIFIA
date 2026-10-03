# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=10, shots=None)

@qml.qnode(device)
def circuit():
    qml.ctrl(qml.PauliX, control=[1, 2])(wires=3)
    qml.ctrl(qml.PauliX, control=[1])(wires=2)
    qml.ctrl(qml.PauliX, control=[4, 5])(wires=6)
    qml.ctrl(qml.PauliX, control=[4])(wires=5)
    qml.ctrl(qml.PauliX, control=[7, 8])(wires=9)
    qml.ctrl(qml.PauliX, control=[7])(wires=8)
    qml.ctrl(qml.PauliX, control=[0, 2])(wires=3)
    qml.ctrl(qml.PauliX, control=[3, 5])(wires=6)
    qml.ctrl(qml.PauliX, control=[6, 8])(wires=9)
    qml.ctrl(qml.PauliX, control=[0])(wires=2)
    qml.ctrl(qml.PauliX, control=[3])(wires=5)
    qml.ctrl(qml.PauliX, control=[6])(wires=8)
    return qml.state()
