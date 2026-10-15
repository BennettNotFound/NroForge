"""Unpack only verified SDK inputs from the immutable toolchain archive."""
import hashlib
import json
from pathlib import Path, PurePosixPath
import shutil
import tarfile
import tempfile


def digest(path):
    with Path(path).open('rb') as f:
        return hashlib.file_digest(f, 'sha256').hexdigest()


def selected(name):
    return name.startswith(('sdk/', 'runtime/', 'tools/llvm/')) or name == 'tools/mono-aot-cross'


def check_files(root, records):
    for r in records:
        p = root / r['path']
        if p.is_symlink() or not p.is_file() or p.stat().st_size != r['bytes'] or digest(p) != r['sha256']:
            raise ValueError('SDK input missing or changed: ' + r['path'])


def unpack(archive, destination, archive_root):
    """Reject links/traversal before extracting; verify the archived manifest."""
    destination = Path(destination)
    with tarfile.open(archive, 'r:xz') as tar:
        members = tar.getmembers()
        names = set()
        for m in members:
            p = PurePosixPath(m.name)
            if p.is_absolute() or '..' in p.parts or not p.parts or p.parts[0] != archive_root:
                raise ValueError('Unsafe SDK archive path: ' + m.name)
            if not (m.isdir() or m.isfile()) or m.name in names:
                raise ValueError('Unsupported or duplicate SDK archive member: ' + m.name)
            names.add(m.name)
        manifest_file = tar.extractfile(archive_root + '/MANIFEST.json')
        if manifest_file is None:
            raise ValueError('SDK manifest missing')
        records = [r for r in json.load(manifest_file)['files'] if selected(r['path'])]
        wanted = {r['path'] for r in records}
        if not records or 'tools/mono-aot-cross' not in wanted:
            raise ValueError('Incomplete SDK manifest')
        for m in members:
            relative = PurePosixPath(m.name).relative_to(archive_root).as_posix()
            if not m.isfile() or not selected(relative):
                continue
            if relative not in wanted:
                raise ValueError('Unlisted SDK input: ' + relative)
            target = destination / relative
            target.parent.mkdir(parents=True, exist_ok=True)
            with tar.extractfile(m) as stream, target.open('wb') as output:
                shutil.copyfileobj(stream, output)
            target.chmod(0o755 if m.mode & 0o111 else 0o644)
    check_files(destination, records)
    return records


def ensure(repo, cache):
    lock = json.loads((repo / 'toolchain.lock.json').read_text())
    cache = Path(cache).resolve()
    cache.mkdir(parents=True, exist_ok=True)
    if lock.get('parts'):
        archive = cache / (lock['sha256'] + '.tar.xz')
        if not archive.exists():
            with tempfile.NamedTemporaryFile(prefix='assemble-', dir=cache, delete=False) as stream:
                temporary = Path(stream.name)
                try:
                    for part in lock['parts']:
                        file = repo / part['path']
                        if file.stat().st_size != part['bytes'] or digest(file) != part['sha256']:
                            raise ValueError('SDK archive part changed: ' + part['path'])
                        with file.open('rb') as source:
                            shutil.copyfileobj(source, stream)
                    stream.flush()
                    if digest(temporary) != lock['sha256']:
                        raise ValueError('Assembled SDK SHA-256 mismatch')
                    temporary.rename(archive)
                finally:
                    temporary.unlink(missing_ok=True)
    else:
        archive = repo / lock['archive']
    if digest(archive) != lock['sha256']:
        raise ValueError('Toolchain archive SHA-256 does not match toolchain.lock.json')
    destination = cache / lock['sha256'][:16]
    if destination.exists():
        marker = json.loads((destination / '.verified.json').read_text())
        if marker['archive_sha256'] != lock['sha256']:
            raise ValueError('SDK cache belongs to another archive')
        check_files(destination, marker['files'])
        return destination
    cache.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='unpack-', dir=cache) as temporary:
        stage = Path(temporary) / 'sdk'
        stage.mkdir()
        records = unpack(archive, stage, lock['archive_root'])
        (stage / '.verified.json').write_text(json.dumps({'archive_sha256': lock['sha256'], 'files': records}))
        stage.rename(destination)
    return destination
