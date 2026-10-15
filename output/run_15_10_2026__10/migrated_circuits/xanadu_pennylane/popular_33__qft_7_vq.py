# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def ccu1_pi_8(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/8, wires=w1)

def ccu1_pi_16(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/16, wires=w1)

def ccu1_pi_32(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/32, wires=w1)

def ccu1_pi_64(w0, w1):
    qml.ctrl(qml.PhaseShift, control=[w0])(math.pi/64, wires=w1)

device = qml.device('default.qubit', wires=7, shots=1000)

@qml.qnode(device)
def circuit():
    qml.Hadamard(wires=0)
    qml.ctrl(qml.PhaseShift, control=[0])(math.pi/2, wires=1)
    qml.ctrl(qml.PhaseShift, control=[0])(math.pi/4, wires=2)
    ccu1_pi_8(0, 3)
    ccu1_pi_16(0, 4)
    ccu1_pi_32(0, 5)
    ccu1_pi_64(0, 6)
    qml.Hadamard(wires=1)
    qml.ctrl(qml.PhaseShift, control=[1])(math.pi/2, wires=2)
    qml.ctrl(qml.PhaseShift, control=[1])(math.pi/4, wires=3)
    ccu1_pi_8(1, 4)
    ccu1_pi_16(1, 5)
    ccu1_pi_32(1, 6)
    qml.Hadamard(wires=2)
    qml.ctrl(qml.PhaseShift, control=[2])(math.pi/2, wires=3)
    qml.ctrl(qml.PhaseShift, control=[2])(math.pi/4, wires=4)
    ccu1_pi_8(2, 5)
    ccu1_pi_16(2, 6)
    qml.Hadamard(wires=3)
    qml.ctrl(qml.PhaseShift, control=[3])(math.pi/2, wires=4)
    qml.ctrl(qml.PhaseShift, control=[3])(math.pi/4, wires=5)
    ccu1_pi_8(3, 6)
    qml.Hadamard(wires=4)
    qml.ctrl(qml.PhaseShift, control=[4])(math.pi/2, wires=5)
    qml.ctrl(qml.PhaseShift, control=[4])(math.pi/4, wires=6)
    qml.Hadamard(wires=5)
    qml.ctrl(qml.PhaseShift, control=[5])(math.pi/2, wires=6)
    qml.Hadamard(wires=6)
    measurement_0_0 = qml.measure(wires=0)
    measurement_1_1 = qml.measure(wires=1)
    measurement_2_2 = qml.measure(wires=2)
    measurement_3_3 = qml.measure(wires=3)
    measurement_4_4 = qml.measure(wires=4)
    measurement_5_5 = qml.measure(wires=5)
    measurement_6_6 = qml.measure(wires=6)
    return (
        qml.sample(measurement_0_0),
        qml.sample(measurement_1_1),
        qml.sample(measurement_2_2),
        qml.sample(measurement_3_3),
        qml.sample(measurement_4_4),
        qml.sample(measurement_5_5),
        qml.sample(measurement_6_6),
    )
