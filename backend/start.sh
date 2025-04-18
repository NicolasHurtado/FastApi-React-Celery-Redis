#!/bin/bash
set -e

# Show environment variables for debugging (without showing full passwords)
echo "Variables at the beginning of the script:"
echo "DATABASE_URL=${DATABASE_URL//:*@/:[PASSWORD_HIDDEN]@}"
echo "POSTGRES_HOST=${POSTGRES_HOST:-no defined}"
echo "POSTGRES_USER=${POSTGRES_USER:-no defined}"
echo "POSTGRES_DB=${POSTGRES_DB:-no defined}"
echo "POSTGRES_PASSWORD is ${POSTGRES_PASSWORD:+defined and is: }${POSTGRES_PASSWORD:-NOT DEFINED}"

# Funtion to wait for PostgreSQL to be available
wait_for_postgres() {
  echo "Esperando a que PostgreSQL esté disponible..."
  RETRIES=10
  
  # Comprobar si tenemos las variables específicas de Postgres
  if [ -z "$POSTGRES_HOST" ] || [ -z "$POSTGRES_PORT" ] || [ -z "$POSTGRES_USER" ] || [ -z "$POSTGRES_DB" ]; then
    echo "PostgreSQL environment variables not configured directly, trying to extract from DATABASE_URL..."
    
    # Intentar extraer variables desde DATABASE_URL si no están definidas
    if [[ "$DATABASE_URL" =~ postgresql.*://([^:]+):([^@]+)@([^:]+):([0-9]+)/([^?]+) ]]; then
      export POSTGRES_USER="${BASH_REMATCH[1]}"
      export POSTGRES_PASSWORD="${BASH_REMATCH[2]}"
      export POSTGRES_HOST="${BASH_REMATCH[3]}"
      export POSTGRES_PORT="${BASH_REMATCH[4]}"
      export POSTGRES_DB="${BASH_REMATCH[5]}"
    else
      echo "WARNING: Could not parse DATABASE_URL: $DATABASE_URL"
    fi
  fi
  
  echo "Connection to PostgreSQL: Host=$POSTGRES_HOST, Port=$POSTGRES_PORT, Database=$POSTGRES_DB, User=$POSTGRES_USER"
  echo "POSTGRES_PASSWORD is ${POSTGRES_PASSWORD:+defined and is: }${POSTGRES_PASSWORD:-NOT DEFINED}"
  
  until PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "SELECT 1" > /dev/null 2>&1 || [ $RETRIES -eq 0 ]; do
    echo "Trying to connect to PostgreSQL ($((RETRIES)) attempts remaining)..."
    RETRIES=$((RETRIES-1))
    sleep 2
  done

  if [ $RETRIES -eq 0 ]; then
    echo "Error: Could not connect to PostgreSQL after several attempts"
    echo "Last connection details used:"
    echo "Host: $POSTGRES_HOST"
    echo "Port: $POSTGRES_PORT" 
    echo "User: $POSTGRES_USER"
    echo "Database: $POSTGRES_DB"
    echo "Password is ${POSTGRES_PASSWORD:+defined and is: }${POSTGRES_PASSWORD:-NOT DEFINED}"
    exit 1
  fi
  echo "PostgreSQL is available"
}

# Verificar variables de entorno necesarias
if [ -z "$DATABASE_URL" ]; then
  echo "ERROR: La variable DATABASE_URL no está definida"
  exit 1
fi


echo "POSTGRES_PASSWORD after extraction: ${POSTGRES_PASSWORD:+defined}${POSTGRES_PASSWORD:-NOT DEFINED}"

# Esperar a que PostgreSQL esté disponible
wait_for_postgres

# Función para resetear y recrear las migraciones
echo "Configuring Alembic migrations..."

# Crear directorio de versiones si no existe
mkdir -p alembic/versions

# Generar migración automática
# echo "Generating automatic migration..."
# alembic revision --autogenerate -m "auto_migration_$(date +%Y%m%d%H%M%S)" || {
#   echo "Warning: Error generating migration. Continuing anyway."
# }

# Limpiar la tabla alembic_version en la base de datos
# echo "Limpiando referencias a migraciones anteriores..."
# PGPASSWORD=$POSTGRES_PASSWORD psql -h $POSTGRES_HOST -p $POSTGRES_PORT -U $POSTGRES_USER -d $POSTGRES_DB -c "DROP TABLE IF EXISTS alembic_version;" || {
#   echo "Warning: Could not clean alembic_version table. It may not exist yet."
#   exit 1
# }

# Apply migrations
echo "Applying migrations..."
alembic upgrade head || {
  echo "ERROR: Migration failed. Application will not start."
  exit 1
}

# Iniciar el servidor FastAPI en segundo plano
  echo "Starting FastAPI server in background..."
if [ "$ENVIRONMENT" = "development" ]; then
  echo "Development mode: automatic reload enabled"
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload --reload-dir /app --reload-include "*.py" --log-level ${LOG_LEVEL:-debug} &
else
  echo "Production mode: using multiple workers"
  uvicorn app.main:app --host 0.0.0.0 --port 8000 --workers 4 --proxy-headers --forwarded-allow-ips='*' --log-level ${LOG_LEVEL:-info} &
fi
#sleep 5

#Crear superusuario para administración
echo "Creating superuser for administration..."
python -m app.scripts.create_superuser || {
  echo "WARNING: Could not create superuser"
  exit 1
}

# Guardar el PID del proceso de uvicorn
UVICORN_PID=$!
echo "FastAPI server started with PID: $UVICORN_PID"

# Esperar a que el servidor esté listo (ajustar este tiempo según sea necesario)
echo "Waiting for FastAPI server to be ready..."
sleep 5

# Mantener el script ejecutándose para que el contenedor no se detenga
echo "All initialization tasks completed. Keeping the container active..."
wait $UVICORN_PID 