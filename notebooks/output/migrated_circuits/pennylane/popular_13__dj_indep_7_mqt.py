# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=7, shots=1000)

@qml.qnode(device)
def circuit():
    qml.RY(1.5707963267948966, wires=0)
    qml.RY(1.5707963267948966, wires=1)
    qml.Hadamard(wires=2)
    qml.RY(1.5707963267948966, wires=3)
    qml.Hadamard(wires=4)
    qml.RY(1.5707963267948966, wires=5)
    qml.RY(-1.5707963267948966, wires=6)
    qml.ctrl(qml.PauliX, control=[0])(wires=6)
    qml.RY(-1.5707963267948966, wires=0)
    qml.ctrl(qml.PauliX, control=[1])(wires=6)
    qml.RY(-1.5707963267948966, wires=1)
    qml.ctrl(qml.PauliX, control=[2])(wires=6)
    qml.Hadamard(wires=2)
    qml.ctrl(qml.PauliX, control=[3])(wires=6)
    qml.RY(-1.5707963267948966, wires=3)
    qml.ctrl(qml.PauliX, control=[4])(wires=6)
    qml.Hadamard(wires=4)
    qml.ctrl(qml.PauliX, control=[5])(wires=6)
    qml.RY(-1.5707963267948966, wires=5)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    measurement_3_3 = qml.measure(wires=3)
    measurement_4_4 = qml.measure(wires=4)
    measurement_5_5 = qml.measure(wires=5)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
        qml.sample(measurement_3_3),
        qml.sample(measurement_4_4),
        qml.sample(measurement_5_5),
    )
