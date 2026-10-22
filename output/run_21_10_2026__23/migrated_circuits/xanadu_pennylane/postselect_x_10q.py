# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def sdg_gate(w0):
    qml.PhaseShift(-math.pi/2, wires=w0)

device = qml.device('default.qubit', wires=10, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    qml.Hadamard(wires=2)
    qml.Hadamard(wires=3)
    qml.Hadamard(wires=4)
    qml.Hadamard(wires=5)
    qml.Hadamard(wires=6)
    qml.Hadamard(wires=7)
    qml.Hadamard(wires=8)
    qml.Hadamard(wires=9)
    qml.PhaseShift(math.pi/2, wires=0)
    qml.PhaseShift(math.pi/2, wires=1)
    qml.PhaseShift(math.pi/2, wires=2)
    qml.PhaseShift(math.pi/2, wires=3)
    qml.PhaseShift(math.pi/2, wires=4)
    qml.PhaseShift(math.pi/2, wires=5)
    qml.PhaseShift(math.pi/2, wires=6)
    qml.PhaseShift(math.pi/2, wires=7)
    qml.PhaseShift(math.pi/2, wires=8)
    qml.PhaseShift(math.pi/2, wires=9)
    sdg_gate(0)
    qml.Hadamard(wires=0)
    measurement_10_0 = qml.measure(wires=0)
    sdg_gate(1)
    qml.Hadamard(wires=1)
    measurement_11_1 = qml.measure(wires=1)
    sdg_gate(2)
    qml.Hadamard(wires=2)
    measurement_12_2 = qml.measure(wires=2)
    sdg_gate(3)
    qml.Hadamard(wires=3)
    measurement_13_3 = qml.measure(wires=3)
    sdg_gate(4)
    qml.Hadamard(wires=4)
    measurement_14_4 = qml.measure(wires=4)
    sdg_gate(5)
    qml.Hadamard(wires=5)
    measurement_15_5 = qml.measure(wires=5)
    sdg_gate(6)
    qml.Hadamard(wires=6)
    measurement_16_6 = qml.measure(wires=6)
    sdg_gate(7)
    qml.Hadamard(wires=7)
    measurement_17_7 = qml.measure(wires=7)
    sdg_gate(8)
    qml.Hadamard(wires=8)
    measurement_18_8 = qml.measure(wires=8)
    sdg_gate(9)
    qml.Hadamard(wires=9)
    measurement_19_9 = qml.measure(wires=9)
    measurement_0_10 = qml.measure(wires=0)
    measurement_1_11 = qml.measure(wires=1)
    measurement_2_12 = qml.measure(wires=2)
    measurement_3_13 = qml.measure(wires=3)
    measurement_4_14 = qml.measure(wires=4)
    measurement_5_15 = qml.measure(wires=5)
    measurement_6_16 = qml.measure(wires=6)
    measurement_7_17 = qml.measure(wires=7)
    measurement_8_18 = qml.measure(wires=8)
    measurement_9_19 = qml.measure(wires=9)
    return (
        qml.sample(measurement_0_10),
        qml.sample(measurement_1_11),
        qml.sample(measurement_2_12),
        qml.sample(measurement_3_13),
        qml.sample(measurement_4_14),
        qml.sample(measurement_5_15),
        qml.sample(measurement_6_16),
        qml.sample(measurement_7_17),
        qml.sample(measurement_8_18),
        qml.sample(measurement_9_19),
        qml.sample(measurement_10_0),
        qml.sample(measurement_11_1),
        qml.sample(measurement_12_2),
        qml.sample(measurement_13_3),
        qml.sample(measurement_14_4),
        qml.sample(measurement_15_5),
        qml.sample(measurement_16_6),
        qml.sample(measurement_17_7),
        qml.sample(measurement_18_8),
        qml.sample(measurement_19_9),
    )
