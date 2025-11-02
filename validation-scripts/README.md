# Validation Scripts — Mini Gestor de Proyectos

Scripts de validación para funcionalidad core y **patrones arquitectónicos**.

## Contenido

### Parte 1: Pruebas Funcionales
Prueban: **smoke/health**, **ACID intra-servicio**, **idempotencia**,
**stateless + persistencia**, **aislamiento por schemas** y **concurrencia**.

1. `1_smoke.sh` - Smoke test básico
2. `2_acid_tasks.sh` - Transacciones ACID
3. `3_idempotency_users.sh` - Idempotencia
4. `4_stateless_restart.sh` - Stateless + persistencia
5. `5_schemas.sh` - Aislamiento por schemas
6. `6_concurrency_users.sh` - Concurrencia

### Parte 2: Patrones Arquitectónicos
Validan los **8 patrones** implementados (disponibilidad, rendimiento, seguridad):

7. `7_health_monitoring.sh` - **Health Endpoint Monitoring**
   - Verifica monitoreo detallado de dependencias
   
8. `8_cache_aside.sh` - **Cache-Aside Pattern**
   - Valida caché Redis y mejora de rendimiento
   
9. `9_circuit_breaker_retry.sh` - **Circuit Breaker + Retry**
   - Prueba prevención de fallos en cascada
   - Valida reintentos con exponential backoff
   
10. `10_rate_limiting.sh` - **Rate Limiting**
    - Verifica límites en gateway y aplicación
    
11. `11_queue_load_leveling.sh` - **Queue-Based Load Leveling**
    - Valida procesamiento asíncrono con RabbitMQ
    
12. `12_gateway_offloading.sh` - **Gateway Offloading**
    - Prueba routing y offloading de concerns
    
13. `13_gatekeeper.sh` - **Gatekeeper**
    - Valida autenticación/autorización con JWT

## Requisitos
- Servicios levantados: `docker compose up -d`
- macOS / Linux con `bash`, `curl`, `jq` y Docker
- Puertos disponibles: 8001-8004, 8080, 5432, 6379, 5672, 15672

## Uso

### Correr todo (funcionales + patrones)
```bash
chmod +x *.sh
./run_all.sh
```

### Solo pruebas de patrones
```bash
./run_pattern_tests.sh
```

### Scripts individuales
```bash
# Ejemplos
./7_health_monitoring.sh
./8_cache_aside.sh
./9_circuit_breaker_retry.sh
```

## Estructura de Pruebas

Cada script:
1. ✅ Ejecuta pruebas específicas del patrón
2. ✅ Valida comportamiento esperado
3. ✅ Retorna exit code 0 si pasa, 1 si falla
4. ✅ Imprime resultados detallados

## Patrones Validados

| Script | Patrón | Categoría | Tecnología |
|--------|--------|-----------|------------|
| 7 | Health Endpoint Monitoring | Disponibilidad | FastAPI |
| 9 | Circuit Breaker | Disponibilidad | pybreaker |
| 9 | Retry | Disponibilidad | tenacity |
| 10 | Rate Limiting | Disponibilidad | Redis + nginx |
| 8 | Cache-Aside | Rendimiento | Redis |
| 11 | Queue-Based Load Leveling | Rendimiento | RabbitMQ |
| 12 | Gateway Offloading | Seguridad | nginx |
| 13 | Gatekeeper | Seguridad | JWT/FastAPI |

**Total: 8 patrones** (4 disponibilidad + 2 rendimiento + 2 seguridad)

## Troubleshooting

### Error: "Connection refused"
```bash
# Verificar que todos los servicios estén corriendo
docker compose ps

# Revisar logs si algún servicio falló
docker compose logs users-api
docker compose logs redis
docker compose logs rabbitmq
```

### Error: "jq: command not found"
```bash
# macOS
brew install jq

# Ubuntu/Debian
sudo apt-get install jq
```

### RabbitMQ no responde
```bash
# RabbitMQ puede tardar 10-15s en iniciar
# Esperar y reintentar
docker compose logs rabbitmq
```

## Documentación Completa

Ver [../PATTERNS.md](../PATTERNS.md) para documentación detallada de cada patrón implementado.
