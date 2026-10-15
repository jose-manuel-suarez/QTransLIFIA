# Importación de paquetes requeridos
import math
from qiskit import QuantumCircuit, QuantumRegister, ClassicalRegister

# Generación de registros cuánticos y clásicos
qreg_q = QuantumRegister(4, 'q')
creg_c = ClassicalRegister(4, 'c')

# Compuertas personalizadas (funciones locales)
def ry_0_3639515108210906(circuit, w0):
    circuit.ry(0.3639515108210906, w0)

def ry_3_635990261432437(circuit, w0):
    circuit.ry(-3.635990261432437, w0)

def ry_1_002813228816168(circuit, w0):
    circuit.ry(-1.002813228816168, w0)

def ry_3_362268080070584(circuit, w0):
    circuit.ry(3.362268080070584, w0)

def ry_6_243016014063322(circuit, w0):
    circuit.ry(6.243016014063322, w0)

def ry_0_8811055252112134(circuit, w0):
    circuit.ry(0.8811055252112134, w0)

def ry_2_9808572300959044(circuit, w0):
    circuit.ry(2.9808572300959044, w0)

def ry_3_076180161567417(circuit, w0):
    circuit.ry(3.076180161567417, w0)

def ry_3_5997755951020247(circuit, w0):
    circuit.ry(3.5997755951020247, w0)

def ry_3_8705959422613034(circuit, w0):
    circuit.ry(-3.8705959422613034, w0)

def ry_1_9599706708457578(circuit, w0):
    circuit.ry(-1.9599706708457578, w0)

def ry_4_560604436086811(circuit, w0):
    circuit.ry(4.560604436086811, w0)

def ry_3_836947786309806(circuit, w0):
    circuit.ry(3.836947786309806, w0)

def ry_3_6364557194733527(circuit, w0):
    circuit.ry(-3.6364557194733527, w0)

def ry_5_8061284709341265(circuit, w0):
    circuit.ry(5.8061284709341265, w0)

def ry_3_8237047898941157(circuit, w0):
    circuit.ry(-3.8237047898941157, w0)

def ry_5_382258257999492(circuit, w0):
    circuit.ry(5.382258257999492, w0)

def ry_0_4608030009462126(circuit, w0):
    circuit.ry(0.4608030009462126, w0)

def ry_5_991413266982324(circuit, w0):
    circuit.ry(5.991413266982324, w0)

def ry_3_1604705609650257(circuit, w0):
    circuit.ry(-3.1604705609650257, w0)

def ry_3_8085796950542656(circuit, w0):
    circuit.ry(-3.8085796950542656, w0)

def ry_6_4608361773846(circuit, w0):
    circuit.ry(6.4608361773846, w0)

def ry_2_709332149091332(circuit, w0):
    circuit.ry(-2.709332149091332, w0)

def ry_1_6710555259169388(circuit, w0):
    circuit.ry(1.6710555259169388, w0)

# Creación del circuito cuántico
circuit = QuantumCircuit(qreg_q, creg_c)

ry_0_3639515108210906(circuit, qreg_q[0])
ry_3_635990261432437(circuit, qreg_q[1])
circuit.cz(qreg_q[0], qreg_q[1])
ry_1_002813228816168(circuit, qreg_q[0])
ry_3_362268080070584(circuit, qreg_q[2])
circuit.cz(qreg_q[1], qreg_q[2])
ry_6_243016014063322(circuit, qreg_q[1])
circuit.cz(qreg_q[0], qreg_q[1])
ry_0_8811055252112134(circuit, qreg_q[0])
ry_2_9808572300959044(circuit, qreg_q[3])
circuit.cz(qreg_q[2], qreg_q[3])
ry_3_076180161567417(circuit, qreg_q[2])
circuit.cz(qreg_q[1], qreg_q[2])
ry_3_5997755951020247(circuit, qreg_q[1])
circuit.cz(qreg_q[0], qreg_q[1])
ry_3_8705959422613034(circuit, qreg_q[0])
ry_1_9599706708457578(circuit, qreg_q[3])
circuit.cz(qreg_q[2], qreg_q[3])
ry_4_560604436086811(circuit, qreg_q[2])
circuit.cz(qreg_q[1], qreg_q[2])
ry_3_836947786309806(circuit, qreg_q[1])
circuit.cz(qreg_q[0], qreg_q[1])
ry_3_6364557194733527(circuit, qreg_q[0])
ry_5_8061284709341265(circuit, qreg_q[3])
circuit.cz(qreg_q[2], qreg_q[3])
ry_3_8237047898941157(circuit, qreg_q[2])
circuit.cz(qreg_q[1], qreg_q[2])
ry_5_382258257999492(circuit, qreg_q[1])
circuit.cz(qreg_q[0], qreg_q[1])
ry_0_4608030009462126(circuit, qreg_q[0])
ry_5_991413266982324(circuit, qreg_q[3])
circuit.cz(qreg_q[2], qreg_q[3])
ry_3_1604705609650257(circuit, qreg_q[2])
circuit.cz(qreg_q[1], qreg_q[2])
ry_3_8085796950542656(circuit, qreg_q[1])
ry_6_4608361773846(circuit, qreg_q[3])
circuit.cz(qreg_q[2], qreg_q[3])
ry_2_709332149091332(circuit, qreg_q[2])
ry_1_6710555259169388(circuit, qreg_q[3])
circuit.measure(qreg_q[0], creg_c[0])
circuit.measure(qreg_q[1], creg_c[1])
circuit.measure(qreg_q[2], creg_c[2])
circuit.measure(qreg_q[3], creg_c[3])
