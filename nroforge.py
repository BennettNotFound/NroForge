#!/usr/bin/env python3
"""NroForge: linked .NET 9 assemblies -> LLVM Full AOT -> Switch NRO."""
import argparse
import json
import os
from pathlib import Path
import platform
import re
import shutil
import struct
import subprocess
import sys
from scripts.payload import load_profile, prepare
from scripts.sdk import digest, ensure

ROOT = Path(__file__).resolve().parent


def run(*args, **kwargs):
    subprocess.run([str(a) for a in args], check=True, **kwargs)


def link(input_dir, build, sdk, entry, env):
    base = sdk / 'sdk/mono'
    xml = base / 'src/mono/System.Private.CoreLib/src/ILLink'
    args = ['dotnet', base / 'artifacts/bin/Mono.Linker/Debug/net9.0/illink.dll',
        '-x', xml / 'ILLink.Descriptors.xml', '-x', xml / 'ILLink.LinkAttributes.xml',
        '-d', input_dir, '-d', base / 'artifacts/bin/mono/libnx.arm64.Debug',
        '-d', base / 'artifacts/bin/runtime/net9.0-libnx-Debug-arm64']
    for name, value in [('System.Runtime.CompilerServices.RuntimeFeature.IsDynamicCodeSupported', 'false'),
            ('System.Runtime.CompilerServices.RuntimeFeature.IsDynamicCodeCompiled', 'false'),
            ('System.Text.Json.JsonSerializer.IsReflectionEnabledByDefault', 'false'),
            ('System.Resources.UseSystemResourceKeys', 'true')]:
        args += ['--feature', name, value]
    run(*args, '--skip-unresolved', 'false', '--trim-mode', 'link', '-a', input_dir / entry,
        '-out', build / 'managed', env=env)


def check_nro(file):
    with Path(file).open('rb') as f:
        header = f.read(0x80)
        if len(header) != 0x80 or header[0x10:0x14] != b'NRO0':
            raise ValueError('Invalid NRO: ' + str(file))
        size = struct.unpack_from('<I', header, 0x18)[0]
        if not 0x80 <= size <= Path(file).stat().st_size - 0x38:
            raise ValueError('Invalid NRO image size')
        f.seek(size)
        aset = f.read(0x38)
        if len(aset) != 0x38 or aset[:4] != b'ASET' or struct.unpack_from('<I', aset, 4)[0] != 0:
            raise ValueError('NRO asset section missing')
        regions = [struct.unpack_from('<QQ', aset, i) for i in [8, 24, 40]]
        for offset, length in regions:
            if length and (offset < 0x38 or size + offset + length > Path(file).stat().st_size):
                raise ValueError('NRO asset region outside the file')
        if regions[1][1] != 0x4000 or not regions[2][1]:
            raise ValueError('NACP or embedded metadata ROMFS missing')


