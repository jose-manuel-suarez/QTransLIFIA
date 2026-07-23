# Quirk Translator - IBM y AWS

Servidor Flask para traducir circuitos cuánticos del formato [Quirk](https://algassert.com/quirk) a código Python ejecutable para **Qiskit (IBM)** o **Amazon Braket**.

## 📋 Descripción

API REST que recibe URLs de circuitos cuánticos en formato Quirk y las traduce a código Python compatible con:
- **Qiskit** (framework de IBM)
- **Amazon Braket** (servicio de AWS)

## 🏗️ Estructura del Proyecto

```
traductor_unex/
├── translator.py                                    # Servidor Flask principal
├── requirements.txt                                 # Dependencias mínimas (6 paquetes)
├── requirements_original.txt                        # Backup con ~130 dependencias originales
├── .env                                               # Variables de entorno (puerto, etc.)
├── postman/
│   ├── Quirk_Translator_IBM_AWS.postman_collection.json              # Colección lista para importar
│   └── Quirk_Translator_IBM_AWS.postman_collection_original.json     # Versión original (caracteres crudos)
├── test/                                            # Scripts de validación y reparación
│   ├── analyze.py                                   # Validar JSON con Python
│   ├── analyze.ps1                                  # Validar JSON con PowerShell
│   └── fix_postman.py                               # Verificar/reparar codificación UTF-8
└── .venv/                                           # Entorno virtual (no incluido en git)
```

## 🚀 Instalación y Ejecución

### 1. Crear el entorno virtual (venv)

```bash
python -m venv .venv
```

### 2. Activar el entorno virtual

**Windows (PowerShell):**
```powershell
.venv\Scripts\Activate.ps1
```

**Windows (CMD):**
```cmd
.venv\Scripts\activate.bat
```

**Linux/Mac:**
```bash
source .venv/bin/activate
```

> **Nota:** Después de activar, verás `(.venv)` al inicio de tu línea de comandos.

### 3. Instalar dependencias

```bash
# Con pip (solo las 6 dependencias mínimas necesarias)
pip install -r requirements.txt

# Restaurar todas las dependencias originales (~130 paquetes) si se perdió algo
pip install -r requirements_original.txt
```

### 4. Ejecutar el servidor Flask

```bash
python translator.py
```

El servidor iniciará en `http://localhost:8081`.

### 5. Verificar que está corriendo

Abre tu navegador y visita http://localhost:8081/ (debería mostrar un mensaje de bienvenida o error 405).

## 📡 Endpoints Disponibles

| Endpoint | Método | Descripción |
|----------|--------|-------------|
| `/code/ibm` | POST | Traduce múltiples circuitos Quirk → Qiskit |
| `/code/ibm/individual` | POST | Traduce un circuito individual → Qiskit (con offset de qubits) |
| `/code/aws` | POST | Traduce múltiples circuitos Quirk → Braket |
| `/code/aws/individual` | POST | Traduce un circuito individual → Braket (con offset de qubits) |

### Formato de Request

**Individual:**
```json
{
  "url": "https://algassert.com/quirk#circuit={...}",
  "d": 0
}
```

**Por lotes (múltiples circuitos):**
```json
{
  "1": "https://algassert.com/quirk#circuit={...}",
  "2": "https://algassert.com/quirk#circuit={...}"
}
```