#!/usr/bin/env python3
"""Use Docker from a Linux hosted runner; never interpolate inputs into a shell."""
import json
import os
from pathlib import Path
import platform
import subprocess


def workspace_path(workspace, value):
    workspace = workspace.resolve()
    path = (workspace / value).resolve()
    if not path.is_relative_to(workspace):
        raise ValueError('Action paths must remain inside GITHUB_WORKSPACE')
    return path


def main():
    if platform.system() != 'Linux' or platform.machine() != 'x86_64':
        raise ValueError('The composite Action requires a Linux x86_64 runner with Docker')
    root = Path(os.environ['NROFORGE_ACTION_PATH']).resolve()
    workspace = Path(os.environ['GITHUB_WORKSPACE']).resolve()
    args = ['python3', '/nroforge/nroforge.py', 'build']
    for flag, key in [('--managed', 'NROFORGE_MANAGED'), ('--output', 'NROFORGE_OUTPUT')]:
        path = workspace_path(workspace, os.environ[key])
        args += [flag, '/workspace/' + str(path.relative_to(workspace))]
    profile = os.environ['NROFORGE_PROFILE']
    if profile != 'kuroaki-gimmick':
        profile = '/workspace/' + str(workspace_path(workspace, profile).relative_to(workspace))
    args += ['--profile', profile, '--sdk-cache', '/workspace/.nroforge/sdk']
    assets = os.environ.get('NROFORGE_ASSETS')
    if assets:
        args += ['--assets', '/workspace/' + str(workspace_path(workspace, assets).relative_to(workspace))]
    link = os.environ.get('NROFORGE_LINK', 'false')
    if link not in {'true', 'false'}:
        raise ValueError('link-assemblies must be true or false')
    if link == 'true':
        args += ['--link']
    jobs = int(os.environ.get('NROFORGE_JOBS', '2'))
    if jobs < 1:
        raise ValueError('jobs must be positive')
    args += ['--jobs', str(jobs)]
    subprocess.run(['docker', 'build', '--platform', 'linux/amd64', '-t', 'nroforge-local:2026.10.15', str(root)], check=True)
    subprocess.run(['docker', 'run', '--rm', '--platform', 'linux/amd64',
        '--mount', f'type=bind,source={workspace},target=/workspace',
        '--mount', f'type=bind,source={root},target=/nroforge,readonly',
        'nroforge-local:2026.10.15', *args], check=True)
    output = workspace_path(workspace, os.environ['NROFORGE_OUTPUT'])
    result = json.loads((output / 'outputs.json').read_text())
    with Path(os.environ['GITHUB_OUTPUT']).open('a') as f:
        for key, value in [('nro', result['nro']), ('sd-directory', result['sd'])]:
            relative = Path(value).relative_to('/workspace')
            f.write(f'{key}={workspace / relative}\n')


if __name__ == '__main__':
    main()
