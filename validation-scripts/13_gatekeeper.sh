set -e
source "$(dirname "$0")/env.sh"

echo "Patrón: Gatekeeper (Autenticación/Autorización)"
echo ""

echo "✓ Probando servicio Gatekeeper para control de acceso..."
echo ""

# Verificar que Auth API esté corriendo
echo "1. Verificando que Auth API (Gatekeeper) esté corriendo..."
AUTH_HEALTH=$(curl -s http://localhost:8004/health)
if echo "$AUTH_HEALTH" | jq -e '.status == "healthy"' > /dev/null; then
    echo "  ✓ Auth API (Gatekeeper) está healthy"
else
    echo "  ✗ Auth API no está disponible"
    exit 1
fi
echo ""

# Test de login exitoso
echo "2. Probando autenticación exitosa (login)..."
LOGIN_RESPONSE=$(curl -s -X POST http://localhost:8004/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"admin123"}')

ACCESS_TOKEN=$(echo $LOGIN_RESPONSE | jq -r '.access_token')
TOKEN_TYPE=$(echo $LOGIN_RESPONSE | jq -r '.token_type')

if [ "$ACCESS_TOKEN" != "null" ] && [ -n "$ACCESS_TOKEN" ]; then
    echo "  ✓ Login exitoso: Token JWT emitido"
    echo "  Token type: $TOKEN_TYPE"
    echo "  Token (primeros 50 chars): ${ACCESS_TOKEN:0:50}..."
else
    echo "  ✗ Login falló"
    echo "  Respuesta: $LOGIN_RESPONSE"
    exit 1
fi
echo ""

# Test de login fallido
echo "3. Probando autenticación fallida (credenciales incorrectas)..."
FAILED_LOGIN=$(curl -s -w "\nHTTP_CODE:%{http_code}" -X POST http://localhost:8004/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"admin","password":"wrong_password"}')

HTTP_CODE=$(echo "$FAILED_LOGIN" | grep "HTTP_CODE" | cut -d: -f2)

if [ "$HTTP_CODE" == "401" ]; then
    echo "  ✓ Gatekeeper rechaza credenciales inválidas: PASS (401)"
else
    echo "  ✗ Gatekeeper no rechazó credenciales inválidas (código: $HTTP_CODE)"
    exit 1
fi
echo ""

# Test de validación de token
echo "4. Probando validación de token..."
VALIDATION=$(curl -s -X POST http://localhost:8004/auth/validate \
  -H "Authorization: Bearer $ACCESS_TOKEN")

IS_VALID=$(echo $VALIDATION | jq -r '.valid')
USERNAME=$(echo $VALIDATION | jq -r '.username')

if [ "$IS_VALID" == "true" ]; then
    echo "  ✓ Token validado exitosamente"
    echo "  Usuario: $USERNAME"
    echo "  Roles: $(echo $VALIDATION | jq -c '.roles')"
else
    echo "  ✗ Validación de token falló"
    exit 1
fi
echo ""

# Test de token inválido
echo "5. Probando rechazo de token inválido..."
INVALID_VALIDATION=$(curl -s -X POST http://localhost:8004/auth/validate \
  -H "Authorization: Bearer token_invalido_12345")

IS_INVALID=$(echo $INVALID_VALIDATION | jq -r '.valid')

if [ "$IS_INVALID" == "false" ]; then
    echo "  ✓ Gatekeeper rechaza tokens inválidos: PASS"
    echo "  Error: $(echo $INVALID_VALIDATION | jq -r '.error')"
else
    echo "  ✗ Gatekeeper aceptó token inválido"
    exit 1
fi
echo ""

# Test de whoami
echo "6. Probando endpoint whoami (info del usuario autenticado)..."
WHOAMI=$(curl -s http://localhost:8004/auth/whoami \
  -H "Authorization: Bearer $ACCESS_TOKEN")

WHOAMI_USERNAME=$(echo $WHOAMI | jq -r '.username')

if [ "$WHOAMI_USERNAME" == "admin" ]; then
    echo "  ✓ Endpoint whoami retorna info correcta: PASS"
    echo "  Usuario: $WHOAMI_USERNAME"
    echo "  ID: $(echo $WHOAMI | jq -r '.user_id')"
else
    echo "  ✗ Whoami falló"
    exit 1
fi
echo ""

# Test de refresh token
echo "7. Probando renovación de token..."
REFRESH_RESPONSE=$(curl -s -X POST http://localhost:8004/auth/refresh \
  -H "Authorization: Bearer $ACCESS_TOKEN")

NEW_TOKEN=$(echo $REFRESH_RESPONSE | jq -r '.access_token')

if [ "$NEW_TOKEN" != "null" ] && [ -n "$NEW_TOKEN" ]; then
    echo "  ✓ Token renovado exitosamente: PASS"
else
    echo "  ✗ Renovación de token falló"
    exit 1
fi
echo ""

# Test de diferentes usuarios con diferentes roles
echo "8. Probando autenticación con diferentes roles..."

# Login como usuario regular
USER_LOGIN=$(curl -s -X POST http://localhost:8004/auth/login \
  -H "Content-Type: application/json" \
  -d '{"username":"user","password":"user123"}')

USER_TOKEN=$(echo $USER_LOGIN | jq -r '.access_token')

if [ "$USER_TOKEN" != "null" ]; then
    echo "  ✓ Login de usuario regular exitoso"
    
    # Validar token de usuario
    USER_VALIDATION=$(curl -s -X POST http://localhost:8004/auth/validate \
      -H "Authorization: Bearer $USER_TOKEN")
    
    USER_ROLES=$(echo $USER_VALIDATION | jq -c '.roles')
    echo "  Roles de usuario: $USER_ROLES"
    
    if echo $USER_ROLES | grep -q "user"; then
        echo "  ✓ Roles asignados correctamente: PASS"
    fi
else
    echo "  ✗ Login de usuario regular falló"
    exit 1
fi
echo ""

# Test de acceso via gateway
echo "9. Probando acceso a Auth API via gateway..."
GATEWAY_AUTH=$(curl -s http://localhost:8080/auth/health)

if echo "$GATEWAY_AUTH" | jq -e '.status == "healthy"' > /dev/null; then
    echo "  ✓ Gateway rutea a Auth API correctamente: PASS"
else
    echo "  ⚠ Gateway puede no estar ruteando a Auth API"
fi

echo ""
echo "✓ Patrón Gatekeeper validado"
echo ""

