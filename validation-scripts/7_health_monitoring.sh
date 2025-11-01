set -e
source "$(dirname "$0")/env.sh"

echo "Patrón: Health Endpoint Monitoring"
echo ""

echo "1. Health Check de Users API:"
USERS_HEALTH=$(curl -s http://localhost:8001/health)
echo "$USERS_HEALTH" | jq '.'

if echo "$USERS_HEALTH" | jq -e '.dependencies.database.status == "healthy"' > /dev/null; then
    echo "  ✓ Health check de base de datos: PASS"
else
    echo "  ✗ Health check de base de datos: FAIL"
    exit 1
fi

if echo "$USERS_HEALTH" | jq -e '.dependencies.redis.status == "healthy"' > /dev/null; then
    echo "  ✓ Health check de Redis: PASS"
else
    echo "  ✗ Health check de Redis: FAIL"
    exit 1
fi

if echo "$USERS_HEALTH" | jq -e '.dependencies.rabbitmq.status == "healthy"' > /dev/null; then
    echo "  ✓ Health check de RabbitMQ: PASS"
else
    echo "  ✗ Health check de RabbitMQ: FAIL"
    exit 1
fi

echo ""

echo "2. Health Check de Projects API:"
PROJECTS_HEALTH=$(curl -s http://localhost:8002/health)
echo "$PROJECTS_HEALTH" | jq '.'

if echo "$PROJECTS_HEALTH" | jq -e '.dependencies."users-api".status == "healthy"' > /dev/null; then
    echo "  ✓ Verificación de dependencia Users API: PASS"
else
    echo "  ✗ Verificación de dependencia Users API: FAIL"
    exit 1
fi

echo ""

echo "3. Health Check de Tasks API:"
TASKS_HEALTH=$(curl -s http://localhost:8003/health)
echo "$TASKS_HEALTH" | jq '.'

if echo "$TASKS_HEALTH" | jq -e '.dependencies."users-api".status == "healthy"' > /dev/null; then
    echo "  ✓ Verificación de dependencia Users API: PASS"
else
    echo "  ✗ Verificación de dependencia Users API: FAIL"
    exit 1
fi

if echo "$TASKS_HEALTH" | jq -e '.dependencies."projects-api".status == "healthy"' > /dev/null; then
    echo "  ✓ Verificación de dependencia Projects API: PASS"
else
    echo "  ✗ Verificación de dependencia Projects API: FAIL"
    exit 1
fi

echo ""

echo "4. Health Check del API Gateway:"
GATEWAY_HEALTH=$(curl -s http://localhost:8080/gateway/health)
echo "$GATEWAY_HEALTH"

if [ "$GATEWAY_HEALTH" == "Gateway OK" ]; then
    echo "  ✓ Health check del gateway: PASS"
else
    echo "  ✗ Health check del gateway: FAIL"
    exit 1
fi

echo ""
echo "✓ Todas las pruebas de health monitoring PASARON"

