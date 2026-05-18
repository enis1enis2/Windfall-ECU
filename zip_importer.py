import os, zipfile, tempfile, shutil
from config import SERVERS_DIR
from models import create_server
from path_util import safe_path, safe_join, safe_write

def import_zip(file_storage, server_name=None):
    tmp = tempfile.mkdtemp()
    ed = os.path.join(tmp, 'extracted')
    os.makedirs(ed, exist_ok=True)
    file_storage.save(os.path.join(tmp, 'import.zip'))

    try:
        with zipfile.ZipFile(os.path.join(tmp, 'import.zip')) as zf: zf.extractall(ed)

        jars = []
        for root, dirs, files in os.walk(ed):
            for f in files:
                if f.endswith('.jar'):
                    r = os.path.relpath(root, ed)
                    jars.append(os.path.join(r, f) if r != '.' else f)

        if not jars: shutil.rmtree(tmp); return None, 'No .jar file found in the zip archive'

        jc = [j for j in jars if any(kw in j.lower() for kw in
             ['server', 'paper', 'purpur', 'spigot', 'vanilla', 'fabric', 'quilt', 'forge', 'neoforge', 'minecraft_server'])]
        jf = (jc or jars)[0]

        dt = 'vanilla'
        for kw, t in [('paper', 'paper'), ('folia', 'folia'), ('purpur', 'purpur'),
                       ('fabric', 'fabric'), ('quilt', 'quilt'), ('forge', 'forge'), ('neoforge', 'neoforge')]:
            if kw in jf.lower(): dt = t; break

        sn = server_name or (os.path.basename(jf).replace('.jar', '') or 'Imported Server')
        sp = safe_path(SERVERS_DIR, sn)
        if os.path.exists(sp): shutil.rmtree(tmp); return None, f'Server directory {os.path.basename(sp)} already exists'

        shutil.copytree(ed, sp)
        el = safe_join(sp, 'eula.txt')
        if not os.path.isfile(el): safe_write(el, 'eula=true\n')

        sid = create_server(name=sn, path=sp, jar_file=jf, server_type=dt)
        shutil.rmtree(tmp)
        return sid, None

    except zipfile.BadZipFile: shutil.rmtree(tmp); return None, 'Invalid zip file'
    except: shutil.rmtree(tmp); return None, 'Import failed'
