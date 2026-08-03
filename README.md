# Minecraft Server Manager

Aplicación de escritorio con interfaz web local para crear, administrar y alojar
servidores de Minecraft Java Edition sin usar la consola ni editar ficheros a mano.

- El usuario **nunca** descarga jars ni Java: la aplicación lo hace por él.
- La aplicación **no limita** los recursos del equipo: sólo recomienda.
- Cada servidor es un proceso independiente supervisado por el backend.

**Proyecto completo**: las 11 fases están implementadas y verificadas contra un
servidor de Minecraft real. 94 pruebas automáticas en el backend.

---

# Instalación

## Requisitos previos

Sólo hay que instalar tres cosas, y **Java no es una de ellas**: la aplicación
descarga sola el runtime que necesite cada versión de Minecraft.

| Programa | Versión mínima | Dónde |
|---|---|---|
| Python | 3.12 o superior | <https://www.python.org/downloads/> — marca **«Add python.exe to PATH»** al instalar |
| Node.js | 20 o superior | <https://nodejs.org/> (versión LTS) |
| Git | cualquiera | <https://git-scm.com/downloads> |

Comprueba que están bien instalados abriendo una terminal (PowerShell) y
escribiendo:

```bash
python --version
```

```bash
node --version
```

Si alguno responde «no se reconoce», reinstálalo marcando la opción de añadirlo
al PATH y **cierra y vuelve a abrir la terminal**.

## Paso 1 — Descargar el proyecto

```bash
git clone https://github.com/AlejandroBast/Minecraft-Server-Manager.git
```

```bash
cd Minecraft-Server-Manager
```

## Paso 2 — Preparar el backend

Crea el entorno de Python e instala sus dependencias:

```bash
python -m venv backend/.venv
```

```bash
backend/.venv/Scripts/python.exe -m pip install -r backend/requirements.txt
```

Tarda un par de minutos la primera vez. Si además quieres ejecutar las pruebas,
usa `requirements-dev.txt` en lugar de `requirements.txt`.

## Paso 3 — Preparar el frontend

```bash
cd frontend
```

```bash
npm install
```

```bash
cd ..
```

## Paso 4 — Arrancar la aplicación

Hacen falta **dos terminales abiertas a la vez**. En la primera, el backend:

```bash
backend/.venv/Scripts/python.exe backend/run.py
```

Déjala abierta. En una segunda terminal, la interfaz:

```bash
npm --prefix frontend run dev
```

Abre <http://localhost:3000> en el navegador. Deberías ver el panel con los
datos de tu equipo (CPU, RAM, disco, IP).

> Cerrar esas terminales apaga la aplicación **y todos los servidores de
> Minecraft que estén corriendo**, de forma limpia y guardando el mundo.

## Paso 5 — Crear tu primer servidor

1. Pulsa **Crear servidor**
2. Ponle nombre y elige el tipo (**Paper** es la opción recomendada: rápido y
   admite plugins)
3. La lista de versiones se rellena sola; elige la que quieras
4. Pulsa **Usar la recomendada** para que la memoria se ajuste a tu equipo
5. **Crear servidor**

La tarjeta aparecerá como «Instalando» con una barra de progreso: está
descargando Java y el servidor. Cuando ponga **Detenido**, pulsa **Iniciar**.
La primera vez tarda un poco porque genera el mundo. Cuando ponga **En línea**,
ya se puede jugar.

## Paso 6 — Que entren tus amigos

**Desde tu propia casa (mismo wifi)**: les pasas tu IP local, la que aparece en
la tarjeta **Red** del panel, con el puerto. Por ejemplo `192.168.1.50:25565`.

**Desde fuera de tu casa**: abre **Red** en el panel. Si te avisa de que estás
tras **CGNAT** (muy habitual con operadores de fibra), abrir puertos no servirá
de nada y necesitas el túnel:

1. En la sección **Acceso desde internet**, pulsa **Abrir playit.gg** y crea una
   cuenta gratuita
