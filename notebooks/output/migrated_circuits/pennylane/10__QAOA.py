# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=2, shots=1000)

@qml.qnode(device)
def circuit():
    qml.ctrl(qml.PauliX, control=[0])(wires=1)
    qml.ctrl(qml.PauliX, control=[0])(wires=1)
    measurement_1_0 = qml.measure(wires=1)
    measurement_0_1 = qml.measure(wires=0)
    return (
        qml.sample(measurement_0_1),
        qml.sample(measurement_1_0),
    )
