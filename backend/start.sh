#!/bin/bash
set -e

# Mostrar variables de entorno para debugging (sin mostrar contraseñas completas)
echo "Variables al inicio del script:"
echo "DATABASE_URL=${DATABASE_URL//:*@/:[PASSWORD_HIDDEN]@}"
echo "POSTGRES_HOST=${POSTGRES_HOST:-no definido}"
echo "POSTGRES_USER=${POSTGRES_USER:-no definido}"
echo "POSTGRES_DB=${POSTGRES_DB:-no definido}"
echo "POSTGRES_PASSWORD está ${POSTGRES_PASSWORD:+definida y es: }${POSTGRES_PASSWORD:-NO DEFINIDA}"

# Función para esperar a que PostgreSQL esté disponible
wait_for_postgres() {
  echo "Esperando a que PostgreSQL esté disponible..."
  RETRIES=10
  
  # Comprobar si tenemos las variables específicas de Postgres
  if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_PORT" ] || [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ]; then
    echo "Variables de entorno para PostgreSQL no configuradas directamente, intentando extraer de DATABASE_URL..."
    
    # Intentar extraer variables desde DATABASE_URL si no están definidas
    if [[ "$DATABASE_URL" =~ postgresql.*://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
      export POSTGRES_USER="${BASH_REMATCH[1]}"
      export POSTGRES_PASSWORD="${BASH_REMATCH[2]}"
      export POSTGRES_HOST="${BASH_REMATCH[3]}"
      export POSTGRES_PORT="${BASH_REMATCH[4]}"
      export POSTGRES_DB="${BASH_REMATCH[5]}"
    else
      echo "ADVERTENCIA: No se pudo parsear DATABASE_URL: $DATABASE_URL"
    fi
  fi
  
  echo "Conexión a PostgreSQL: Host=$POSTGRES_HOST, Puerto=$POSTGRES_PORT, BD=$POSTGRES_DB, Usuario=$POSTGRES_USER"
  echo "POSTGRES_PASSWORD está ${POSTGRES_PASSWORD:+definida y es: }${POSTGRES_PASSWORD:-NO DEFINIDA}"
  
  until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
    echo "Intentando conectar a PostgreSQL ($((RETRIES)) intentos restantes)..."
    RETRIES=$((RETRIES-1))
    sleep 2
  done

  if [ $RETRIES -eq 0 ]; then
    echo "Error: No se pudo conectar a PostgreSQL después de varios intentos"
    echo "Últimos detalles de conexión usados:"
    echo "Host: $POSTGRES_HOST"
    echo "Puerto: $POSTGRES_PORT" 
    echo "Usuario: $POSTGRES_USER"
    echo "BD: $POSTGRES_DB"
    echo "Password está ${POSTGRES_PASSWORD:+definida y es: }${POSTGRES_PASSWORD:-NO DEFINIDA}"
    exit 1
  fi
  echo "PostgreSQL está disponible"
}

# Función para resetear y recrear las migraciones
reset_migrations() {
  echo "Configurando migraciones de Alembic..."
  
  # Crear directorio de versiones si no existe
  mkdir -p alembic/versions
  
  # Limpiar directorio de versiones (excepto README)
  find alembic/versions -type f -not -name "README" -delete
  
  # Limpiar la tabla alembic_version para eliminar cualquier referencia a migraciones perdidas
  PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "DROP TABLE IF EXISTS alembic_version;" || true
  
  # Generar migración inicial
  echo "Generando migración inicial..."
  alembic revision --autogenerate -m "initial_$(date +%Y%m%d)" || {
    echo "Advertencia: Error al generar migración. Continuando de todos modos."
  }
}

# Verificar variables de entorno necesarias
if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: La variable DATABASE_URL no está definida"
  exit 1
fi

# Asegurar que las variables de PostgreSQL estén definidas
# Ya sea directamente o a través de DATABASE_URL
export POSTGRES_HOST=${POSTGRES_HOST:-db}
export POSTGRES_PORT=${POSTGRES_PORT:-5432}
export POSTGRES_USER=${POSTGRES_USER:-vacation_user}
export POSTGRES_DB=${POSTGRES_DB:-vacation_db}
# Si POSTGRES_PASSWORD no está definida, intentar usar un valor por defecto
export POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-vacation_pass}

# Extraer variables desde DATABASE_URL si es necesario
if [[ "$DATABASE_URL" =~ postgresql.*://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
  # Solo asignar si no están definidas explícitamente
  POSTGRES_USER=${POSTGRES_USER:-${BASH_REMATCH[1]}}
  POSTGRES_PASSWORD=${POSTGRES_PASSWORD:-${BASH_REMATCH[2]}}
  POSTGRES_HOST=${POSTGRES_HOST:-${BASH_REMATCH[3]}}
  POSTGRES_PORT=${POSTGRES_PORT:-${BASH_REMATCH[4]}}
  POSTGRES_DB=${POSTGRES_DB:-${BASH_REMATCH[5]}}
  echo "Variables extraídas de DATABASE_URL: Host=$POSTGRES_HOST, Puerto=$POSTGRES_PORT, BD=$POSTGRES_DB"
fi

echo "POSTGRES_PASSWORD después de extracción: ${POSTGRES_PASSWORD:+definida}${POSTGRES_PASSWORD:-NO DEFINIDA}"

# Esperar a que PostgreSQL esté disponible
wait_for_postgres

# Resetear y recrear migraciones
reset_migrations

# Aplicar migraciones
echo "Aplicando migraciones..."
alembic upgrade head || {
  echo "Error en la migración. Continuando de todos modos para permitir desarrollo."
}

# Iniciar el servidor FastAPI
echo "Iniciando servidor FastAPI..."
if [ "$ENVIRONMENT" = "development" ]; then
  echo "Modo desarrollo: recarga automática activada"
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app --reload-include "*.py" --log-level ${LOG_LEVEL:-debug}
else
  echo "Modo producción: usando múltiples workers"
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*' --log-level ${LOG_LEVEL:-info}
fi 