2. Verifica tu correo (playit no deja crear túneles sin verificar)
3. Copia tu **clave de agente** y pégala en la app → **Guardar**
4. Pulsa **Iniciar túnel**
5. En playit.gg crea un túnel de tipo **Minecraft Java** apuntando a
   `127.0.0.1` y **al mismo puerto que tu servidor**
6. La dirección pública aparecerá en la app con botón de copiar. Eso es lo que
   les pasas a tus amigos: la escriben tal cual en Minecraft, sin instalar nada

## Uso diario

Cada vez que quieras jugar, repite sólo el **Paso 4** (las dos terminales) y
arranca el servidor desde el panel. La instalación de los pasos 1 a 3 se hace
una única vez.

## Si algo no funciona

| Síntoma | Causa y solución |
|---|---|
| «No se puede conectar con el backend» en el panel | La primera terminal se cerró. Vuelve a ejecutar el comando del Paso 4. Si el puerto 3000 estaba ocupado, la interfaz arranca en otro y **también funciona**: mira en la terminal qué dirección indica |
| El servidor se queda en **Error** | Abre su tarjeta: el motivo aparece escrito. Si la descarga se cortó, el botón pasa a ser **Reintentar instalación** — púlsalo y no pierdes ni el servidor ni el mundo |
| «Este servidor no llegó a instalarse» al iniciar | La descarga de Java o del jar no terminó. Usa **Reintentar instalación** en esa misma tarjeta |
| «El puerto ya lo usa el servidor X» | Dos servidores no pueden compartir puerto. Usa 25566, 25567… |
| Tus amigos no entran desde fuera | Comprueba en **Red** si hay CGNAT. Si lo hay, necesitas el túnel del Paso 6 |
| Windows pregunta por el cortafuegos | Es normal la primera vez que arranca Java. Permite el acceso en redes privadas |
| El antivirus bloquea la descarga de Java | Los runtimes vienen de Adoptium (Eclipse Temurin) y se verifican por sha256. Añade una excepción a la carpeta `downloads/` |

---

## Estado

| Fase | Contenido | Estado |
|------|-----------|--------|
| 1 | Arquitectura del proyecto | ✅ completada |
| 2 | Backend FastAPI (CRUD de servidores, sistema) | ✅ completada |
| 3 | Frontend Next.js | ✅ completada |
| 4 | Creación de servidores | ✅ completada |
| 5 | Descarga automática (Java, jars, librerías) | ✅ completada |
| 6 | Consola en tiempo real (WebSockets) | ✅ completada |
| 7 | Backups | ✅ completada |
| 8 | Plugins y mods | ✅ completada |
| 9 | Red (IP, puertos, UPnP, dominio) | ✅ completada |
| 10 | Optimización y pruebas | ✅ completada |
| 11 | Acceso desde internet (túnel playit.gg) | ✅ completada |

Todos los tipos se instalan solos salvo **Spigot**, que no publica descargas
(exige compilar con BuildTools) y se rechaza al crear explicando por qué; Paper
es compatible con sus plugins. Forge y NeoForge descargan su instalador y lo
ejecutan con el Java gestionado (fase 8).

## Arquitectura

```
Frontend (Next.js)
      ↓ REST / WebSocket
API FastAPI            app/api        adaptadores HTTP, sin lógica
      ↓
Server Manager         app/services   lógica de negocio, sin FastAPI
      ↓
Java Process Manager   subprocess     un proceso por servidor
      ↓
Servidor Minecraft     servers/<nombre>/
```

Reglas que sostienen el diseño:

1. **Los servicios no conocen HTTP.** Reciben datos y una sesión; lanzan
   excepciones de dominio (`app/core/exceptions.py`) que la API traduce.
2. **Todo acceso a ficheros pasa por `app/core/paths.py`** (`resolve_within`).
   No se concatenan rutas recibidas del frontend en ningún otro sitio.
3. **Ninguna ruta se construye a mano**: todas salen de `app/core/config.py`,
   configurable por entorno y desde la UI de ajustes.
