FROM python:3.11-slim

WORKDIR /app

# Instalar dependencias del sistema
RUN apt-get update && apt-get install -y \
    git \
    curl \
    && rm -rf /var/lib/apt/lists/*

# Clonar el repositorio de BunkrDownloader
RUN git clone https://github.com/Lysagxra/BunkrDownloader.git /app/bunkr

# Instalar dependencias del BunkrDownloader
RUN cd /app/bunkr && pip install --no-cache-dir -r requirements.txt

# Copiar la aplicación web
COPY app.py /app/
COPY requirements-web.txt /app/
COPY templates/ /app/templates/

# Instalar dependencias de la aplicación web
RUN pip install --no-cache-dir -r /app/requirements-web.txt

# Crear carpetas necesarias
RUN mkdir -p /app/Downloads

# Cambiar permisos
RUN chmod +x /app/app.py

# Exponer puerto
EXPOSE 5000

# Comando para iniciar la aplicación
CMD ["python", "/app/app.py"]
