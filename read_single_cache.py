import os.path as osp
import glob
import io
import itertools
import json
import sys
import zipfile

from entrypoints import (Distribution, CaseSensitiveConfigParser, EntryPoint,
    BadEntryPoint, NoSuchEntryPoint,
)

def make_eps(cp, distro):
    for group_name, group in cp.items():
        for name, objref in group.items():
            with BadEntryPoint.err_to_warnings():
                yield group_name, EntryPoint.from_string(objref, name, distro)

def iter_entry_pts(path=None, repeated_distro='first'):
    if path is None:
        path = sys.path

    cache_file = osp.expanduser('~/.cache/entry_points.json')
    with open(cache_file) as f:
        cache_by_dir = json.load(f)

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
                    cp = CaseSensitiveConfigParser()
                    cp.read(ep_path)
                    yield from make_eps(cp, distro)

            elif zipfile.is_zipfile(folder):
                z = zipfile.ZipFile(folder)
                try:
                    info = z.getinfo('EGG-INFO/entry_points.txt')
                except KeyError:
                    continue
                cp = CaseSensitiveConfigParser()
                with z.open(info) as f:
                    fu = io.TextIOWrapper(f)
                    cp.read_file(fu,
                                 source=osp.join(folder, 'EGG-INFO',
                                                 'entry_points.txt'))
                    yield from make_eps(cp, distro)

            continue

        folder = osp.normpath(folder)
        if folder in cache_by_dir:
            cache = cache_by_dir[folder]
            for d in cache:
                distro = Distribution(d['distribution_name'], d['distribution_version'])
                with BadEntryPoint.err_to_warnings():
                    yield d['group'], EntryPoint.from_string(
                        d['reference'], d['name'], distro)
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
            cp = CaseSensitiveConfigParser()
            cp.read(path)
            yield from make_eps(cp, distro)

def get_group_all(group, path=None):
    """Find all entry points in a group.

    Returns a list of :class:`EntryPoint` objects.
    """
    result = []
    for group_name, ep in iter_entry_pts(path=path):
        if group_name == group:
            result.append(ep)

    return result


if __name__ == '__main__':
    import pprint

    pprint.pprint(get_group_all('console_scripts'))
