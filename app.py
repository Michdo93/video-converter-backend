import os
import subprocess
import uuid
from flask import Flask, request, send_file, jsonify
from flask_cors import CORS

app = Flask(__name__)
CORS(app, resources={r"/*": {"origins": "*"}})

# Mime-Types für Video-Formate
MIME_TYPES = {
    'mp4': 'video/mp4',
    'webm': 'video/webm',
    'avi': 'video/x-msvideo',
    'mkv': 'video/x-matroska',
    'mov': 'video/quicktime',
    'flv': 'video/x-flv',
    'wmv': 'video/x-ms-wmv'
}

@app.route('/convert', methods=['POST'])
def convert_video():
    if 'file' not in request.files:
        return jsonify({"error": "Keine Datei hochgeladen"}), 400
    
    file = request.files['file']
    target_format = request.form.get('target_format', '').lower().strip()
    
    if file.filename == '' or not target_format:
        return jsonify({"error": "Ungültige Parameter"}), 400

    filename, file_extension = os.path.splitext(file.filename)
    source_format = file_extension.lower().replace('.', '')

    if source_format == target_format:
        return jsonify({"error": "Quell- und Zielformat sind identisch."}), 400

    # Eindeutige IDs für temporäre Dateien generieren, um Konflikte bei parallelen Zugriffen zu vermeiden
    unique_id = uuid.uuid4().hex
    input_path = f"/tmp/input_{unique_id}.{source_format}"
    output_path = f"/tmp/output_{unique_id}.{target_format}"

    try:
        # 1. Datei temporär auf Festplatte speichern (FFmpeg benötigt physischen Zugriff)
        file.save(input_path)

        # 2. FFmpeg-Befehl zusammenbauen
        # Wir nutzen "-preset ultrafast", um die CPU von Render.com maximal zu schonen!
        cmd = [
            "ffmpeg", "-y",
            "-i", input_path,
            "-c:v", "libx264" if target_format in ['mp4', 'mkv', 'mov'] else "libvpx-vp9" if target_format == 'webm' else "copy",
            "-preset", "ultrafast",
            "-c:a", "aac",
            "-strict", "experimental",
            output_path
        ]

        # Wenn zu AVI/WMV konvertiert wird, nutzen wir einfachere Codecs für maximale Kompatibilität
        if target_format in ['avi', 'wmv']:
            cmd = ["ffmpeg", "-y", "-i", input_path, output_path]

        # 3. Konvertierung ausführen
        process = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True)

        if process.returncode != 0:
            raise Exception(f"FFmpeg Fehler: {process.stderr}")

        # 4. Konvertierte Datei in den Speicher laden
        with open(output_path, 'rb') as f:
            video_bytes = f.read()

        # 5. Temporäre Dateien sofort wieder löschen
        os.remove(input_path)
        os.remove(output_path)

        mime = MIME_TYPES.get(target_format, 'application/octet-stream')

        return send_file(
            io.BytesIO(video_bytes) if 'io' in globals() else __import__('io').BytesIO(video_bytes),
            mimetype=mime,
            as_attachment=True,
            download_name=f"{filename}.{target_format}"
        )

    except Exception as e:
        # Im Fehlerfall aufräumen
        for path in [input_path, output_path]:
            if os.path.exists(path):
                os.remove(path)
        return jsonify({"error": f"Konvertierungsfehler: {str(e)}"}), 500

if __name__ == '__main__':
    app.run(port=8080)
