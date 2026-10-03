# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=3, shots=None)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.PauliX(wires=1)
    qml.PauliX(wires=2)
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PauliZ, control=[1])(wires=0)
    qml.ctrl(qml.PhaseShift, control=[2])(1.5707963267948966, wires=0)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PauliZ, control=[2])(wires=1)
    qml.Hadamard(wires=2)
    return qml.state()