def build(args):
    if platform.system() != 'Linux' or platform.machine() not in {'x86_64', 'AMD64'}:
        raise ValueError('Native builds require Linux x86_64; use the composite Action or Docker')
    profile_path = ROOT / 'profiles' / (args.profile + '.json')
    profile = load_profile(profile_path if profile_path.is_file() else args.profile)
    managed, output = args.managed.resolve(), args.output.resolve()
    if not managed.is_dir() or output.exists():
        raise ValueError('Managed input must exist and output must be a new directory')
    for source in [managed] + ([args.assets.resolve()] if args.assets else []):
        if source == output or source in output.parents:
            raise ValueError('Output must not be inside an input directory')
    if not (managed / profile['entry_assembly']).is_file():
        raise ValueError('Missing entry assembly: ' + profile['entry_assembly'])
    if args.assets and not args.assets.is_dir():
        raise ValueError('Assets directory does not exist')
    sdk = ensure(ROOT, args.sdk_cache)
    for path in [output, sdk]:
        if not re.fullmatch(r'[A-Za-z0-9_./+-]+', str(path)):
            raise ValueError('Native Makefile paths must use ASCII letters, numbers, /, _, ., + or -')
    devkit = Path(os.environ.get('DEVKITPRO', '/opt/devkitpro'))
    env = dict(os.environ)
    env.update(DEVKITPRO=str(devkit), MONO_NX_ROOT=str(sdk / 'sdk/mono'), ICU_NX_INSTALL_DIR=str(sdk / 'sdk/icu'),
        PATH=f'{devkit}/devkitA64/bin:{devkit}/tools/bin:' + env.get('PATH', ''),
        LD_LIBRARY_PATH=str(sdk / 'tools/llvm/lib') + (':' + env['LD_LIBRARY_PATH'] if env.get('LD_LIBRARY_PATH') else ''),
        PKG_CONFIG_LIBDIR=f'{sdk}/sdk/sdl3/lib/pkgconfig:{sdk}/sdk/mesa/lib/pkgconfig:{devkit}/portlibs/switch/lib/pkgconfig')
    for tool in ['aarch64-none-elf-gcc', 'elf2nro', 'nacptool', 'pkg-config', 'make'] + (['dotnet'] if args.link else []):
        if not shutil.which(tool, path=env['PATH']):
            raise ValueError('Missing build tool: ' + tool)
    run('pkg-config', '--exists', 'sdl3', 'vulkan', env=env)
    output.mkdir(parents=True)
    if args.link:
        link(managed, output, sdk, profile['entry_assembly'], env)
    else:
        (output / 'managed').mkdir()
        for file in managed.glob('*.dll'):
            shutil.copy2(file, output / 'managed' / file.name)
    run(sys.executable, ROOT / 'tools/compile_full_aot.py', '--managed', output / 'managed',
        '--compiler', sdk / 'tools/mono-aot-cross', '--llvm-tools', sdk / 'tools/llvm/bin',
        '--output', output / 'objects', '--jobs', args.jobs, env=env)
    objects = sorted((output / 'objects').glob('*.o'))
    modules = json.loads((output / 'aot-manifest.json').read_text())
    if len(objects) != len(modules) * 2:
        raise ValueError('LLVM AOT did not produce both primary and LLVM objects for every module')
    symbols = subprocess.check_output(['aarch64-none-elf-nm', '-g', '--defined-only', *map(str, objects)], env=env, text=True)
    for module in modules:
        if not re.search(r'\b' + re.escape(module['symbol']) + r'\b', symbols):
            raise ValueError('AOT module registration symbol missing: ' + module['symbol'])
    print(f'Validated {len(objects)} AOT objects and {len(modules)} exported registration symbols.', flush=True)
    payload = prepare(output, profile)
    runner = output / 'runner'
    shutil.copytree(ROOT / 'runner', runner)
    run('make', '-C', runner, f'KG_SWITCH_NATIVE={runner}/native', f'KG_SWITCH_AOT={output}',
        f'NROFORGE_SDK={sdk}',
        'KG_PKG_CONFIG=pkg-config', 'MONO_NX_USE_SDL2=0', 'MONO_NX_USE_CIMGUI=0',
        f'TARGET={profile["app_id"]}', 'BUILD=build-native', 'DEFINES=-DKG_SWITCH_TLS_FIX=1',
        f'APP_TITLE={profile["title"]}', f'APP_AUTHOR={profile["author"]}', f'APP_VERSION={profile["version"]}',
        'NO_ICON=1', env=env)
    name = profile['app_id'] + '.nro'
    nro = output / name
    shutil.copy2(runner / name, nro)
    check_nro(nro)
    sd = output / 'sd'
    app = sd / 'switch' / profile['app_id']
    app.mkdir(parents=True)
    shutil.copy2(nro, app / name)
    for directory in ['UserData', 'Songs', 'Exports', 'Temp']:
        (app / directory).mkdir()
    if args.assets:
        shutil.copytree(args.assets, app / 'Assets', ignore=shutil.ignore_patterns('.DS_Store', '._*'))
    icu = sd / 'mono/etc'
    icu.mkdir(parents=True)
    shutil.copy2(sdk / 'runtime/mono/etc/icudt77l.dat', icu / 'icudt77l.dat')
    (app / 'launch.args').write_text(profile.get('launch_args', ''))
    info = {'toolchain': json.loads((ROOT / 'toolchain.lock.json').read_text()), 'profile': profile,
        'nro': {'file': name, 'sha256': digest(nro), 'bytes': nro.stat().st_size},
        'metadata': payload, 'hardware_tested': False}
    (output / 'BUILD-INFO.json').write_text(json.dumps(info, indent=2) + '\n')
    (output / 'outputs.json').write_text(json.dumps({'nro': str(nro), 'sd': str(sd)}))
    print('NRO:', nro)
    print('SD staging:', sd)


def main():
    p = argparse.ArgumentParser(description=__doc__)
    sub = p.add_subparsers(dest='command', required=True)
    verify = sub.add_parser('verify-sdk')
    verify.add_argument('--sdk-cache', type=Path, default=Path('.nroforge/sdk'))
    b = sub.add_parser('build')
    b.add_argument('--managed', type=Path, required=True)
    b.add_argument('--profile', default='kuroaki-gimmick')
    b.add_argument('--output', type=Path, required=True)
    b.add_argument('--assets', type=Path)
    b.add_argument('--link', action='store_true', help='ILLink raw publish output using the bundled libnx BCL')
    b.add_argument('--jobs', type=int, default=2)
    b.add_argument('--sdk-cache', type=Path, default=Path('.nroforge/sdk'))
    args = p.parse_args()
    if args.command == 'verify-sdk':
        print('Verified SDK:', ensure(ROOT, args.sdk_cache))
    else:
        if args.jobs < 1:
            p.error('--jobs must be positive')
        build(args)


if __name__ == '__main__':
    try:
        main()
    except (OSError, ValueError, subprocess.CalledProcessError) as ex:
        print('NroForge:', ex, file=sys.stderr)
        sys.exit(1)
