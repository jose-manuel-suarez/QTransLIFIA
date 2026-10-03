# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=7, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PauliX, control=[0])(wires=1)
    qml.ctrl(qml.PauliX, control=[1])(wires=2)
    qml.ctrl(qml.PauliX, control=[2])(wires=3)
    qml.ctrl(qml.PauliX, control=[3])(wires=4)
    qml.ctrl(qml.PauliX, control=[4])(wires=5)
    qml.ctrl(qml.PauliX, control=[5])(wires=6)
    qml.RZ(1.5707963267948966, wires=6)
    qml.Hadamard(wires=0)
    measurement_0_0 = qml.measure(wires=0)
    return (
        qml.sample(measurement_0_0),
    )