4. **Un único punto de composición de rutas HTTP**: `app/api/router.py`.

## Estructura

```
minecraft-server-manager/
├── backend/            API FastAPI y lógica de negocio
│   ├── app/
│   │   ├── api/        routers HTTP (v1)
│   │   ├── core/       config, logging, excepciones, sandbox de rutas
│   │   ├── db/         motor, sesiones, arranque del esquema
│   │   ├── models/     modelos ORM y enumeraciones
│   │   ├── repositories/  acceso a datos
│   │   ├── schemas/    esquemas Pydantic
│   │   └── services/   servidores, descargas, backups, red, túnel
│   └── tests/
├── frontend/           Next.js 16 + Tailwind 4 + shadcn/ui
│   └── src/
│       ├── app/        layout y dashboard
│       ├── components/ tarjetas, formulario de creación, panel de sistema
│       ├── hooks/      consulta periódica de la API
│       └── lib/        cliente tipado, tipos del contrato y formateo
├── servers/            un directorio por servidor creado
├── downloads/          jars, runtimes de Java y agente del túnel
├── backups/            copias comprimidas en ZIP
├── database/           manager.db (SQLite)
├── logs/               app / servers / downloads / console
├── config/             preferencias exportadas
└── temp/               ficheros intermedios
```

## Desarrollo

Pruebas del backend (necesita `requirements-dev.txt`):

```bash
backend/.venv/Scripts/python.exe -m pytest
```

Comprobaciones del frontend:

```bash
cd frontend && npx tsc --noEmit && npx eslint .
```

Documentación interactiva de la API con el backend arrancado:
<http://127.0.0.1:8000/docs>

El navegador llama directamente a la API (`http://127.0.0.1:8000/api/v1`). Todo
corre en el mismo equipo, así que un proxy en Next sólo añadiría latencia. Para
apuntar a otra dirección, define `NEXT_PUBLIC_API_URL`.

## API disponible

