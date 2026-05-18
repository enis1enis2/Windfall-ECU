import os
import zipfile
import tempfile
import shutil
from config import SERVERS_DIR
from models import create_server
from path_util import safe_path, safe_join, safe_write


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

        jar_candidates = [j for j in jar_files if any(kw in j.lower() for kw in ['server', 'paper', 'purpur', 'spigot', 'vanilla', 'fabric', 'quilt', 'forge', 'neoforge', 'minecraft_server'])]

        if jar_candidates:
            jar_file = jar_candidates[0]
        else:
            jar_file = jar_files[0]

        jar_lower = jar_file.lower()
        if 'paper' in jar_lower:
            detected_type = 'paper'
        elif 'folia' in jar_lower:
            detected_type = 'folia'
        elif 'purpur' in jar_lower:
            detected_type = 'purpur'
        elif 'fabric' in jar_lower:
            detected_type = 'fabric'
        elif 'quilt' in jar_lower:
            detected_type = 'quilt'
        elif 'forge' in jar_lower:
            detected_type = 'forge'
        elif 'neoforge' in jar_lower:
            detected_type = 'neoforge'
        else:
            detected_type = 'vanilla'

        if not server_name:
            base = os.path.basename(jar_file).replace('.jar', '')
            server_name = base if base else 'Imported Server'

        server_path = safe_path(SERVERS_DIR, server_name)

        if os.path.exists(server_path):
            shutil.rmtree(tmp_dir)
            return None, f'Server directory {os.path.basename(server_path)} already exists'

        shutil.copytree(extract_dir, server_path)

        eula_path = safe_join(server_path, 'eula.txt')
        if not os.path.isfile(eula_path):
            safe_write(eula_path, 'eula=true\n')

        jar_rel_path = jar_file

        server_id = create_server(
            name=server_name,
            path=server_path,
            jar_file=jar_rel_path,
            server_type=detected_type
        )

        shutil.rmtree(tmp_dir)
        return server_id, None

    except zipfile.BadZipFile:
        shutil.rmtree(tmp_dir)
        return None, 'Invalid zip file'
    except Exception as e:
        shutil.rmtree(tmp_dir)
        return None, str(e)
