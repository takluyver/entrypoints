from copy import deepcopy
import errno
import glob
import io
import itertools
import json
import logging
import os
import os.path as osp
import stat
import sys
from tempfile import mkstemp
import zipfile

from entrypoints import Distribution, CaseSensitiveConfigParser, EntryPoint,\
    entry_point_pattern

log = logging.getLogger(__name__)

if sys.version_info[0] >= 3:
    PY3 = True
    replace = os.replace

    def read_user_cache(path):
        """Load a JSON file, returning an empty dict if the file is not present"""
        try:
            with open(path, 'r', encoding='utf-8') as f:
                return json.load(f)
        except FileNotFoundError:
            return {}

else:
    PY3 = False
    def replace(src, dst):
        if os.name == 'nt':
            try:
                os.unlink(dst)
            except OSError as e:
                if e.errno != errno.ENOENT:
                    raise
        os.rename(src, dst)


    def read_user_cache(path):
        """Load a JSON file, returning an empty dict if the file is not present"""
        try:
            with open(path, 'rb') as f:
                return json.load(f)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            return {}


def atomic_json_dump(obj, path, **kwargs):
    """Overwrite a JSON file as atomically as possible.

    This creates a temporary file in the same directory and renames it after
    closing. It should be atomic except in Python 2 on Windows.
    """
    dirname, basename = osp.split(path)
    fd, tmpname = mkstemp(dir=dirname)
    try:
        if PY3:
            with open(fd, 'w', encoding='utf-8') as f:
                json.dump(obj, f, **kwargs)
        else:
            with open(fd, 'wb') as f:
                json.dump(obj, f, **kwargs)
        # TODO: chmod?
    except:
        os.unlink(tmpname)
        raise
    else:
        replace(tmpname, path)

def get_cache_dir():
    """Locate a platform-appropriate cache directory to use.

    Does not ensure that the cache directory exists.
    """
    # Linux, Unix, AIX, etc.
    if os.name == 'posix' and sys.platform != 'darwin':
        # use ~/.cache if empty OR not set
        return os.environ.get("XDG_CACHE_HOME", None) \
              or os.path.expanduser('~/.cache')

    # Mac OS
    elif sys.platform == 'darwin':
        return os.path.expanduser('~/Library/Caches')

    # Windows (hopefully)
    else:
        return os.environ.get('LOCALAPPDATA', None) \
               or os.path.expanduser('~\\AppData\\Local')

def write_user_cache(data, path):
    """Write a JSON file atomically, after ensuring that the directory exists"""
    directory = osp.dirname(path)
    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise
    atomic_json_dump(data, path, indent=2, sort_keys=True)

def entrypoints_from_configparser(cp):
    res = []
    for group_name, group in sorted(cp.items()):
        for name, epstr in sorted(group.items()):
            m = entry_point_pattern.match(epstr)
            if m:
                mod, obj, extras = m.group('modulename', 'objectname', 'extras')
                if extras is not None:
                    extras = [e.strip() for e in extras.split(',')]
                res.append({
                    'group': group_name,
                    'name': name,
                    'module_name': mod,
                    'object_name': obj,
                    'extras': extras,
                })
            else:
                log.warning("Invalid entry point specification: %r", epstr)
    return res


