# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def sdg_gate(w0):
    qml.PhaseShift(-math.pi/2, wires=w0)

device = qml.device('default.qubit', wires=4, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Hadamard(wires=3)
    qml.PhaseShift(math.pi/2, wires=0)
    qml.PhaseShift(math.pi/2, wires=1)
    qml.PhaseShift(math.pi/2, wires=2)
    qml.PhaseShift(math.pi/2, wires=3)
    sdg_gate(0)
    qml.Hadamard(wires=0)
    measurement_4_0 = qml.measure(wires=0)
    sdg_gate(1)
    qml.Hadamard(wires=1)
    measurement_5_1 = qml.measure(wires=1)
    sdg_gate(2)
    qml.Hadamard(wires=2)
    measurement_6_2 = qml.measure(wires=2)
    sdg_gate(3)
    qml.Hadamard(wires=3)
    measurement_7_3 = qml.measure(wires=3)
    measurement_0_4 = qml.measure(wires=0)
    measurement_1_5 = qml.measure(wires=1)
    measurement_2_6 = qml.measure(wires=2)
    measurement_3_7 = qml.measure(wires=3)
    return (
        qml.sample(measurement_0_4),
        qml.sample(measurement_1_5),
        qml.sample(measurement_2_6),
        qml.sample(measurement_3_7),
        qml.sample(measurement_4_0),
        qml.sample(measurement_5_1),
        qml.sample(measurement_6_2),
        qml.sample(measurement_7_3),
    )
