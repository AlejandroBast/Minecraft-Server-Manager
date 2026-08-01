# Minecraft Server Manager

Aplicación de escritorio con interfaz web local para crear, administrar y alojar
servidores de Minecraft Java Edition sin usar la consola ni editar ficheros a mano.

- El usuario **nunca** descarga jars ni Java: la aplicación lo hace por él.
- La aplicación **no limita** los recursos del equipo: sólo recomienda.
- Cada servidor es un proceso independiente supervisado por el backend.

## Estado

| Fase | Contenido | Estado |
|------|-----------|--------|
| 1 | Arquitectura del proyecto | ✅ completada |
| 2 | Backend FastAPI (CRUD de servidores, sistema) | ✅ completada |
| 3 | Frontend Next.js | ✅ completada |
| 4 | Creación de servidores | ✅ completada |
| 5 | Descarga automática (Java, jars, librerías) | pendiente |
| 6 | Consola en tiempo real (WebSockets) | pendiente |
| 7 | Backups | pendiente |
| 8 | Plugins y mods | pendiente |
| 9 | Red (IP, puertos, UPnP, dominio) | pendiente |
| 10 | Optimización y pruebas | pendiente |

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
│   │   └── services/   servidores, descargas, backups, red
│   └── tests/
├── frontend/           Next.js 16 + Tailwind 4 + shadcn/ui
│   └── src/
│       ├── app/        layout y dashboard
│       ├── components/ tarjetas, formulario de creación, panel de sistema
│       ├── hooks/      consulta periódica de la API
│       └── lib/        cliente tipado, tipos del contrato y formateo
├── servers/            un directorio por servidor creado
├── downloads/          jars, librerías y runtimes de Java
├── backups/            copias comprimidas en ZIP
├── database/           manager.db (SQLite)
├── logs/               app / servers / downloads / console
├── config/             preferencias exportadas
└── temp/               ficheros intermedios
```

## Puesta en marcha (backend)

```bash
cd backend
python -m venv .venv
.venv/Scripts/python.exe -m pip install -r requirements-dev.txt
.venv/Scripts/python.exe run.py
```

- API: <http://127.0.0.1:8000/api/v1/health>
- Documentación interactiva: <http://127.0.0.1:8000/docs>

Pruebas:

```bash
backend/.venv/Scripts/python.exe -m pytest
```

## Puesta en marcha (frontend)

Con el backend en marcha, en otra terminal:

```bash
cd frontend
npm install
npm run dev
```

Interfaz: <http://localhost:3000>

El navegador llama directamente a la API (`http://127.0.0.1:8000/api/v1`). Todo
corre en el mismo equipo, así que un proxy en Next sólo añadiría latencia. Para
apuntar a otra dirección, define `NEXT_PUBLIC_API_URL`.

Comprobaciones:

```bash
cd frontend && npx tsc --noEmit && npx eslint .
```

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

## Configuración

Copia `.env.example` a `.env`. Todas las claves usan el prefijo `MSM_`
(`MSM_PORT`, `MSM_SERVERS_DIR`, `MSM_LOG_LEVEL`, …). Las preferencias de usuario
(idioma, tema, rutas) se guardan además en la tabla `configurations`.

## Requisitos

- Python 3.12 o superior
- Node.js 20 o superior (a partir de la fase 3)
- Java: **no es necesario instalarlo**; la aplicación descarga el runtime
  adecuado para cada versión de Minecraft (fase 5).
