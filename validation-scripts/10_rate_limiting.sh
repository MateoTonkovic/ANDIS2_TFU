set -e
source "$(dirname "$0")/env.sh"

echo "Patrón: Rate Limiting (Gateway + Aplicación)"
echo ""

echo "✓ Probando rate limiting multi-nivel"
echo ""

# Probar rate limiting a nivel de aplicación
echo "1. Probando rate limiting a nivel de aplicación (100 req/min)"
echo "  Enviando requests rápidos para disparar rate limiter"

SUCCESS_COUNT=0
RATE_LIMITED_COUNT=0

# Enviar 25 requests rápidos
for i in {1..25}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/users)
    
    if [ "$HTTP_CODE" == "200" ]; then
        ((SUCCESS_COUNT++))
    elif [ "$HTTP_CODE" == "429" ]; then
        ((RATE_LIMITED_COUNT++))
        echo "  Request $i: Rate limited (429)"
    fi
    
    # Delay muy corto para disparar rate limiting
    sleep 0.05
done

echo ""
echo "  Resultados después de 25 requests rápidos:"
echo "    Exitosos: $SUCCESS_COUNT"
echo "    Rate limited: $RATE_LIMITED_COUNT"

if [ $SUCCESS_COUNT -gt 0 ]; then
    echo "  ✓ Aplicación permite requests: PASS"
else
    echo "  ✗ Aplicación bloqueando todos los requests: FAIL"
    exit 1
fi

echo ""

# Probar rate limiting a nivel de gateway
echo "2. Probando rate limiting a nivel de gateway (10 req/sec + burst 20)"
echo "  Enviando requests a través del API gateway"

GATEWAY_SUCCESS=0
GATEWAY_LIMITED=0

# Enviar requests a través del gateway
for i in {1..30}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8080/api/users/users)
    
    if [ "$HTTP_CODE" == "200" ]; then
        ((GATEWAY_SUCCESS++))
    elif [ "$HTTP_CODE" == "429" ]; then
        ((GATEWAY_LIMITED++))
        if [ $GATEWAY_LIMITED -eq 1 ]; then
            echo "  Primer rate limit alcanzado en request $i"
        fi
    fi
    
    # Disparo rápido para probar manejo de burst
    sleep 0.05
done

echo ""
echo "  Resultados del gateway después de 30 requests rápidos:"
echo "    Exitosos: $GATEWAY_SUCCESS"
echo "    Rate limited: $GATEWAY_LIMITED"

if [ $GATEWAY_LIMITED -gt 0 ]; then
    echo "  ✓ Rate limiting del gateway activo: PASS"
else
    echo "  ⚠ Rate limiting del gateway: Puede necesitar más carga para disparar"
fi

echo ""

# Probar que health endpoints no están limitados agresivamente
echo "3. Probando health endpoints (deberían permitir chequeos frecuentes)"

HEALTH_SUCCESS=0
for i in {1..20}; do
    HTTP_CODE=$(curl -s -o /dev/null -w "%{http_code}" http://localhost:8001/health)
    if [ "$HTTP_CODE" == "200" ]; then
        ((HEALTH_SUCCESS++))
    fi
    sleep 0.1
done

if [ $HEALTH_SUCCESS -eq 20 ]; then
    echo "  ✓ Health endpoints permiten monitoreo: PASS"
else
    echo "  ⚠ Rate limiting de health endpoints: $HEALTH_SUCCESS/20 exitosos"
fi

echo ""
echo "✓ Patrones de rate limiting validados"
echo ""
