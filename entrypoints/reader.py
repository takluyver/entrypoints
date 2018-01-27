from copy import deepcopy
import errno
import glob
import io
import itertools
import json
import logging
import os
import os.path as osp
import re
import stat
import sys
from tempfile import mkstemp
import zipfile

if sys.version_info[0] >= 3:
    import configparser
else:
    from backports import configparser

entry_point_pattern = re.compile(r"""
(?P<modulename>\w+(\.\w+)*)
(:(?P<objectname>\w+(\.\w+)*))?
\s*
(\[(?P<extras>.+)\])?
$
""", re.VERBOSE)

# If a file with this name is in the root of a site-packages directory, or a zip
# file, we won't store entrypoints from there in the cache.
NO_CACHE_MARKER_FILE = '.entrypoints_no_cache'


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
        except IOError as e:
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
            with os.fdopen(fd, 'wb') as f:
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

def locate_cache_file():
    """Return the location of the per-user cache file.

    Uses ENTRYPOINTS_CACHE_FILE environment variable if present.
    This may either be set to a path, or to '0' to disable per-user caching.
    """
    envvar = os.environ.get('ENTRYPOINTS_CACHE_FILE', '')
    if envvar == '0':
        return None
    elif envvar:
        return envvar
    else:
        return osp.join(get_cache_dir(), 'entrypoints.json')


class CaseSensitiveConfigParser(configparser.ConfigParser):
    optionxform = staticmethod(str)

def entrypoints_from_configparser(cp, path):
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
                log.warning("Invalid entry point %r in %s", epstr, path)
    return res


