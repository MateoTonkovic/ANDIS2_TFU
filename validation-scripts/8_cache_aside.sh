set -e
source "$(dirname "$0")/env.sh"

echo "Patrón: Cache-Aside"
echo ""

echo "✓ Probando patrón cache-aside con endpoint de usuarios"
echo ""

# Crear usuario de prueba
echo "1. Creando usuario de prueba"
USER_RESPONSE=$(curl -s -X POST http://localhost:8001/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Cache Test User","email":"cache_test_'$RANDOM'@example.com"}')

USER_ID=$(echo $USER_RESPONSE | jq -r '.id')
echo "  Usuario creado con ID: $USER_ID"
echo ""

# Primera lectura - va a la base de datos y puebla el cache
echo "2. Primera lectura (cache miss - consulta base de datos)"
START_TIME=$(date +%s%N)
FIRST_READ=$(curl -s http://localhost:8001/users/$USER_ID)
FIRST_TIME=$(($(date +%s%N) - START_TIME))
echo "  Tiempo de respuesta: $((FIRST_TIME / 1000000))ms"
echo "  Usuario: $(echo $FIRST_READ | jq -c '.')"
echo ""

# Segunda lectura - obtiene desde cache (más rápido)
echo "3. Segunda lectura (cache hit - debería ser más rápido)"
START_TIME=$(date +%s%N)
SECOND_READ=$(curl -s http://localhost:8001/users/$USER_ID)
SECOND_TIME=$(($(date +%s%N) - START_TIME))
echo "  Tiempo de respuesta: $((SECOND_TIME / 1000000))ms"
echo "  Usuario: $(echo $SECOND_READ | jq -c '.')"
echo ""

# Verificar consistencia del cache
if [ "$FIRST_READ" == "$SECOND_READ" ]; then
    echo "  ✓ Consistencia del cache: PASS (respuestas coinciden)"
else
    echo "  ✗ Consistencia del cache: FAIL (respuestas no coinciden)"
    exit 1
fi

echo ""

# Probar cache de lista
echo "4. Probando cache de endpoint de lista"
echo "  Primer request de lista (cache miss)"
START_TIME=$(date +%s%N)
LIST_FIRST=$(curl -s http://localhost:8001/users)
LIST_FIRST_TIME=$(($(date +%s%N) - START_TIME))
echo "  Tiempo de respuesta: $((LIST_FIRST_TIME / 1000000))ms"
echo ""

echo "  Segundo request de lista (cache hit)"
START_TIME=$(date +%s%N)
LIST_SECOND=$(curl -s http://localhost:8001/users)
LIST_SECOND_TIME=$(($(date +%s%N) - START_TIME))
echo "  Tiempo de respuesta: $((LIST_SECOND_TIME / 1000000))ms"
echo ""

if [ "$LIST_FIRST" == "$LIST_SECOND" ]; then
    echo "  ✓ Consistencia de cache de lista: PASS"
else
    echo "  ✗ Consistencia de cache de lista: FAIL"
    exit 1
fi

echo ""

# Probar invalidación de cache al crear
echo "5. Probando invalidación de cache al crear"
NEW_USER=$(curl -s -X POST http://localhost:8001/users \
  -H "Content-Type: application/json" \
  -d '{"name":"Cache Invalidation Test","email":"cache_inv_'$RANDOM'@example.com"}')
echo "  Nuevo usuario creado: $(echo $NEW_USER | jq -r '.id')"

# La lista debería estar actualizada (cache invalidado)
UPDATED_LIST=$(curl -s http://localhost:8001/users)
USER_COUNT=$(echo $UPDATED_LIST | jq '. | length')
echo "  Cantidad de usuarios actualizada: $USER_COUNT"

if echo $UPDATED_LIST | jq -e "map(select(.id == $(echo $NEW_USER | jq -r '.id'))) | length == 1" > /dev/null; then
    echo "  ✓ Invalidación de cache: PASS (nuevo usuario aparece en lista)"
else
    echo "  ✗ Invalidación de cache: FAIL"
    exit 1
fi

echo ""
echo "✓ Todas las pruebas de cache-aside PASARON"
echo ""

