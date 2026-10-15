# Importación de paquetes requeridos
import math
import pennylane as qml

# Compuertas personalizadas (funciones locales)
def ry_0_3639515108210906(w0):
    qml.RY(0.3639515108210906, wires=w0)

def ry_3_635990261432437(w0):
    qml.RY(-3.635990261432437, wires=w0)

def ry_1_002813228816168(w0):
    qml.RY(-1.002813228816168, wires=w0)

def ry_3_362268080070584(w0):
    qml.RY(3.362268080070584, wires=w0)

def ry_6_243016014063322(w0):
    qml.RY(6.243016014063322, wires=w0)

def ry_0_8811055252112134(w0):
    qml.RY(0.8811055252112134, wires=w0)

def ry_2_9808572300959044(w0):
    qml.RY(2.9808572300959044, wires=w0)

def ry_3_076180161567417(w0):
    qml.RY(3.076180161567417, wires=w0)

def ry_3_5997755951020247(w0):
    qml.RY(3.5997755951020247, wires=w0)

def ry_3_8705959422613034(w0):
    qml.RY(-3.8705959422613034, wires=w0)

def ry_1_9599706708457578(w0):
    qml.RY(-1.9599706708457578, wires=w0)

def ry_4_560604436086811(w0):
    qml.RY(4.560604436086811, wires=w0)

def ry_3_836947786309806(w0):
    qml.RY(3.836947786309806, wires=w0)

def ry_3_6364557194733527(w0):
    qml.RY(-3.6364557194733527, wires=w0)

def ry_5_8061284709341265(w0):
    qml.RY(5.8061284709341265, wires=w0)

def ry_3_8237047898941157(w0):
    qml.RY(-3.8237047898941157, wires=w0)

def ry_5_382258257999492(w0):
    qml.RY(5.382258257999492, wires=w0)

def ry_0_4608030009462126(w0):
    qml.RY(0.4608030009462126, wires=w0)

def ry_5_991413266982324(w0):
    qml.RY(5.991413266982324, wires=w0)

def ry_3_1604705609650257(w0):
    qml.RY(-3.1604705609650257, wires=w0)

def ry_3_8085796950542656(w0):
    qml.RY(-3.8085796950542656, wires=w0)

def ry_6_4608361773846(w0):
    qml.RY(6.4608361773846, wires=w0)

def ry_2_709332149091332(w0):
    qml.RY(-2.709332149091332, wires=w0)

def ry_1_6710555259169388(w0):
    qml.RY(1.6710555259169388, wires=w0)

device = qml.device('default.qubit', wires=4, shots=1000)

@qml.qnode(device)
def circuit():
    ry_0_3639515108210906(0)
    ry_3_635990261432437(1)
    qml.ctrl(qml.PauliZ, control=[0])(wires=1)
    ry_1_002813228816168(0)
    ry_3_362268080070584(2)
    qml.ctrl(qml.PauliZ, control=[1])(wires=2)
    ry_6_243016014063322(1)
    qml.ctrl(qml.PauliZ, control=[0])(wires=1)
    ry_0_8811055252112134(0)
    ry_2_9808572300959044(3)
    qml.ctrl(qml.PauliZ, control=[2])(wires=3)
    ry_3_076180161567417(2)
    qml.ctrl(qml.PauliZ, control=[1])(wires=2)
    ry_3_5997755951020247(1)
    qml.ctrl(qml.PauliZ, control=[0])(wires=1)
    ry_3_8705959422613034(0)
    ry_1_9599706708457578(3)
    qml.ctrl(qml.PauliZ, control=[2])(wires=3)
    ry_4_560604436086811(2)
    qml.ctrl(qml.PauliZ, control=[1])(wires=2)
    ry_3_836947786309806(1)
    qml.ctrl(qml.PauliZ, control=[0])(wires=1)
    ry_3_6364557194733527(0)
    ry_5_8061284709341265(3)
    qml.ctrl(qml.PauliZ, control=[2])(wires=3)
    ry_3_8237047898941157(2)
    qml.ctrl(qml.PauliZ, control=[1])(wires=2)
    ry_5_382258257999492(1)
    qml.ctrl(qml.PauliZ, control=[0])(wires=1)
    ry_0_4608030009462126(0)
    ry_5_991413266982324(3)
    qml.ctrl(qml.PauliZ, control=[2])(wires=3)
    ry_3_1604705609650257(2)
    qml.ctrl(qml.PauliZ, control=[1])(wires=2)
    ry_3_8085796950542656(1)
    ry_6_4608361773846(3)
    qml.ctrl(qml.PauliZ, control=[2])(wires=3)
    ry_2_709332149091332(2)
    ry_1_6710555259169388(3)
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