| Método | Ruta | Descripción |
|--------|------|-------------|
| GET | `/api/v1/health` | Estado de la API y de la base de datos |
| GET | `/api/v1/servers` | Lista de servidores registrados |
| POST | `/api/v1/servers` | Crea un servidor (devuelve avisos no bloqueantes) |
| GET | `/api/v1/servers/{id}` | Detalle de un servidor |
| PATCH | `/api/v1/servers/{id}` | Modifica ajustes; bloquea los que exigen reinicio si está activo |
| DELETE | `/api/v1/servers/{id}` | Elimina un servidor detenido |
| GET | `/api/v1/system/info` | CPU, RAM, disco, Java, IP local |
| GET | `/api/v1/system/recommendations` | Jugadores y memoria estimados por tipo de servidor |
| GET | `/api/v1/servers/{id}/stats` | CPU, RAM, jugadores, TPS, tamaño del mundo |
| GET | `/api/v1/servers/{id}/install` | Progreso de la instalación en curso |
| POST | `/api/v1/servers/{id}/install/retry` | Reintenta una instalación fallida sin borrar el servidor |
| POST | `/api/v1/system/cleanup` | Borra copias huérfanas y temporales sueltos |
| POST | `/api/v1/servers/{id}/start` | Arranca el proceso Java del servidor |
| POST | `/api/v1/servers/{id}/stop` | Detención limpia (`stop` por stdin; kill sólo si no responde) |
| POST | `/api/v1/servers/{id}/restart` | Reinicio (parar y volver a arrancar) |
| GET | `/api/v1/servers/{id}/console` | Salida acumulada con índice incremental |
| POST | `/api/v1/servers/{id}/console` | Envía un comando (validado) al proceso |
| WS | `/api/v1/servers/{id}/console/ws` | Salida en tiempo real (sólo emite) |
| GET | `/api/v1/servers/{id}/addons/{plugins\|mods}` | Lista los plugins o mods instalados |
| POST | `/api/v1/servers/{id}/addons/{plugins\|mods}` | **Adjunta un .jar** desde la interfaz (multipart) |
| PATCH | `/api/v1/servers/{id}/addons/{tipo}/{archivo}` | Activa o desactiva sin borrar |
| DELETE | `/api/v1/servers/{id}/addons/{tipo}/{archivo}` | Elimina el archivo |
| GET | `/api/v1/servers/{id}/backups` | Copias de seguridad del servidor |
| POST | `/api/v1/servers/{id}/backups` | Crea una copia ZIP (en segundo plano) |
| POST | `/api/v1/backups/{id}/restore` | Restaura una copia (servidor detenido) |
| DELETE | `/api/v1/backups/{id}` | Elimina la copia y su fichero |
| GET | `/api/v1/downloads/versions/{tipo}` | Catálogo de versiones del tipo (o el motivo si no se descarga solo) |
| GET | `/api/v1/downloads/java` | Runtimes de Java gestionados por la aplicación |
| GET | `/api/v1/tunnel` | Estado del túnel y direcciones públicas asignadas |
| PUT | `/api/v1/tunnel/secret` | Guarda la clave del agente (validada contra playit.gg) |
| DELETE | `/api/v1/tunnel/secret` | Elimina la clave y detiene el túnel |
| POST | `/api/v1/tunnel/{start\|stop}` | Arranca o detiene el agente |
| GET | `/api/v1/tailscale` | Estado de la red privada y si cada amigo va directo o por relé |
| POST | `/api/v1/tailscale/install` | Descarga e instala Tailscale (firma verificada) |
| POST | `/api/v1/tailscale/login` | Devuelve el enlace de acceso para abrir en el navegador |
| POST | `/api/v1/tailscale/disconnect` | Desconecta la red privada |
| GET | `/api/v1/network` | Diagnóstico: IP local y pública, CGNAT, UPnP y puertos |
| POST | `/api/v1/network/ports/{puerto}/open` | Abre el puerto por UPnP (o explica cómo hacerlo a mano) |
| POST | `/api/v1/network/ports/{puerto}/close` | Cierra el mapeo UPnP |
| POST | `/api/v1/network/dns` | Registros DNS que crear para un dominio propio |
| GET | `/api/v1/settings` | Preferencias de la aplicación |
| PUT | `/api/v1/settings` | Modifica preferencias (sólo claves conocidas) |

Reglas de negocio que aplica el backend:

- Crear un servidor genera su carpeta completa en `servers/`: `eula.txt`
  aceptada, `server.properties`, `ops.json`, `whitelist.json` y los
  subdirectorios (`plugins/` o `mods/` según el tipo). Si algo falla a mitad,
  la instalación se revierte y no queda nada a medias.
- La base de datos es la fuente de verdad: cambiar ajustes por la API regenera
  `server.properties`; nunca se edita el fichero a mano.
- Eliminar un servidor borra también su carpeta (siempre dentro del sandbox).
- El nombre y el puerto no pueden repetirse entre servidores → `409`.
- Si otro **programa ajeno** ocupa el puerto, se crea igualmente y se devuelve
  un aviso: recomendar, no bloquear.
- `hardcore: true` fuerza dificultad `hard`, como hace el propio juego.
- Un servidor activo no se puede eliminar ni cambiarle puerto o memoria → `409`.
- Las recomendaciones **nunca** impiden crear un servidor.
- La creación es asíncrona: el servidor nace en `installing`, se descargan el
  Java necesario (Temurin, con sha256) y el `server.jar` (hash de cada
  fuente), y termina en `stopped` o en `error` con el motivo.
- El Java requerido lo dicta el manifest de Mojang por versión (p. ej. `26.2`
  exige Java 25; `1.21.4`, Java 21; `1.16.5`, Java 8): nada de tablas fijas.
- Cada servidor en marcha es un proceso Java independiente. El estado pasa a
  `online` al detectar el «Done (…s)!» del log real, y la detención siempre
  intenta `stop` por stdin (30 s) antes de matar: matar sin guardar puede
  corromper el mundo. Al apagar la aplicación se detienen todos los procesos.
