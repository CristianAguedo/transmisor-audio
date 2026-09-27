# Transmisor de Audio LAN

Convierte la entrada de audio de una placa de sonido en un servidor MP3 dentro de la red local.
Desde el celu, la tablet o cualquier otra PC se escucha con el navegador (o con VLC) sin instalar nada.

## Qué hace

- Captura la entrada física elegida (micrófono, interfaz, mezcladora) con FFmpeg.
- La convierte a MP3 y la sirve por HTTP en streaming, sin grabar a disco.
- Cada dispositivo que se conecta recibe la señal por su propia cola: un oyente lento
  no corta el audio de los demás.
- Muestra en vivo la URL, el código QR, los oyentes conectados y los kbps reales.
- No guarda archivos ni pide contraseña: la emisión existe solo mientras el botón está en verde.

## Requisitos

- Windows 10 u 11.
- Python 3.10 o superior (solo para compilar; la aplicación final no lo necesita).
- `ffmpeg.exe` en la misma carpeta que el programa. Si no está, el botón **Examinar** permite buscarlo.

## Instalación

1. Copiá la carpeta `TransmisorAudio` completa al equipo donde está la placa de audio.
2. Abrí `TransmisorAudio.exe`. No requiere instalación ni permisos de administrador
   (salvo que quieras agregarlo al firewall, que sí pide permisos).
3. Elegí la entrada en la lista y tocá **Probar**. Si marca la barra de nivel, esa entrada sirve.
4. Tocá **Iniciar transmisión**.

## Cómo escucharlo

| Dispositivo | Cómo |
| --- | --- |
| Celu o tablet | Conectate a la misma red y abrí la URL en el navegador (el QR la copia directo). |
| PC con Windows | `http://IPDELPC:9000` en el navegador, o VLC → **Abrir red**. |
| VLC en cualquier equipo | URL directa: `http://IPDELPC:9000/stream.mp3` |
| Teléfono Android | `Chrome` o `VLC` con la URL `/stream.mp3`. En Android el navegador no siempre reproduce MP3 en directo: usá VLC. |
| Altavoz inteligente / radio | No compatible: necesitan HLS o IceCast, no MP3 chunked. |

La URL completa se ve en el panel derecho, junto al QR, e incluye la IP de la red del equipo
(por ejemplo `http://192.168.1.36:9000`).

## Ajustes disponibles

| Opción | Valores | Por defecto | Para qué sirve |
| --- | --- | --- | --- |
| Puerto | 1025–65535 | `9000` | Cambialo si otro programa ya lo usa. |
| Bitrate | 96k, 128k, 160k, 192k, 256k | `128k` | Más alto = mejor calidad y más consumo de datos. |
| Sample rate | 22050, 32000, 44100, 48000 | `44100` | 44100 sirve para casi todo. |
| Canales | Original, Mono, Estéreo | Original | Forzá mono para Voz de la radio o escenarios IA. |
| Buffer (MB) | 1 a 32 | `4` | Más buffer = más estable con Wi‑Fi flojo, más latencia. |
| Captura sin buffer | on/off | on | Menos latencia de entrada; si la captura se corta, desmarcá y subí el buffer. |

**Latencia:** el stream es en vivo, no diferido. Se acumulan entre 0,2 s y 1 s
según el dispositivo, la red y el navegador. La primera carga del player tarda un poco más
porque espera los primeros chunks.

## Firewall

La primera vez, Windows puede bloquear las conexiones entrantes. El programa avisa con un botón
que abre PowerShell con el comando listo (necesita permisos de administrador):

```powershell
New-NetFirewallRule -DisplayName "Audio LAN" -Direction Inbound -LocalPort 9000 -Protocol TCP -Action Allow -Profile Private
```

Si cambiás el puerto, reemplazá `9000`. Si la red Wi‑Fi del router está marcada como "Pública",
usá `-Profile Any` o cambiá el perfil de la red a Privada en la configuración de Windows.

## Estructura

```
TransmisorAudio/
├── TransmisorAudio.exe   programa
├── ffmpeg.exe            motor de captura y conversión
└── _internal/            recursos de Python y del player web
```

Para distribuirlo, copiá la carpeta completa. No sirve solo el `.exe`.

## Compilar desde el código

```powershell
git clone <repo> ; cd stream-audio
python -m pip install -r requirements.txt
.\build.ps1
```

- `.\build.ps1` → `dist\TransmisorAudio\` (carpeta, arranque instantáneo). Es el modo recomendado.
- `.\build.ps1 -OneFile` → `dist\TransmisorAudio.exe` (un archivo, ~3 s de arranque).
- `.\build.ps1 -SkipDeps` → no reinstala dependencias (rebuilds rápidos).

Si `ffmpeg.exe` no está en el `PATH`, el script usa el que está en la raíz del proyecto y lo
copia junto al programa.

## Archivos del proyecto

| Archivo | Rol |
| --- | --- |
| `app.py` | Interfaz, selección de entrada, métricas, QR, firewall. |
| `core/ffmpeg_bin.py` | Encuentra `ffmpeg.exe` y los recursos empaquetados. |
| `core/devices.py` | Lista y prueba entradas de DirectShow. |
| `core/encoder.py` | Proceso FFmpeg, lectura de MP3 y estadísticas. |
| `core/server.py` | Servidor HTTP, chunked, cola por cliente. |
| `core/applog.py` | Logs con rotación. |
| `assets/index.html` | Player web (HTML + CSS + JS en un archivo). |

## Diagnóstico

Los logs están en `%LOCALAPPDATA%\TransmisorAudio\`:

- `stream.log`: arranque, dispositivos, comando de FFmpeg, emisiones, errores.
- `ffmpeg.log`: salida de error de FFmpeg (dispositivo ocupado, formato inválido).

Problemas habituales:

- **La lista de entradas está vacía** → no hay `ffmpeg.exe` al lado del programa. Usá **Examinar**.
- **"El dispositivo ya está en uso"** → otra app (DAW, Zoom, Meet, el mezclador de la interfaz) tiene
  el micrófono abierto. Cerrala o elegí otra entrada.
- **Se corta el audio** → desmarcá *Captura sin buffer* y subí el buffer a 8 o 16 MB.
- **No entra nada desde el celu** → revisá que estén en la misma red, que el firewall permita el puerto
  y que la red no tenga "aislamiento de clientes" activado en el router.
- **El player queda mudo** → tocá ▶. Los navegadores exigen una interacción del usuario antes de
  dejar sonar audio; VLC no tiene esa restricción.
- **Sale `ffmpeg` como proceso colgado al cerrar** → cerrá la ventana con la X (no mata la consola a la fuerza).

## Notas de diseño

- **FFmpeg externo y no empaquetado**: el ejecutable pesa 3 MB y el motor se actualiza por separado.
- **MP3 chunked** en vez de HLS: es lo que aceptan VLC, foobar y la mayoría de los players de red,
  y también lo reproduce un `<audio>` normal de cualquier navegador moderno.
- **Sin token**: la URL es adivinable para cualquiera en la misma red. Si necesitás privacidad,
  cambiá el puerto a algo arbitrario y usá la red como zona segura.
- **Sin `sounddevice`**: los nombres de las entradas salen de FFmpeg, así que coinciden exactamente
  con lo que el mezclador de Windows muestra.
