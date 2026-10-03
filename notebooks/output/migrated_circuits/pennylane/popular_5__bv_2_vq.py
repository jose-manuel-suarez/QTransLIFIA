# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=2, shots=None)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.PauliX(wires=1)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PauliX, control=[0])(wires=1)
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    return qml.state()