- Los comandos de consola se validan (longitud, una sola línea, sin caracteres
  de control) y el WebSocket nunca los acepta: sólo emite salida.
- Los jugadores conectados se leen con el **Server List Ping**, el mismo
  protocolo que usa el cliente de Minecraft: es la fuente autoritativa y vale
  igual para Vanilla, Paper, Fabric o Forge (analizar el log sería frágil).
  El TPS se pregunta con el comando `tps` sólo en la familia Paper, cacheado
  30 s para no llenar la consola de comandos automáticos.
- Al arrancar, la aplicación **corrige los estados imposibles** heredados de un
  cierre inesperado (servidores «en línea» sin proceso, copias «en curso») y
  borra los restos de descargas cortadas.
- Una instalación que no terminó **se puede reintentar** sin borrar el servidor
  ni su mundo. La interfaz no ofrece «Iniciar» a un servidor sin instalar:
  ofrecerlo sólo llevaba a un error sin salida.
- Si hay CGNAT, la solución es el **túnel de playit.gg**, integrado en la app:
  descarga el agente oficial (versión fijada y verificada por sha256), lo
  ejecuta y muestra la dirección pública lista para copiar. Los jugadores no
  instalan nada. La clave del agente la genera el usuario en su propia cuenta
  de playit.gg; la aplicación nunca pide ni ve su contraseña, y esa clave
  **nunca sale por la API** aunque comparta tabla con las preferencias.
- Como alternativa de baja latencia existe **Tailscale**, también integrado: la
  aplicación descarga el instalador oficial, **verifica su firma digital** (en
  vez de fijar un hash, porque se actualiza a menudo) y lo instala en silencio;
  el acceso se hace con un botón que abre la web de Tailscale. La interfaz
  indica, amigo por amigo, si la conexión es **directa** (ping bajo) o **por
  relé** (parecido al túnel): ese es el dato que dice si compensa. El precio es
  que cada amigo instala Tailscale una vez.
- Cloudflare **no** sirve para esto en su plan gratuito: su proxy sólo entiende
  HTTP/HTTPS y Minecraft usa TCP en crudo. Sí es útil como DNS (nube gris)
  apuntando a la dirección del túnel.
- El diagnóstico de red detecta **CGNAT** por dos vías: comparando la IP que
  el router dice tener con la que ve internet, y comprobando si varios
  servicios externos te ven con IPs distintas (pool de salida del operador).
  Si hay CGNAT, abrir puertos no sirve y se propone un túnel: mejor decirlo
  que dejar al usuario peleándose con el router. UPnP se implementa sin
  dependencias externas (SSDP + SOAP) para no exigir compiladores al instalar.
- Los plugins y mods se **adjuntan desde la interfaz** (arrastrar y soltar o
  selector de archivos): el usuario nunca abre las carpetas del servidor. El
  nombre se valida (sólo `.jar`, sin rutas ni nombres reservados de Windows),
  hay límite de 200 MB y se escribe primero en `.part`. Desactivar no borra:
  renombra a `.jar.disabled`, que los cargadores ignoran.
- Los backups pueden hacerse con el servidor en marcha: se envía `save-off` y
  `save-all` antes de comprimir y `save-on` al terminar, el protocolo estándar
  para no corromper el mundo. La restauración exige el servidor detenido,
  valida cada entrada del ZIP contra el sandbox (anti zip-slip) y reemplaza la
  carpeta por intercambio: nunca queda una restauración a medias.

## Configuración avanzada

Copia `.env.example` a `.env` para cambiar puertos o rutas. Todas las claves
usan el prefijo `MSM_` (`MSM_PORT`, `MSM_SERVERS_DIR`, `MSM_LOG_LEVEL`, …). Las
preferencias de usuario (idioma, tema, rutas) se guardan además en la tabla
`configurations` de la base de datos.
