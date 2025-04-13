#!/bin/bash
set -e

# Función mejorada para esperar a que PostgreSQL esté disponible
wait_for_postgres() {
  echo "Esperando a que PostgreSQL esté disponible..."
  
  RETRIES=10
  until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
    echo "Intentando conectar a PostgreSQL ($((RETRIES)) intentos restantes)..."
    RETRIES=$((RETRIES-1))
    sleep 2
  done

  if [ $RETRIES -eq 0 ]; then
    echo "Error: No se pudo conectar a PostgreSQL después de varios intentos"
    exit 1
  fi
  
  echo "PostgreSQL está disponible"
}

# Función para ejecutar migraciones de base de datos
apply_migrations() {
  echo "Aplicando migraciones de la base de datos..."
  # Ejecutar las migraciones de Alembic con reintentos si fallan
  alembic upgrade head || {
    echo "Error en las migraciones. Reintentando en 5 segundos..."
    sleep 5
    alembic upgrade head
  }
  echo "Migraciones aplicadas exitosamente"
}

# Variables de entorno para conexión a Postgres (de DATABASE_URL)
if [[ "$DATABASE_URL" =~ postgresql.*://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
  export POSTGRES_USER="${BASH_REMATCH[1]}"
  export POSTGRES_PASSWORD="${BASH_REMATCH[2]}"
  export POSTGRES_HOST="${BASH_REMATCH[3]}"
  export POSTGRES_PORT="${BASH_REMATCH[4]}"
  export POSTGRES_DB="${BASH_REMATCH[5]}"
  echo "Conexión a PostgreSQL: Host=$POSTGRES_HOST, Puerto=$POSTGRES_PORT, BD=$POSTGRES_DB"
else
  echo "Error: No se pudo parsear DATABASE_URL: $DATABASE_URL"
  exit 1
fi

# Esperar a que los servicios dependientes estén disponibles
wait_for_postgres

# Aplicar migraciones
apply_migrations

# Iniciar el servidor FastAPI (configuración para producción)
echo "Iniciando servidor FastAPI..."
if [ "$ENVIRONMENT" = "development" ]; then
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
else
  # Configuración para producción: múltiples workers (2 * núcleos + 1)
  # Omitimos --reload para producción
  exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*'
fi 