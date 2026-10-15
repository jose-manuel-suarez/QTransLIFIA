# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def rz_pi_2(w0):
    qml.RZ(math.pi/2, wires=w0)

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
    rz_pi_2(6)
    qml.Hadamard(wires=0)
    measurement_0_0 = qml.measure(wires=0)
    return (
        qml.sample(measurement_0_0),
    )
