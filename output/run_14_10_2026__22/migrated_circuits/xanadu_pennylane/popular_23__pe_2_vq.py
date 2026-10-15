# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def ccu1_pi_512(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/512, wires=w1)

def ccu1_pi_256(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/256, wires=w1)

device = qml.device('default.qubit', wires=3, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.Hadamard(wires=1)
    ccu1_pi_512(1, 2)
    ccu1_pi_256(0, 2)
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PhaseShift, control=[0])(-math.pi/2, wires=1)
    qml.Hadamard(wires=1)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
    )
