import os
import zipfile
import tempfile
import shutil
from config import SERVERS_DIR
from models import create_server


def import_zip(file_storage, server_name=None):
    tmp_dir = tempfile.mkdtemp()
    extract_dir = os.path.join(tmp_dir, 'extracted')
    os.makedirs(extract_dir, exist_ok=True)

    zip_path = os.path.join(tmp_dir, 'import.zip')
    file_storage.save(zip_path)

    try:
        with zipfile.ZipFile(zip_path, 'r') as zf:
            zf.extractall(extract_dir)

        jar_files = []
        for root, dirs, files in os.walk(extract_dir):
            for f in files:
                if f.endswith('.jar'):
                    rel = os.path.relpath(root, extract_dir)
                    jar_files.append(os.path.join(rel, f) if rel != '.' else f)

        if not jar_files:
            shutil.rmtree(tmp_dir)
            return None, 'No .jar file found in the zip archive'

        jar_candidates = [j for j in jar_files if 'server' in j.lower() or 'paper' in j.lower() or 'purpur' in j.lower() or 'spigot' in j.lower() or 'vanilla' in j.lower()]

        if jar_candidates:
            jar_file = jar_candidates[0]
        else:
            jar_file = jar_files[0]

        if not server_name:
            base = os.path.basename(jar_file).replace('.jar', '')
            server_name = base if base else 'Imported Server'

        safe_name = ''.join(c if c.isalnum() or c in ' _-' else '_' for c in server_name)
        server_path = os.path.join(SERVERS_DIR, safe_name)

        if os.path.exists(server_path):
            shutil.rmtree(tmp_dir)
            return None, f'Server directory {safe_name} already exists'

        shutil.copytree(extract_dir, server_path)

        jar_rel_path = jar_file

        server_id = create_server(
            name=server_name,
            path=server_path,
            jar_file=jar_rel_path,
            server_type='vanilla'
        )

        shutil.rmtree(tmp_dir)
        return server_id, None

    except zipfile.BadZipFile:
        shutil.rmtree(tmp_dir)
        return None, 'Invalid zip file'
    except Exception as e:
        shutil.rmtree(tmp_dir)
        return None, str(e)
