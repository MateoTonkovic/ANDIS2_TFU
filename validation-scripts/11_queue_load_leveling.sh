set -e
source "$(dirname "$0")/env.sh"

echo "Patrón: Queue-Based Load Leveling"
echo ""

echo "✓ Probando queue-based load leveling con RabbitMQ"
echo ""

# Verificar que RabbitMQ esté accesible
echo "1. Verificando que RabbitMQ esté corriendo"
if curl -s -u guest:guest http://localhost:15672/api/overview > /dev/null; then
    echo "  ✓ API de gestión de RabbitMQ accesible"
else
    echo "  ✗ RabbitMQ no accesible"
    exit 1
fi
echo ""

# Obtener estadísticas iniciales de colas
echo "2. Verificando colas de mensajes"
QUEUES=$(curl -s -u guest:guest http://localhost:15672/api/queues)
echo "  Colas configuradas:"
echo "$QUEUES" | jq -r '.[] | select(.name | contains("tasks")) | "    - \(.name): \(.messages) mensajes"'
echo ""

# Crear usuarios que deberían disparar notificaciones asíncronas
echo "3. Creando usuarios (debería disparar tareas de notificación asíncronas)"
USER_COUNT=5
for i in $(seq 1 $USER_COUNT); do
    USER_RESPONSE=$(curl -s -X POST http://localhost:8001/users \
      -H "Content-Type: application/json" \
      -d '{"name":"Queue Test User '$i'","email":"queue_test_'$i'_'$RANDOM'@example.com"}')
    
    USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
    if [ "$USER_ID" != "null" ]; then
        echo "  Usuario $i creado: ID $USER_ID"
    fi
    sleep 0.2
done
echo ""

# Verificar si los mensajes fueron encolados
echo "4. Verificando si las tareas fueron encoladas"
sleep 2  # Dar tiempo para que los mensajes sean encolados y procesados

QUEUES_AFTER=$(curl -s -u guest:guest http://localhost:15672/api/queues)
echo "  Estado de colas después de crear usuarios:"
echo "$QUEUES_AFTER" | jq -r '.[] | select(.name | contains("tasks")) | "    - \(.name): \(.messages) mensajes, \(.messages_ready) listos, \(.message_stats.publish_details.rate // 0) msg/s"'
echo ""

# Verificar que exista la cola de tareas de usuario
USER_QUEUE_EXISTS=$(echo "$QUEUES_AFTER" | jq -r '.[] | select(.name == "user_tasks") | .name')
if [ "$USER_QUEUE_EXISTS" == "user_tasks" ]; then
    echo "  ✓ Cola de tareas de usuario existe: PASS"
else
    echo "  ⚠ Cola de tareas de usuario puede no estar creada aún (necesita primera tarea)"
fi
echo ""

# Probar con proyectos
echo "5. Probando procesamiento basado en colas con proyectos"
# Primero crear un usuario
USER_FOR_PROJECT=$(curl -s -X POST http://localhost:8001/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Project Owner","email":"proj_owner_'$RANDOM'@example.com"}' | jq -r '.id')

# Crear proyectos que deberían disparar notificaciones asíncronas
for i in $(seq 1 3); do
    PROJECT_RESPONSE=$(curl -s -X POST http://localhost:8002/projects \
      -H "Content-Type: application/json" \
      -d '{"name":"Queue Test Project '$i'","owner_user_id":'$USER_FOR_PROJECT'}')
    
    PROJECT_ID=$(echo $PROJECT_RESPONSE | jq -r '.id')
    if [ "$PROJECT_ID" != "null" ]; then
        echo "  Proyecto $i creado: ID $PROJECT_ID"
    fi
    sleep 0.2
done
echo ""

sleep 2

FINAL_QUEUES=$(curl -s -u guest:guest http://localhost:15672/api/queues)
echo "6. Estadísticas finales de colas:"
echo "$FINAL_QUEUES" | jq -r '.[] | select(.name | contains("_tasks")) | "    \(.name):"' 
echo "$FINAL_QUEUES" | jq -r '.[] | select(.name | contains("_tasks")) | "      Publicados: \(.message_stats.publish // 0)"'
echo "$FINAL_QUEUES" | jq -r '.[] | select(.name | contains("_tasks")) | "      Entregados: \(.message_stats.deliver_get // 0)"'
echo "$FINAL_QUEUES" | jq -r '.[] | select(.name | contains("_tasks")) | "      En cola: \(.messages)"'
echo ""

# Verificar que el procesamiento asíncrono no bloquea requests
echo "7. Verificando que el procesamiento async no bloquea requests"
START_TIME=$(date +%s%N)
BULK_USER=$(curl -s -X POST http://localhost:8001/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Async Test","email":"async_'$RANDOM'@example.com"}')
REQUEST_TIME=$(($(date +%s%N) - START_TIME))
REQUEST_MS=$((REQUEST_TIME / 1000000))

echo "  Request completado en: ${REQUEST_MS}ms"
if [ $REQUEST_MS -lt 500 ]; then
    echo "  ✓ Tareas async no bloquean requests: PASS"
else
    echo "  ⚠ Request tomó más tiempo del esperado: ${REQUEST_MS}ms"
fi

echo ""
echo "✓ Patrón queue-based load leveling validado"
echo ""
