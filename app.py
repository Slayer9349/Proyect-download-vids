import os
import sys
import json
import threading
from pathlib import Path
from flask import Flask, render_template, request, jsonify, send_from_directory, url_for
from werkzeug.utils import secure_filename

# Agregar el directorio de bunkr al path
sys.path.insert(0, '/app/bunkr')

from downloader import Downloader

app = Flask(__name__)
app.config['DOWNLOAD_FOLDER'] = '/app/Downloads'
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024  # 16MB max

# Crear carpeta si no existe
os.makedirs(app.config['DOWNLOAD_FOLDER'], exist_ok=True)

# Diccionario para rastrear descargas en progreso
download_status = {}

def start_download(url, download_id):
    """Función para ejecutar descarga en un thread separado"""
    try:
        download_status[download_id] = {
            'status': 'downloading',
            'url': url,
            'progress': 0,
            'error': None,
            'files': []
        }
        
        downloader = Downloader(
            url=url,
            download_path=app.config['DOWNLOAD_FOLDER'],
            disable_ui=True
        )
        downloader.download()
        
        # Obtener lista de archivos descargados
        files = []
        for root, dirs, filenames in os.walk(app.config['DOWNLOAD_FOLDER']):
            for filename in filenames:
                filepath = os.path.join(root, filename)
                files.append({
                    'name': filename,
                    'path': filepath,
                    'size': os.path.getsize(filepath),
                    'download_url': url_for('download_file', filename=filename, _external=True)
                })
        
        download_status[download_id]['status'] = 'completed'
        download_status[download_id]['files'] = files
        
    except Exception as e:
        download_status[download_id]['status'] = 'error'
        download_status[download_id]['error'] = str(e)

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
    
    # Generar ID único para esta descarga
    download_id = f"download_{len(download_status)}"
    
    # Iniciar descarga en thread separado
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
    """Listar archivos disponibles para descargar"""
    files = []
    try:
        for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                files.append({
                    'name': filename,
                    'size': os.path.getsize(filepath),
                    'url': url_for('download_file', filename=filename)
                })
    except Exception as e:
        return jsonify({'error': str(e)}), 500
    
    return jsonify({'files': files})

@app.route('/download/<filename>')
def download_file(filename):
    """Descargar archivo"""
    try:
        return send_from_directory(
            app.config['DOWNLOAD_FOLDER'],
            filename,
            as_attachment=True
        )
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/delete/<filename>', methods=['DELETE'])
def delete_file(filename):
    """Eliminar archivo"""
    try:
        filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], secure_filename(filename))
        if os.path.exists(filepath):
            os.remove(filepath)
            return jsonify({'status': 'deleted'})
        return jsonify({'error': 'Archivo no encontrado'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500

@app.route('/api/clear', methods=['POST'])
def clear_downloads():
    """Limpiar todas las descargas"""
    try:
        for filename in os.listdir(app.config['DOWNLOAD_FOLDER']):
            filepath = os.path.join(app.config['DOWNLOAD_FOLDER'], filename)
            if os.path.isfile(filepath):
                os.remove(filepath)
        download_status.clear()
        return jsonify({'status': 'cleared'})
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(host='0.0.0.0', port=5000, debug=False)
