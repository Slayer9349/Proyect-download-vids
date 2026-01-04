import os
import sys
import json
import threading
import subprocess
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for

app = Flask(__name__)
app.config['DOWNLOAD_FOLDER'] = '/app/Downloads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024

# Crear carpeta si no existe
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Diccionario para rastrear descargas
download_status = {}

def get_downloaded_files():
    """Obtener lista de archivos descargados"""
    files = []
    try:
        for root, dirs, filenames in os.walk(app.config['DOWNLOAD_FOLDER']):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                if os.path.isfile(filepath):
                    files.append({
                        'name': filename,
                        'size': os.path.getsize(filepath),
                        'url': url_for('download_file', filename=filename)
                    })
    except Exception as e:
        print(f"Error obteniendo archivos: {e}")
    return sorted(files, key=lambda x: x['name'])

def start_download(url, download_id):
    """Ejecutar descarga en thread separado"""
    try:
        download_status[download_id] = {
            'status': 'downloading',
            'url': url,
            'progress': 50,
            'error': None
        }
        
        # Ejecutar el downloader.py
        cmd = [
            'python3',
            '/app/bunkr/downloader.py',
            url,
            '--custom-path',
            '/app',
            '--disable-ui'
        ]
        
        print(f"Ejecutando: {' '.join(cmd)}")
        result = subprocess.run(cmd, capture_output=True, text=True, timeout=3600, cwd='/app/bunkr')
        
        print(f"Return code: {result.returncode}")
        print(f"Stdout: {result.stdout}")
        print(f"Stderr: {result.stderr}")
        
        if result.returncode == 0:
            download_status[download_id]['status'] = 'completed'
            download_status[download_id]['progress'] = 100
            download_status[download_id]['files'] = get_downloaded_files()
        else:
            error_msg = result.stderr if result.stderr else 'Error desconocido durante la descarga'
            download_status[download_id]['status'] = 'error'
            download_status[download_id]['error'] = error_msg
            download_status[download_id]['progress'] = 0
        
    except subprocess.TimeoutExpired:
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['error'] = 'La descarga tardó demasiado (timeout de 1 hora)'
        download_status[download_id]['progress'] = 0
    except Exception as e:
        print(f"Excepción: {str(e)}")
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['error'] = str(e)
        download_status[download_id]['progress'] = 0

@app.route('/')
def index():
    """Página principal"""
    return render_template('index.html')

@app.route('/api/download', methods=['POST'])
def api_download():
    """API para iniciar descarga"""
    data = request.get_json()
    url = data.get('url', '').strip()
    
    if not url:
        return jsonify({'error': 'URL no proporcionada'}), 400
    
    # Validar que sea una URL de Bunkr
    if 'bunkr' not in url.lower():
        return jsonify({'error': 'Por favor proporciona una URL válida de Bunkr'}), 400
    
    # Generar ID único
    download_id = f"download_{len(download_status)}_{os.urandom(4).hex()}"
    
    # Iniciar descarga en thread
    thread = threading.Thread(target=start_download, args=(url, download_id))
    thread.daemon = True
    thread.start()
    
    return jsonify({
        'download_id': download_id,
        'status': 'started'
    })

@app.route('/api/status/<download_id>')
def api_status(download_id):
    """Obtener estado de una descarga"""
    if download_id not in download_status:
        return jsonify({'error': 'Descarga no encontrada'}), 404
    
    return jsonify(download_status[download_id])

@app.route('/api/files')
def api_files():
    """Listar archivos disponibles"""
    try:
        files = get_downloaded_files()
        return jsonify({'files': files})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/download/<filename>')
def download_file(filename):
    """Descargar archivo"""
    try:
        # Sanitizar nombre de archivo
        safe_filename = os.path.basename(filename)
        # Verificar que el archivo existe en Downloads
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], safe_filename)
        
        if not os.path.exists(filepath):
            # Si no está en la raíz, buscar en subdirectorios
            for root, dirs, filenames in os.walk(app.config['DOWNLOAD_FOLDER']):
                if safe_filename in filenames:
                    return send_from_directory(root, safe_filename, as_attachment=True)
            return jsonify({'error': 'Archivo no encontrado'}), 404
        
        return send_from_directory(app.config['DOWNLOAD_FOLDER'], safe_filename, as_attachment=True)
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Eliminar archivo"""
    try:
        safe_filename = os.path.basename(filename)
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], safe_filename)
        
        if os.path.exists(filepath) and os.path.isfile(filepath):
            os.remove(filepath)
            return jsonify({'status': 'deleted'})
        return jsonify({'error': 'Archivo no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_downloads():
    """Limpiar todas las descargas"""
    try:
        import shutil
        for item in os.listdir(app.config['DOWNLOAD_FOLDER']):
            path = os.path.join(app.config['DOWNLOAD_FOLDER'], item)
            if os.path.isfile(path):
                os.remove(path)
            elif os.path.isdir(path):
                shutil.rmtree(path)
        download_status.clear()
        return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.errorhandler(404)
def not_found(e):
    return jsonify({'error': 'No encontrado'}), 404

@app.errorhandler(500)
def server_error(e):
    return jsonify({'error': 'Error del servidor'}), 500

if __name__ == '__main__':
    print("=" * 50)
    print("🚀 Bunkr Downloader Web - Servidor iniciado")
    print("=" * 50)
    print("📍 Accede a: http://localhost:5000")
    print("=" * 50)
    app.run(host='0.0.0.0', port=5000, debug=False, use_reloader=False)