class EntryPointsScanner(object):
    def __init__(self):
        self.cache_file = locate_cache_file()
        self.non_cacheable_paths = set()
        if self.cache_file:
            self.working_cache = read_user_cache(self.cache_file)
        else:
            self.working_cache = {}


    def _abspath_multi(self, paths):
        """Like os.path.abspath(), but avoid calling getcwd multiple times"""
        res = []
        cwd = os.getcwd()
        for path in paths:
            if not osp.isabs(path):
                path = osp.join(cwd, path)
            res.append(osp.normpath(path))
        return res

    def write_user_cache(self):
        """Filter cacheable data, ensure the directory exists, write atomically
        """
        data = {path: eps for (path, eps) in self.working_cache.items()
                if path not in self.non_cacheable_paths}

        directory = osp.dirname(self.cache_file)
        try:
            os.makedirs(directory)
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise
        atomic_json_dump(data, self.cache_file, indent=2, sort_keys=True)

    def scan(self, locations=None):
        """Get entry points from a list of paths (sys.path by default)"""
        if locations is None:
            locations = sys.path
        locations = self._abspath_multi(locations)

        cache_modified = False

        try:
            for path in locations:
                locn_ep = self.entrypoints_for_path(path)
                if locn_ep != self.working_cache.get(path):
                    self.working_cache[path] = locn_ep
                    if path not in self.non_cacheable_paths:
                        cache_modified = True
                yield locn_ep

        finally:
            if cache_modified and self.cache_file:
                self.write_user_cache()

    def rebuild_cache(self, add_locations=None):
        """Rebuild the cache, discard cached data for paths which don't exist"""
        if not self.cache_file:
            raise RuntimeError("Caching is disabled by environment")
        add_locations = self._abspath_multi(add_locations or [])
        locations = set(self.working_cache).union(add_locations)
        self.working_cache = {}
        for path in locations:
            if osp.exists(path):
                self.working_cache[path] = self.entrypoints_for_path(path)

        self.write_user_cache()

    def entrypoints_for_path(self, path):
        """Get the entry points from a given path.

        This does use the cache if it is valid. For .egg paths, any cached
        data is considered valid (since the path includes the version number).
        For other paths, the cache is valid if the stored mtime matches.
        """
        path_cache = self.working_cache.get(path)

        if path.endswith('.egg'):
            # Egg paths include a version number, and there may be many of
            # them, so if we've got the path in the cache, trust it without
            # checking the mtime.
            if path_cache is not None:
                log.debug("Using cached entrypoints for %s", path)
                return deepcopy(path_cache)
            log.debug("Scanning entrypoints for %s", path)
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
            log.debug("Using cached entrypoints for %s", path)
            return path_cache
        elif isdir:
            log.debug("Scanning entrypoints for %s", path)
            return self.entrypoints_from_dir(path, path_st)
        elif zipfile.is_zipfile(path):
            log.debug("Scanning entrypoints for %s", path)
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
            log.warning("Can't get name & version from %s", path)
            name = version = None

        entrypoints = []

        if isdir:
            ep_path = osp.join(path, 'EGG-INFO', 'entry_points.txt')
            if osp.isfile(ep_path):
                cp = CaseSensitiveConfigParser()
                cp.read(ep_path)
                entrypoints = entrypoints_from_configparser(cp, ep_path)

        elif zipfile.is_zipfile(path):
            z = zipfile.ZipFile(path)
            try:
                info = z.getinfo('EGG-INFO/entry_points.txt')
            except KeyError:
                return None
            cp = CaseSensitiveConfigParser()
            ep_path = osp.join(path, 'EGG-INFO', 'entry_points.txt')
            with z.open(info) as f:
                fu = io.TextIOWrapper(f)
                cp.read_file(fu, source=ep_path)
                entrypoints = entrypoints_from_configparser(cp, ep_path)

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
        for ep_path in itertools.chain(
                glob.iglob(osp.join(path, '*.dist-info', 'entry_points.txt')),
                glob.iglob(osp.join(path, '*.egg-info', 'entry_points.txt'))
        ):
            info_dir = osp.dirname(ep_path)
            distro_name_version = osp.splitext(osp.basename(info_dir))[0]
            if '-' in distro_name_version:
                name, version = distro_name_version.split('-', 1)
            else:
                log.warning("Can't get name & version from %s", info_dir)
                name = version = None

            distro = {
                'name': name, 'version': version,
                'entrypoints': []
            }
            distributions.append(distro)

            cp = CaseSensitiveConfigParser()
            cp.read(ep_path)
            distro['entrypoints'] = entrypoints_from_configparser(cp, ep_path)

        distributions.sort(key=lambda d: "%s-%s" % (d['name'], d['version']))

        if os.path.isfile(os.path.join(path, NO_CACHE_MARKER_FILE)):
            self.non_cacheable_paths.add(path)

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
                log.warning("Can't get name & version from %s %s", path, z.filename)
                name, version = None, None

            distro = {
                'name': name, 'version': version,
                'entrypoints': []
            }
            distributions.append(distro)

            cp = CaseSensitiveConfigParser()
            ep_path = osp.join(path, z.filename)
            with z.open(info) as f:
                fu = io.TextIOWrapper(f)
                cp.read_file(fu, source=osp.join(path, z.filename))
            distro['entrypoints'] = entrypoints_from_configparser(cp, ep_path)

        distributions.sort(key=lambda d: "%s-%s" % (d['name'], d['version']))

        if NO_CACHE_MARKER_FILE in z.namelist():
            self.non_cacheable_paths.add(path)

        return {
            'mtime': path_st.st_mtime,
            'isdir': True,
            'distributions': distributions,
        }

def iter_all_epinfo(path=None):
    # Distributions found earlier in path will shadow those with the same name
    # found later. If these distributions used different module names, it may
    # actually be possible to import both, but in most cases this shadowing
    # will be correct. pkg_resources does something similar.
    distro_names_seen = set()

    for location_ep in EntryPointsScanner().scan(path):
        for distro in location_ep['distributions']:
            if distro['name'] in distro_names_seen:
                continue
            distro_names_seen.add(distro['name'])

            for epinfo in distro['entrypoints']:
                yield (distro, epinfo)



if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG)
    for _, epinfo in iter_all_epinfo():
        if epinfo['group'] == 'console_scripts':
            print("{name} = {module_name}:{object_name}".format(**epinfo))
