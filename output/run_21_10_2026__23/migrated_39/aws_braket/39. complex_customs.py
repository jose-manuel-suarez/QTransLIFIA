# Importación de paquetes requeridos
import math
from braket.circuits import Circuit

# Creación del circuito AWS Braket
circuit = Circuit()

# Puertas migradas desde OpenQASM
circuit.h(0)
circuit.h(1)
circuit.u(0, 0, 0, 1.022086548338751)
circuit.rz(0, -1.022086548338751)
circuit.u(0, 2.6572556550648576, -0.7494504172766678, 1.6303968037558327)
circuit.u(1, 1.7722832659115826, 1.7993318097017053, -0.15769545148268982)
circuit.x(1, control=[0])
circuit.u(0, 0.6610620143917973, -math.pi/2, math.pi/2)
circuit.u(1, 1.146322550785802, -0.6825452469363378, -0.4689493306248971)
circuit.x(1, control=[0])
circuit.u(0, 0.4249056861253225, 0, -math.pi/2)
circuit.u(1, 1.047197551196598, 2.526112944919406, -0.6154797086703869)
circuit.x(1, control=[0])
circuit.u(0, 1.661438225728421, -1.939568706812894, 0.7979501493332246)
circuit.u(1, 0.899625573385694, 0.41532997728071486, -1.6762487268948827)
circuit.cphaseshift([1], 0, math.pi/512)
circuit.cphaseshift([0], 1, math.pi/256)
circuit.u(0, 0, 0, 0.34906596460815587)
circuit.rz(0, -0.34906596460815587)
circuit.rz(0, math.pi/2)
circuit.ry(0, 0.5235988043049772)
circuit.rz(0, -math.pi/2)
circuit.rz(1, 1.020135819677448)
circuit.ry(1, 0.6355626524430418)
circuit.rz(1, -0.5506605071174487)

# Mediciones en orden clásico, diferidas al final
circuit.measure([0])
circuit.measure([1])
