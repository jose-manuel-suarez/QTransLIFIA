# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=5, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PauliX, control=[1])(wires=4)
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PauliX, control=[0])(wires=1)
    qml.Hadamard(wires=0)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    qml.ctrl(qml.PauliX, control=[1])(wires=4)
    qml.ctrl(qml.PauliZ, control=[0])(wires=4)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
    )
