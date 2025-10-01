# Validation Scripts — Mini Gestor de Proyectos (FastAPI + Docker + ACID)

Estos scripts prueban: **smoke/health**, **ACID intra-servicio**, **idempotencia**,
**stateless + persistencia**, **aislamiento por schemas** y **concurrencia**.

## Requisitos
- Servicios levantados: `docker compose up -d`
- macOS / Linux con `bash`, `curl`, `jq` y Docker

## Uso
```bash
# dar permisos
chmod +x *.sh

# correr todo
./run_all.sh
```

Podés ejecutar cada script por separado también.
