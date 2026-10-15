import io
import json
from pathlib import Path
import struct
import tarfile
import tempfile
import unittest

from nroforge import check_nro
from scripts.payload import load_profile, prepare
from scripts.run_action import workspace_path
from scripts.sdk import check_files, digest, ensure, unpack


class ForgeChecks(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name).resolve()
        self.profile = {'app_id': 'AnotherApp', 'entry_assembly': 'Other.dll',
            'title': 'Another App', 'author': 'Example', 'version': '1.0.0'}

    def tearDown(self):
        self.temp.cleanup()

    def profile_file(self, profile):
        file = self.root / 'profile.json'
        file.write_text(json.dumps(profile))
        return file

    def test_generic_profile_and_metadata(self):
        profile = load_profile(self.profile_file(self.profile))
        managed = self.root / 'managed'
        managed.mkdir()
        (managed / 'Other.dll').write_bytes(b'example metadata')
        (managed / 'System.Private.CoreLib.dll').write_bytes(b'core metadata')
        result = prepare(self.root, profile)
        header = (self.root / 'kg_aot_payload.h').read_text()
        self.assertIn('/switch/AnotherApp/AOT-', header)
        self.assertIn('/Other.dll', header)
        self.assertNotIn('KuroakiGimmick', header)
        original = result['sd_runtime']
        self.assertEqual(prepare(self.root, profile)['sd_runtime'], original)
        (managed / 'Other.dll').write_bytes(b'changed metadata')
        self.assertNotEqual(prepare(self.root, profile)['sd_runtime'], original)

    def test_deleted_metadata_is_not_retained(self):
        managed = self.root / 'managed'
        managed.mkdir()
        for name in ['Other.dll', 'System.Private.CoreLib.dll', 'Removed.dll']:
            (managed / name).write_bytes(name.encode())
        prepare(self.root, self.profile)
        (managed / 'Removed.dll').unlink()
        prepare(self.root, self.profile)
        self.assertFalse((self.root / 'romfs/metadata/Removed.dll').exists())

    def test_profile_rejects_paths_and_make_injection(self):
        for key, value in [('app_id', '../oops'), ('app_id', 'a/b'), ('entry_assembly', '../Other.dll'),
                ('title', '$(shell touch /tmp/oops)'), ('author', 'x"; echo oops'), ('version', '1\n2')]:
            with self.subTest(key=key, value=value), self.assertRaises(ValueError):
                load_profile(self.profile_file(self.profile | {key: value}))

    def test_unicode_title_is_supported(self):
        title = '原生应用'
        self.assertEqual(load_profile(self.profile_file(self.profile | {'title': title}))['title'], title)

    def test_missing_entry_is_rejected(self):
        with self.assertRaises(ValueError):
            prepare(self.root, self.profile)

    def sdk_archive(self, unsafe=None):
        archive = self.root / 'sdk.tar.xz'
        file = self.root / 'compiler'
        file.write_bytes(b'compiler fixture')
        records = [{'path': 'tools/mono-aot-cross', 'bytes': file.stat().st_size, 'sha256': digest(file)}]
        with tarfile.open(archive, 'w:xz') as tar:
            for name, data in [('sdk/MANIFEST.json', json.dumps({'files': records}).encode()),
                    ('sdk/tools/mono-aot-cross', file.read_bytes())]:
                info = tarfile.TarInfo(name); info.size = len(data); info.mode = 0o755
                tar.addfile(info, io.BytesIO(data))
            if unsafe:
                info = tarfile.TarInfo(unsafe)
                if 'symlink' in unsafe:
                    info.type = tarfile.SYMTYPE; info.linkname = '/tmp/escape'
                tar.addfile(info)
        return archive

    def test_sdk_extraction_and_tamper_detection(self):
        out = self.root / 'unpacked'; out.mkdir()
        records = unpack(self.sdk_archive(), out, 'sdk')
        self.assertTrue((out / 'tools/mono-aot-cross').stat().st_mode & 0o111)
        (out / 'tools/mono-aot-cross').write_bytes(b'tampered')
        with self.assertRaises(ValueError):
            check_files(out, records)

    def test_sdk_rejects_traversal_and_symlinks(self):
        for path in ['sdk/../../escape', '/tmp/escape', 'sdk/symlink']:
            with self.subTest(path=path), self.assertRaises(ValueError):
                unpack(self.sdk_archive(path), self.root / 'out', 'sdk')

    def test_archive_digest_is_required(self):
        archive = self.sdk_archive()
        (self.root / 'toolchain.lock.json').write_text(json.dumps({'archive': archive.name,
            'sha256': '0' * 64, 'archive_root': 'sdk'}))
        with self.assertRaises(ValueError):
            ensure(self.root, self.root / 'cache')

    def test_split_sdk_assembly_and_bad_part_rejection(self):
        archive = self.sdk_archive()
        data = archive.read_bytes()
        records = []
        for index, content in enumerate([data[:100], data[100:]]):
            file = self.root / f'part{index}'
            file.write_bytes(content)
            records.append({'path': file.name, 'bytes': len(content), 'sha256': digest(file)})
        (self.root / 'toolchain.lock.json').write_text(json.dumps({'archive': archive.name,
            'sha256': digest(archive), 'archive_root': 'sdk', 'parts': records}))
        result = ensure(self.root, self.root / 'cache')
        self.assertEqual((result / 'tools/mono-aot-cross').read_bytes(), b'compiler fixture')
        (self.root / 'part0').write_bytes(b'changed')
        with self.assertRaises(ValueError):
            ensure(self.root, self.root / 'another-cache')

    def test_action_workspace_boundary(self):
        self.assertEqual(workspace_path(self.root, 'build/out'), self.root / 'build/out')
        with self.assertRaises(ValueError):
            workspace_path(self.root, '../outside')

    def test_nro_checks_metadata_regions(self):
        header = bytearray(0x80); header[0x10:0x14] = b'NRO0'
        struct.pack_into('<I', header, 0x18, 0x80)
        aset = b'ASET' + struct.pack('<IQQQQQQ', 0, 0, 0, 0x38, 0x4000, 0x4038, 16)
        file = self.root / 'test.nro'; file.write_bytes(header + aset + bytes(0x4000 + 16))
        check_nro(file)
        file.write_bytes(file.read_bytes()[:-1])
        with self.assertRaises(ValueError):
            check_nro(file)


if __name__ == '__main__':
    unittest.main()
