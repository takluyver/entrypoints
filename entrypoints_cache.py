"""Use a cache layer in front of entry point scanning."""

import errno
import glob
import hashlib
import itertools
import json
import logging
import os
import os.path
import struct
import sys

import entrypoints

NoSuchEntryPoint = entrypoints.NoSuchEntryPoint
BadEntryPoint = entrypoints.BadEntryPoint
EntryPoint = entrypoints.EntryPoint


log = logging.getLogger('entrypoints_cache')


def _get_cache_dir():
    """Locate a platform-appropriate cache directory to use.

    Does not ensure that the cache directory exists.
    """
    # Linux, Unix, AIX, etc.
    if os.name == 'posix' and sys.platform != 'darwin':
        # use ~/.cache if empty OR not set
        return os.environ.get("XDG_CACHE_HOME", None) \
              or os.path.expanduser('~/.cache/python-entrypoints')

    # Mac OS
    elif sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Caches/Python Entry Points')

    # Windows (hopefully)
    else:
        return os.environ.get('LOCALAPPDATA', None) \
               or os.path.expanduser('~\\AppData\\Local\\Python Entry Points')


def _get_mtime(name):
    try:
        s = os.stat(name)
        return s.st_mtime
    except OSError as err:
        if err.errno != errno.ENOENT:
            raise
    return -1.0


def _ftobytes(f):
    return struct.Struct('f').pack(f)


def _hash_settings_for_path(path):
    """Return a hash and the path settings that created it.
    """
    paths = []
    stat = os.stat
    h = hashlib.sha1()
    for entry in path:
        mtime = _get_mtime(entry)
        h.update(entry.encode('utf-8'))
        h.update(_ftobytes(mtime))
        paths.append((entry, mtime))

        for ep_file in itertools.chain(
                glob.iglob(os.path.join(entry,
                                        '*.dist-info',
                                        'entry_points.txt')),
                glob.iglob(os.path.join(entry,
                                        '*.egg-info',
                                        'entry_points.txt'))
        ):
            mtime = _get_mtime(ep_file)
            h.update(ep_file.encode('utf-8'))
            h.update(_ftobytes(mtime))
            paths.append((ep_file, mtime))

    return (h.hexdigest(), paths)


def _build_cacheable_data(path):
    groups = {}
    for config, distro in entrypoints.iter_files_distros(path=path):
        for group_name, group_val in config.items():
            groups.setdefault(group_name, []).extend(
                (name, epstr, distro.name, distro.version)
                for name, epstr in group_val.items()
            )
    return {'groups': groups}


class Cache:

    def __init__(self, cache_dir=None):
        if cache_dir is None:
            cache_dir = _get_cache_dir()
        self._dir = cache_dir

    def _get_data_for_path(self, path):
        if path is None:
            path = sys.path
        digest, path_values = _hash_settings_for_path(path)
        filename = os.path.join(self._dir, digest)
        try:
            log.debug('reading %s', filename)
            with open(filename, 'r') as f:
                data = json.load(f)
        except (IOError, json.JSONDecodeError):
            data = _build_cacheable_data(path)
            data['path_values'] = path_values
            try:
                log.debug('writing to %s', filename)
                os.makedirs(self._dir, exist_ok=True)
                with open(filename, 'w') as f:
                    json.dump(data, f)
            except (IOError, OSError):
                # Could not create cache dir or write file.
                pass
        return data

    def get_group_all(self, group, path=None):
        result = []
        data = self._get_data_for_path(path)
        group_data = data.get('groups', {}).get(group, [])
        for name, epstr, distro_name, distro_version in group_data:
            distro = entrypoints.Distribution(distro_name, distro_version)
            with BadEntryPoint.err_to_warnings():
                result.append(EntryPoint.from_string(epstr, name, distro))
        return result

    def get_group_named(self, group, path=None):
        result = {}
        for ep in self.get_group_all(group, path=path):
            if ep.name not in result:
                result[ep.name] = ep
        return result

    def get_single(self, group, name, path=None):
        data = self._get_data_for_path(path)
        group_data = data.get('groups', {}).get(group, [])
        for name, epstr, distro_name, distro_version in group_data:
            if name == name:
                distro = entrypoints.Distribution(distro_name, distro_version)
                with BadEntryPoint.err_to_warnings():
                    return EntryPoint.from_string(epstr, name, distro)
        raise NoSuchEntryPoint(group,  name)


_c = Cache()
get_group_all = _c.get_group_all
get_group_named = _c.get_group_named
get_single = _c.get_single


if __name__ == '__main__':
    logging.basicConfig(
        stream=sys.stderr,
        level=logging.DEBUG,
    )
    for ep in get_group_all(sys.argv[1]):
        print(ep)
        ep.load()
