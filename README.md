# Transmisor de Audio LAN 📡

[![Windows](https://img.shields.io/badge/Plataforma-Windows%2010%20%2F%2011-0078d4?logo=windows&logoColor=white)](https://microsoft.com/windows)
[![Python](https://img.shields.io/badge/Python-3.10%2B-3776ab?logo=python&logoColor=white)](https://python.org)
[![WASAPI](https://img.shields.io/badge/Audio-WASAPI%20Loopback-10b981)](https://learn.microsoft.com/en-us/windows/win32/coreaudio/wasapi)
[![Web Audio API](https://img.shields.io/badge/Web%20Audio-Baja%20Latencia-f59e0b)](https://developer.mozilla.org/en-US/docs/Web/API/Web_Audio_API)
[![FFmpeg](https://img.shields.io/badge/Encoder-FFmpeg-007808?logo=ffmpeg&logoColor=white)](https://ffmpeg.org)

Aplicación moderna para Windows que transmite el audio de tu PC a cualquier dispositivo en la red local (celulares, Smart TVs, tablets, notebooks o reproductores multimedia) a través de un navegador web o enlace directo, **sin necesidad de instalar aplicaciones en los clientes**.

Permite capturar tanto entradas físicas (micrófonos, consolas, interfaces) como el sonido del sistema en vivo (**WASAPI Loopback**, para escuchar Spotify, juegos, videos, DAWs o cualquier programa).

---

## Descargar aplicación para Windows 10/11

TransmisorAudio v1.0 ([MediaFire](https://www.mediafire.com/file/7og8wq1f79trxbj/TransmisorAudio.zip/file))

---

## 🚀 Características Principales

* **Arquitectura Híbrida de Doble Modo:**
  * **`📶 Estabilidad` (Modo por defecto):** Flujo continuo HTTP MP3 (`/stream.mp3`) con sincronización exacta de cabeceras y búfer de pre-roll. Diseñado para máxima compatibilidad con **Smart TVs antiguas (2012–presente)**, VLC, radios Wi-Fi y navegadores estándar sin cortes ni interrupciones.
  * **`⚡ Baja Latencia` (Celulares y tablets):** Transmisión directa de audio sin comprimir PCM de 16 bits (`/stream.pcm`) procesada en tiempo real mediante **Web Audio API**. Ofrece una latencia ultra-baja en milisegundos (**~75 ms**) ideal para sincronización con video y juegos.
* **Captura Nativa WASAPI Loopback:** Graba el sonido interno de Windows directamente desde el bus de audio sin requerir cables virtuales (Virtual Audio Cable / Stereo Mix).
* **Espectro de Audio Real:** Visualizador de frecuencias en vivo en el navegador mediante Transformada Rápida de Fourier (FFT), reaccionando a graves, medios y agudos reales (con detección de silencio plano).
* **Multidispositivo sin interferencias:** Cada cliente conectado cuenta con su propia cola de memoria desacoplada del motor de codificación; si un dispositivo tiene una señal débil de Wi-Fi, no afecta ni entrecorta la reproducción de los demás.
* **Control Inteligente de Jitter Wi-Fi:** Búfer dinámico que absorbe fluctuaciones de red y descarta excesos acumulados tras bloqueos de pantalla, garantizando que el audio se mantenga siempre pegado al tiempo real.
* **Facilidad de Conexión:** Generación automática de código QR y URL directa en la interfaz para escanear y escuchar al instante.
* **Persistencia de Ajustes:** Guarda automáticamente la configuración de dispositivo, puerto, bitrate y modo en `config.json`.

---

## 📋 Requisitos del Sistema

### Para Ejecutar la Aplicación:
* **Sistema Operativo:** Windows 10 o Windows 11 (64-bit).
* **Conexión de Red:** Wi-Fi o cable Ethernet en la misma red local que los dispositivos receptores.
* **Binario de FFmpeg:** `ffmpeg.exe` (incluido junto al programa o seleccionable con el botón *Examinar*).

### Para Desarrollar o Compilar:
* **Python:** 3.10 o superior (recomendado 3.11 / 3.12 / 3.13).
* **PowerShell:** 5.1 o superior.

---

## 🛠️ Instalación y Uso Rápido en Windows

1. Descarga o descomprime la carpeta de la aplicación (`dist\TransmisorAudio\`).
2. Asegúrate de que `ffmpeg.exe` esté presente en la misma carpeta que `TransmisorAudio.exe`.
3. Ejecuta `TransmisorAudio.exe` (no requiere privilegios de administrador para el uso habitual).
4. En el menú desplegable **Entrada de audio**, selecciona la fuente deseada:
   * Para transmitir lo que suena en la PC: elige la opción que termina en **`[Loopback]`** (por ejemplo, `Altavoces (High Definition Audio Device) [Loopback]`).
   * Para transmitir un micrófono o instrumento: elige el micrófono o interfaz correspondiente.
5. Haz clic en **Iniciar transmisión**.
6. Escanea el código QR desde tu celular o ingresa la URL mostrada en el navegador de cualquier dispositivo de la red local.

---

## 📱 Cómo Escuchar desde Distintos Dispositivos

| Dispositivo / Receptor | Modo Recomendado | Cómo conectarse |
| :--- | :---: | :--- |
| **Celulares (Android / iOS)** | `⚡ Baja Latencia` | Escanear el código QR con la cámara o abrir la URL en Chrome/Safari. Toca **Escuchar** y selecciona **Baja Latencia** para respuesta instantánea (~75 ms). |
| **Smart TVs (LG webOS, Samsung Tizen, Android TV, etc.)** | `📶 Estabilidad` | Abrir el navegador de la TV e ingresar la URL del emisor (ej. `http://192.168.1.35:9000`). Se reproduce automáticamente en modo estabilidad por el elemento nativo de audio. |
| **VLC Media Player (PC / Mac / Linux / TV Box)** | Enlace directo | Ir a **Medio** → **Abrir ubicación de red** e ingresar: `http://IP_DE_TU_PC:9000/stream.mp3` |
| **Navegador en otra PC / Notebook** | Ambos modos | Abrir `http://IP_DE_TU_PC:9000` en Chrome, Edge, Firefox, etc. |

> [!TIP]
> **Políticas de Autoplay en Navegadores:** Por seguridad, los navegadores móviles requieren que el usuario toque la pantalla una vez para habilitar el sonido. Basta con presionar el botón **Escuchar** en la página web.

---

## 🛡️ Configuración del Firewall de Windows

Al abrir un servidor HTTP en la red local, el Firewall de Windows puede solicitar autorización para aceptar conexiones entrantes. Si los dispositivos no logran cargar la página web, ejecuta la siguiente regla en **PowerShell como Administrador**:

```powershell
New-NetFirewallRule -DisplayName "Transmisor Audio LAN" -Direction Inbound -LocalPort 9000 -Protocol TCP -Action Allow -Profile Private
```

*(Si configuraste un puerto diferente a `9000`, cambia el valor en `-LocalPort`).*

> [!NOTE]
> Asegúrate de que la red Wi-Fi de tu PC esté configurada como **Red Privada** en Windows (en Redes Públicas el sistema bloquea por defecto la comunicación entre dispositivos).

---

## ⚙️ Opciones de Configuración

| Parámetro | Rango / Opciones | Valor por Defecto | Descripción |
| :--- | :---: | :---: | :--- |
| **Puerto** | `1025` – `65535` | `9000` | Puerto TCP en el que escucha el servidor web. |
| **Bitrate MP3** | `96k` a `320k` | `128k` | Calidad de compresión para el modo Estabilidad / Smart TVs. |
| **Frecuencia (Hz)** | `22050` a `48000` | `44100` / `48000` | Frecuencia de codificación de salida. |
| **Canales** | `Original`, `Mono`, `Estéreo` | `Original` | Permite forzar audio monofónico para voz o conservar el estéreo. |
| **Búfer de captura**| `1` a `32 MB` | `4 MB` | Búfer en memoria RAM para amortiguar picos de uso del procesador. |
| **Sin búfer (Low Latency)**| Activado / Desactivado | Activado | Desactiva retardos internos de multiplexación en FFmpeg. |
| **Autoiniciar** | Activado / Desactivado | Desactivado | Comienza a emitir automáticamente apenas se abre la aplicación. |

La configuración se almacena en `%LOCALAPPDATA%\TransmisorAudio\config.json`.

---

## 🏗️ Compilación desde el Código Fuente

El proyecto utiliza **PyInstaller** y un script automatizado en PowerShell (`build.ps1`) para generar el ejecutable.

### 1. Clonar el Repositorio e Instalar Dependencias

```powershell
# Clonar el proyecto
git clone https://github.com/tu-usuario/stream-audio.git
cd stream-audio

# Crear y activar entorno virtual (recomendado)
python -m venv venv
.\venv\Scripts\Activate.ps1

# Instalar librerías necesarias
pip install -r requirements.txt
```

### 2. Opciones de Compilación con `build.ps1`

El script `build.ps1` gestiona la recolección de archivos, temas visuales de CustomTkinter, controladores de PortAudio y binarios:

```powershell
# Compilación estándar (Recomendada: genera carpeta dist\TransmisorAudio\ con arranque instantáneo)
.\build.ps1

# Compilación rápida sin reinstalar dependencias de pip
.\build.ps1 -SkipDeps

# Generar un único archivo ejecutable portátil (dist\TransmisorAudio.exe)
.\build.ps1 -OneFile
```

Al finalizar la compilación, el ejecutable y sus recursos quedarán en:
* `dist\TransmisorAudio\TransmisorAudio.exe`

Para distribuir el programa a otra computadora, copia la carpeta completa `dist\TransmisorAudio\`.

---

## 🔬 Arquitectura y Detalles Técnicos

```
                      ┌───────────────────────────────────────┐
                      │      WASAPI Loopback / Micrófono      │
                      │       (Hardware de Audio Windows)     │
                      └──────────────────┬────────────────────┘
                                         │
                   Audio Callback (PCM 16-bit estéreo a 48 kHz)
                                         │
                 ┌───────────────────────┴───────────────────────┐
                 │                                               │
                 ▼                                               ▼
     ┌────────────────────────┐                     ┌────────────────────────┐
     │   Hilo Independiente   │                     │     Cola de FFmpeg     │
     │      (_pcm_worker)     │                     │     (_feed_worker)     │
     └───────────┬────────────┘                     └────────────┬───────────┘
                 │                                               │
                 ▼                                               ▼
        Flujo /stream.pcm                               Codificación MP3 en pipe
       (Sin compresión)                                (CBR 128k / Stereo)
                 │                                               │
                 ▼                                               ▼
      ┌──────────────────────┐                        ┌──────────────────────┐
      │   Web Audio API      │                        │  Flujo /stream.mp3   │
      │  (Celular: ~75 ms)   │                        │ (Smart TV / Estable) │
      └──────────────────────┘                        └──────────────────────┘
```

1. **Captura Directa con PyAudioWPatch:** Se conecta al endpoint WASAPI nativo de Windows. En modo loopback, el controlador extrae las muestras exactamente como salen de la tarjeta de sonido, sin pérdidas.
2. **Desacoplamiento de Flujos:** El procesamiento PCM para celulares corre en un hilo independiente (`_pcm_worker`), aislando el flujo de ultra-baja latencia de los tiempos de codificación de `ffmpeg`.
3. **Optimización de Red TCP:**
   * Se desactiva el algoritmo de Nagle (`TCP_NODELAY = 1`) para evitar que Windows agrupe paquetes y retrase el envío.
   * Se limita el búfer de socket (`SO_SNDBUF`) para impedir que el sistema operativo almacene colas ocultas de audio retrasado.
4. **Programación Precisa en el Navegador:** El cliente web programa los bloques de audio con `audioCtx.createBufferSource()` calculando con precisión de punto flotante la posición temporal en `audioCtx.currentTime`, aplicando un colchón anti-jitter de 75 ms y descartando excesos superiores a 180 ms.

---

## 📂 Estructura del Código

```
stream-audio/
├── app.py                  # Interfaz gráfica moderna (CustomTkinter), selector de entradas y métricas
├── build.ps1               # Script automatizado de compilación y empaquetado para Windows
├── requirements.txt        # Dependencias de Python (pyaudiowpatch, customtkinter, pillow, qrcode)
├── assets/
│   └── index.html          # Reproductor web responsivo con analizador FFT y conmutador de modos
├── core/
│   ├── applog.py           # Sistema de registros y rotación de logs
│   ├── config.py           # Gestión de configuración persistente (JSON)
│   ├── devices.py          # Detección y filtrado de dispositivos WASAPI físicos y Loopback
│   ├── encoder.py          # Captura en tiempo real, gestión de hilos y tubería a FFmpeg
│   ├── ffmpeg_bin.py       # Detección y localización dinámica de binarios y recursos
│   └── server.py           # Servidor HTTP multihilo, streaming PCM y MP3 con sincronización de frames
└── dist/
    └── TransmisorAudio/    # Carpeta final empaquetada lista para usar
```

---

## ❓ Preguntas Frecuentes y Diagnóstico

* **¿Por qué el audio en modo Baja Latencia se detiene al apagar la pantalla del celular?**  
  Algunos sistemas móviles (en particular navegadores en Android e iOS) suspenden la ejecución de JavaScript en segundo plano para ahorrar batería cuando la pantalla se bloquea. Si necesitas escuchar con la pantalla apagada por largos periodos, usa el modo **`📶 Estabilidad`** (que utiliza el reproductor multimedia nativo del sistema operativo).
* **¿Por qué no se escucha sonido en la Smart TV?**  
  Asegúrate de que la TV esté en el modo por defecto **`📶 Estabilidad`**. La mayoría de los navegadores de Smart TVs no soportan Web Audio API compleja, pero admiten de forma nativa flujos continuos MP3.
* **No aparecen dispositivos en el menú:**  
  Verifica que `ffmpeg.exe` esté junto al ejecutable o usa el botón **Examinar** para indicar su ubicación.
* **Ubicación de registros (Logs):**  
  Los logs de depuración se guardan en `%LOCALAPPDATA%\TransmisorAudio\`:
  * `stream.log`: información de arranque, clientes conectados y estado de la red.
  * `ffmpeg.log`: salida y diagnósticos del codificador FFmpeg.

---

## 📄 Licencia

Este proyecto se distribuye bajo la licencia MIT. Eres libre de usarlo, modificarlo y redistribuirlo.