class EntryPointsScanner(object):
    def __init__(self, cache_file=None):
        if cache_file is None:
            cache_file = osp.join(get_cache_dir(), 'entrypoints.json')
        self.cache_file = cache_file
        self.user_cache = read_user_cache(cache_file)

    def _abspath_multi(self, paths):
        """Like os.path.abspath(), but avoid calling getcwd multiple times"""
        res = []
        cwd = os.getcwd()
        for path in paths:
            if not osp.isabs(path):
                path = osp.join(cwd, path)
            res.append(osp.normpath(path))
        return res

    def scan(self, locations=None):
        """Get entry points from a list of paths (sys.path by default)"""
        if locations is None:
            locations = sys.path
        locations = self._abspath_multi(locations)

        cache_modified = False
        for path in locations:
            locn_ep = self.entrypoints_for_path(path)
            if locn_ep != self.user_cache.get(path):
                self.user_cache[path] = locn_ep
                cache_modified = True
            yield locn_ep

        if cache_modified:
            write_user_cache(self.user_cache, self.cache_file)

    def rebuild_cache(self, add_locations=None):
        """Rebuild the cache, discard cached data for paths which don't exist"""
        add_locations = self._abspath_multi(add_locations or [])
        locations = set(self.user_cache).union(add_locations)
        self.user_cache = {}
        for path in locations:
            if osp.exists(path):
                self.user_cache[path] = self.entrypoints_for_path(path)

        write_user_cache(self.user_cache, self.cache_file)

    def entrypoints_for_path(self, path):
        """Get the entry points from a given path.

        This does use the cache if it is valid. For .egg paths, any cached
        data is considered valid (since the path includes the version number).
        For other paths, the cache is valid if the stored mtime matches.
        """
        path_cache = self.user_cache.get(path)

        if path.endswith('.egg'):
            # Egg paths include a version number, and there may be many of
            # them, so if we've got the path in the cache, trust it without
            # checking the mtime.
            if path_cache is not None:
                return deepcopy(path_cache)
            return self.entrypoints_from_egg(path)

        try:
            path_st = os.stat(path)
        except OSError as e:
            if e.errno != errno.ENOENT:
                raise
            return {'mtime': -1, 'isdir': False, 'distributions': []}

        isdir = stat.S_ISDIR(path_st.st_mode)
        # If the cache is up to date, return that
        if path_cache and (path_st.st_mtime == path_cache['mtime']) \
                and (isdir == path_cache['isdir']):
            return path_cache
        elif isdir:
            return self.entrypoints_from_dir(path, path_st)
        elif zipfile.is_zipfile(path):
            return self.entrypoints_from_zip(path, path_st)

    def entrypoints_from_egg(self, path):
        """Get the entrypoints from a .egg path (directory or zip file)

        This does not use the cache.
        """
        path_st = os.stat(path)
        isdir = stat.S_ISDIR(path_st.st_mode)
        egg_name = osp.basename(path)
        if '-' in egg_name:
            name, version = egg_name.split('-')[:2]
        else:
            name = version = None

        entrypoints = []

        if isdir:
            ep_path = osp.join(path, 'EGG-INFO', 'entry_points.txt')
            if osp.isfile(ep_path):
                cp = CaseSensitiveConfigParser()
                cp.read(ep_path)
                entrypoints = entrypoints_from_configparser(cp)

        elif zipfile.is_zipfile(path):
            z = zipfile.ZipFile(path)
            try:
                info = z.getinfo('EGG-INFO/entry_points.txt')
            except KeyError:
                return None
            cp = CaseSensitiveConfigParser()
            with z.open(info) as f:
                fu = io.TextIOWrapper(f)
                cp.read_file(fu,
                             source=osp.join(path, 'EGG-INFO',
                                             'entry_points.txt'))
                entrypoints = entrypoints_from_configparser(cp)

        return {
            'mtime': path_st.st_mtime,
            'isdir': isdir,
            'distributions': [{
                'name': name,
                'version': version,
                'entrypoints': entrypoints
            }],
        }

    def entrypoints_from_dir(self, path, path_st):
        """Get the entrypoints from a non-egg directory.

        This does not use the cache.
        """
        distributions = []
        for path in itertools.chain(
                glob.iglob(osp.join(path, '*.dist-info', 'entry_points.txt')),
                glob.iglob(osp.join(path, '*.egg-info', 'entry_points.txt'))
        ):
            distro_name_version = osp.splitext(osp.basename(osp.dirname(path)))[0]
            if '-' in distro_name_version:
                name, version = distro_name_version.split('-', 1)
            else:
                name = version = None

            distro = {
                'name': name, 'version': version,
                'entrypoints': []
            }
            distributions.append(distro)

            cp = CaseSensitiveConfigParser()
            cp.read(path)
            distro['entrypoints'] = entrypoints_from_configparser(cp)

        distributions.sort(key=lambda d: "%s-%s" % (d['name'], d['version']))

        return {
            'mtime': path_st.st_mtime,
            'isdir': True,
            'distributions': distributions,
        }

    def entrypoints_from_zip(self, path, path_st):
        """Get the entrypoints from a non-egg zip file.

        This does not use the cache.
        """
        z = zipfile.ZipFile(path)
        distributions = []
        for info in z.infolist():
            if not z.filename.endswith(('.dist-info/entry_points.txt',
                                        '.egg-info/entry_points.txt')):
                continue
            if z.filename.count('/') > 1:
                continue  # In a subdirectory

            distro_name_version = z.filename.split('/')[0].rsplit('.', 1)[0]
            if '-' in distro_name_version:
                name, version = distro_name_version.split('-', 1)
            else:
                name, version = None, None

            distro = {
                'name': name, 'version': version,
                'entrypoints': []
            }
            distributions.append(distro)

            cp = CaseSensitiveConfigParser()
            with z.open(info) as f:
                fu = io.TextIOWrapper(f)
                cp.read_file(fu, source=osp.join(path, z.filename))
            distro['entrypoints'] = entrypoints_from_configparser(cp)

        return {
            'mtime': path_st.st_mtime,
            'isdir': True,
            'distributions': distributions,
        }

def get_group_all(group, path=None):
    """Find all entry points in a group.

    Returns a list of :class:`EntryPoint` objects.
    """
    result = []
    for location_ep in EntryPointsScanner().scan(path):
        for distro in location_ep['distributions']:
            distro_obj = Distribution(distro['name'], distro['version'])
            for epinfo in distro['entrypoints']:
                if epinfo['group'] != group:
                    continue
                result.append(EntryPoint(
                    epinfo['name'], epinfo['module_name'], epinfo['object_name'],
                    distro=distro_obj
                ))

    return result

if __name__ == '__main__':
    for ep in get_group_all('console_scripts'):
        print(ep)
