import glob
import itertools
import json
import os.path as osp
import sys

from entrypoints import Distribution, CaseSensitiveConfigParser

cache_by_dir = {}

for folder in sys.path:
    if folder.rstrip('/\\').endswith('.egg'):
        print('Skipping cache for egg:', folder)
        continue

    if not osp.isdir(folder):
        print('Skipping cache for non-directory:', folder)
        continue

    print('Making cache for', folder)
    cached_ep = []

    for path in itertools.chain(
            glob.iglob(osp.join(folder, '*.dist-info', 'entry_points.txt')),
            glob.iglob(osp.join(folder, '*.egg-info', 'entry_points.txt'))
    ):
        distro_name_version = osp.splitext(osp.basename(osp.dirname(path)))[0]
        if '-' in distro_name_version:
            distro = Distribution(*distro_name_version.split('-', 1))
        else:
            distro = None
        cp = CaseSensitiveConfigParser()
        cp.read(path)
        for group_name, group in cp.items():
            for name, objref in group.items():
                cached_ep.append({
                    'group': group_name,
                    'name': name,
                    'reference': objref,
                    'distribution_name': distro.name,
                    'distribution_version': distro.version,
                })

    cache_by_dir[osp.normpath(folder)] = cached_ep
    print(len(cached_ep), "entry points found")

cache_file = osp.expanduser('~/.cache/entry_points.json')
with open(cache_file, 'w') as f:
    json.dump(cache_by_dir, f, indent=2, sort_keys=True)

print('\nWritten', cache_file)
