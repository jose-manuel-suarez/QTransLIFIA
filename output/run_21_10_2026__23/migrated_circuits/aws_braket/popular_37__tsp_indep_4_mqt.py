# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Compuertas personalizadas (funciones locales)
def ry_0_3639515108210906(circuit, w0):
    circuit.ry(w0, 0.3639515108210906)

def ry_3_635990261432437(circuit, w0):
    circuit.ry(w0, -3.635990261432437)

def ry_1_002813228816168(circuit, w0):
    circuit.ry(w0, -1.002813228816168)

def ry_3_362268080070584(circuit, w0):
    circuit.ry(w0, 3.362268080070584)

def ry_6_243016014063322(circuit, w0):
    circuit.ry(w0, 6.243016014063322)

def ry_0_8811055252112134(circuit, w0):
    circuit.ry(w0, 0.8811055252112134)

def ry_2_9808572300959044(circuit, w0):
    circuit.ry(w0, 2.9808572300959044)

def ry_3_076180161567417(circuit, w0):
    circuit.ry(w0, 3.076180161567417)

def ry_3_5997755951020247(circuit, w0):
    circuit.ry(w0, 3.5997755951020247)

def ry_3_8705959422613034(circuit, w0):
    circuit.ry(w0, -3.8705959422613034)

def ry_1_9599706708457578(circuit, w0):
    circuit.ry(w0, -1.9599706708457578)

def ry_4_560604436086811(circuit, w0):
    circuit.ry(w0, 4.560604436086811)

def ry_3_836947786309806(circuit, w0):
    circuit.ry(w0, 3.836947786309806)

def ry_3_6364557194733527(circuit, w0):
    circuit.ry(w0, -3.6364557194733527)

def ry_5_8061284709341265(circuit, w0):
    circuit.ry(w0, 5.8061284709341265)

def ry_3_8237047898941157(circuit, w0):
    circuit.ry(w0, -3.8237047898941157)

def ry_5_382258257999492(circuit, w0):
    circuit.ry(w0, 5.382258257999492)

def ry_0_4608030009462126(circuit, w0):
    circuit.ry(w0, 0.4608030009462126)

def ry_5_991413266982324(circuit, w0):
    circuit.ry(w0, 5.991413266982324)

def ry_3_1604705609650257(circuit, w0):
    circuit.ry(w0, -3.1604705609650257)

def ry_3_8085796950542656(circuit, w0):
    circuit.ry(w0, -3.8085796950542656)

def ry_6_4608361773846(circuit, w0):
    circuit.ry(w0, 6.4608361773846)

def ry_2_709332149091332(circuit, w0):
    circuit.ry(w0, -2.709332149091332)

def ry_1_6710555259169388(circuit, w0):
    circuit.ry(w0, 1.6710555259169388)

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
ry_0_3639515108210906(circuit, 0)
ry_3_635990261432437(circuit, 1)
circuit.z(1, control=[0])
ry_1_002813228816168(circuit, 0)
ry_3_362268080070584(circuit, 2)
circuit.z(2, control=[1])
ry_6_243016014063322(circuit, 1)
circuit.z(1, control=[0])
ry_0_8811055252112134(circuit, 0)
ry_2_9808572300959044(circuit, 3)
circuit.z(3, control=[2])
ry_3_076180161567417(circuit, 2)
circuit.z(2, control=[1])
ry_3_5997755951020247(circuit, 1)
circuit.z(1, control=[0])
ry_3_8705959422613034(circuit, 0)
ry_1_9599706708457578(circuit, 3)
circuit.z(3, control=[2])
ry_4_560604436086811(circuit, 2)
circuit.z(2, control=[1])
ry_3_836947786309806(circuit, 1)
circuit.z(1, control=[0])
ry_3_6364557194733527(circuit, 0)
ry_5_8061284709341265(circuit, 3)
circuit.z(3, control=[2])
ry_3_8237047898941157(circuit, 2)
circuit.z(2, control=[1])
ry_5_382258257999492(circuit, 1)
circuit.z(1, control=[0])
ry_0_4608030009462126(circuit, 0)
ry_5_991413266982324(circuit, 3)
circuit.z(3, control=[2])
ry_3_1604705609650257(circuit, 2)
circuit.z(2, control=[1])
ry_3_8085796950542656(circuit, 1)
ry_6_4608361773846(circuit, 3)
circuit.z(3, control=[2])
ry_2_709332149091332(circuit, 2)
ry_1_6710555259169388(circuit, 3)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
circuit.measure([2])
circuit.measure([3])
