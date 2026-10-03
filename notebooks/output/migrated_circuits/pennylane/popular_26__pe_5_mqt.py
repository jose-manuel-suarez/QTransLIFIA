# Importación de paquetes requeridos
import pennylane as qml

device = qml.device('default.qubit', wires=5, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Hadamard(wires=3)
    qml.PauliX(wires=4)
    qml.ctrl(qml.PhaseShift, control=[4])(-2.748893571891069, wires=0)
    qml.ctrl(qml.PhaseShift, control=[4])(0.7853981633974483, wires=1)
    qml.ctrl(qml.PhaseShift, control=[4])(1.5707963267948966, wires=2)
    qml.SWAP(wires=[1, 2])
    qml.ctrl(qml.PauliZ, control=[4])(wires=3)
    qml.SWAP(wires=[0, 3])
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PhaseShift, control=[1])(-1.5707963267948966, wires=0)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PhaseShift, control=[2])(-0.7853981633974483, wires=0)
    qml.ctrl(qml.PhaseShift, control=[2])(-1.5707963267948966, wires=1)
    qml.Hadamard(wires=2)
    qml.ctrl(qml.PhaseShift, control=[3])(-0.39269908169872414, wires=0)
    qml.ctrl(qml.PhaseShift, control=[3])(-0.7853981633974483, wires=1)
    qml.ctrl(qml.PhaseShift, control=[3])(-1.5707963267948966, wires=2)
    qml.Hadamard(wires=3)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    measurement_3_3 = qml.measure(wires=3)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
        qml.sample(measurement_3_3),
    )
