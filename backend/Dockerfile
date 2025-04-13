# Usa una imagen base de Python más pequeña
FROM python:3.11-slim as build

# Establece variables de entorno
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    POETRY_VERSION=1.6.1

# Instala dependencias del sistema
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    libc6-dev \
    libpq-dev \
    postgresql-client \
    curl \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Establece el directorio de trabajo
WORKDIR /app

# Copia e instala dependencias primero (mejor cacheado)
COPY requirements.txt .

# Instala las dependencias de Python
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# Copia el código de la aplicación
COPY . .

# Dar permisos de ejecución al script de inicio
RUN chmod +x start.sh

# Configuración de seguridad - crear usuario no-root
RUN addgroup --system app && \
    adduser --system --group app && \
    chown -R app:app /app

# Cambia al usuario no privilegiado
USER app

# Expón el puerto que usará FastAPI
EXPOSE 8000

# Define el comando de entrada para producción
CMD ["./start.sh"] 