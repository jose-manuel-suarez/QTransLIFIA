# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=14, shots=1000)

@qml.qnode(device)
def circuit():
    qml.RY(1.5707963267948966, wires=0)
    qml.RY(1.5707963267948966, wires=1)
    qml.Hadamard(wires=2)
    qml.RY(1.5707963267948966, wires=3)
    qml.Hadamard(wires=4)
    qml.RY(1.5707963267948966, wires=5)
    qml.RY(1.5707963267948966, wires=6)
    qml.Hadamard(wires=7)
    qml.RY(1.5707963267948966, wires=8)
    qml.RY(1.5707963267948966, wires=9)
    qml.Hadamard(wires=10)
    qml.RY(1.5707963267948966, wires=11)
    qml.RY(1.5707963267948966, wires=12)
    qml.RY(-1.5707963267948966, wires=13)
    qml.ctrl(qml.PauliX, control=[0])(wires=13)
    qml.RY(-1.5707963267948966, wires=0)
    qml.ctrl(qml.PauliX, control=[1])(wires=13)
    qml.RY(-1.5707963267948966, wires=1)
    qml.ctrl(qml.PauliX, control=[2])(wires=13)
    qml.Hadamard(wires=2)
    qml.ctrl(qml.PauliX, control=[3])(wires=13)
    qml.RY(-1.5707963267948966, wires=3)
    qml.ctrl(qml.PauliX, control=[4])(wires=13)
    qml.Hadamard(wires=4)
    qml.ctrl(qml.PauliX, control=[5])(wires=13)
    qml.RY(-1.5707963267948966, wires=5)
    qml.ctrl(qml.PauliX, control=[6])(wires=13)
    qml.RY(-1.5707963267948966, wires=6)
    qml.ctrl(qml.PauliX, control=[7])(wires=13)
    qml.Hadamard(wires=7)
    qml.ctrl(qml.PauliX, control=[8])(wires=13)
    qml.RY(-1.5707963267948966, wires=8)
    qml.ctrl(qml.PauliX, control=[9])(wires=13)
    qml.RY(-1.5707963267948966, wires=9)
    qml.ctrl(qml.PauliX, control=[10])(wires=13)
    qml.Hadamard(wires=10)
    qml.ctrl(qml.PauliX, control=[11])(wires=13)
    qml.RY(-1.5707963267948966, wires=11)
    qml.ctrl(qml.PauliX, control=[12])(wires=13)
    qml.RY(-1.5707963267948966, wires=12)
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
    )
