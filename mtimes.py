"""Read mtimes of all entry points files."""
# Copyright (c) Thomas Kluyver and contributors
# Distributed under the terms of the MIT license; see LICENSE file.

import glob
import itertools
import os
import os.path as osp
import sys
import zipfile
from entrypoints import Distribution

def mtime(path):
    return os.stat(path).st_mtime

def iter_files_distros(path=None, repeated_distro='first'):
    if path is None:
        path = sys.path

    # Distributions found earlier in path will shadow those with the same name
    # found later. If these distributions used different module names, it may
    # actually be possible to import both, but in most cases this shadowing
    # will be correct.
    distro_names_seen = set()

    for folder in path:
        if folder.rstrip('/\\').endswith('.egg'):
            # Gah, eggs
            egg_name = osp.basename(folder)
            if '-' in egg_name:
                distro = Distribution(*egg_name.split('-')[:2])

                if (repeated_distro == 'first') \
                        and (distro.name in distro_names_seen):
                    continue
                distro_names_seen.add(distro.name)
            else:
                distro = None

            if osp.isdir(folder):
                ep_path = osp.join(folder, 'EGG-INFO', 'entry_points.txt')
                if osp.isfile(ep_path):
                    yield mtime(ep_path), distro

            elif zipfile.is_zipfile(folder):
                z = zipfile.ZipFile(folder)
                try:
                    info = z.getinfo('EGG-INFO/entry_points.txt')
                except KeyError:
                    continue
                yield mtime(folder), distro

                # cp = CaseSensitiveConfigParser()
                # with z.open(info) as f:
                #     fu = io.TextIOWrapper(f)
                #     cp.read_file(fu,
                #                  source=osp.join(folder, 'EGG-INFO',
                #                                  'entry_points.txt'))
                # yield cp, distro

            continue

        for path in itertools.chain(
                glob.iglob(osp.join(folder, '*.dist-info', 'entry_points.txt')),
                glob.iglob(osp.join(folder, '*.egg-info', 'entry_points.txt'))
        ):
            distro_name_version = osp.splitext(osp.basename(osp.dirname(path)))[
                0]
            if '-' in distro_name_version:
                distro = Distribution(*distro_name_version.split('-', 1))

                if (repeated_distro == 'first') \
                        and (distro.name in distro_names_seen):
                    continue
                distro_names_seen.add(distro.name)
            else:
                distro = None
            yield mtime(path), distro



if __name__ == '__main__':
    import pprint

    pprint.pprint(list(iter_files_distros()))
