"""Create content-addressed Mono Full AOT metadata and native configuration."""
import hashlib
import json
from pathlib import Path
import re
import shutil
import zlib


def load_profile(file):
    profile = json.loads(Path(file).read_text())
    for key in ['app_id', 'entry_assembly', 'title', 'author', 'version']:
        if not isinstance(profile.get(key), str) or not profile[key]:
            raise ValueError('Profile requires a nonempty string: ' + key)
    if not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', profile['app_id']) or profile['app_id'] in {'.', '..'}:
        raise ValueError('app_id must be a simple SD directory name')
    if not re.fullmatch(r'[A-Za-z0-9_][A-Za-z0-9_.-]*\.dll', profile['entry_assembly']):
        raise ValueError('entry_assembly must be a DLL filename')
    for key, maximum in [('title', 127), ('author', 127), ('version', 15)]:
        if len(profile[key].encode()) > maximum or any(ord(c) < 32 or c in '$`\\"#' for c in profile[key]):
            raise ValueError('Invalid NACP ' + key)
    return profile


def prepare(build, profile):
    build = Path(build)
    files = sorted((build / 'managed').glob('*.dll'))
    if not (build / 'managed' / profile['entry_assembly']).is_file() or not (build / 'managed/System.Private.CoreLib.dll').is_file():
        raise ValueError('Entry assembly or System.Private.CoreLib.dll missing')
    digest = hashlib.sha256()
    records = []
    dest = build / 'romfs/metadata'
    if dest.exists():
        shutil.rmtree(dest)
    dest.mkdir(parents=True)
    for f in files:
        data = f.read_bytes()
        digest.update(f.name.encode()); digest.update(data)
        shutil.copy2(f, dest / f.name)
        records.append((f.name, len(data), zlib.crc32(data)))
    root = '/switch/' + profile['app_id']
    runtime = root + '/AOT-' + digest.hexdigest()[:12]
    config = f'''[mono]
logging = true
icu = /mono/etc/icudt77l.dat
assembly_dir = {runtime}
config_dir = /mono/etc
[nx]
file_io_redirect = {root}/UserData/mono-aot.log
force_full_application = true
exit_process_on_end = true
'''
    c = lambda value: json.dumps(value, ensure_ascii=True)
    header = ['/* Generated from the exact AOT assembly closure. */',
        '#define KG_AOT_RUNTIME_ROOT ' + c(runtime),
        '#define KG_AOT_CONFIG_PATH ' + c(runtime + '/mono-full-aot.ini'),
        '#define KG_AOT_ASSEMBLY_PATH ' + c(runtime + '/' + profile['entry_assembly']),
        'struct kg_aot_file { const char *name; unsigned int size; unsigned long crc; };',
        'static const struct kg_aot_file kg_aot_files[] = {']
    header += ['    {' + c(n) + f', {s}U, 0x{crc:08x}UL' + '},' for n, s, crc in records]
    header += ['};', 'static const char kg_aot_config[] = ' + c(config) + ';', '']
    (build / 'kg_aot_payload.h').write_text('\n'.join(header))
    (build / 'nroforge_config.h').write_text('#pragma once\n#define NROFORGE_SD_ROOT ' + c(root) + '\n')
    manifest = {'sd_root': root, 'sd_runtime': runtime, 'entry_assembly': profile['entry_assembly'], 'files': records}
    (build / 'payload-manifest.json').write_text(json.dumps(manifest, indent=2) + '\n')
    return manifest
