"""Discover and load entry points from installed packages."""
# Copyright (c) Thomas Kluyver and contributors
# Distributed under the terms of the MIT license; see LICENSE file.

from contextlib import contextmanager
from importlib import import_module
import re
import warnings

from .reader import entry_point_pattern, iter_all_epinfo

__version__ = '0.2.3'

class BadEntryPoint(Exception):
    """Raised when an entry point can't be parsed.
    """
    def __init__(self, epstr):
        self.epstr = epstr

    def __str__(self):
        return "Couldn't parse entry point spec: %r" % self.epstr

    @staticmethod
    @contextmanager
    def err_to_warnings():
        try:
            yield
        except BadEntryPoint as e:
            warnings.warn(str(e))

class NoSuchEntryPoint(Exception):
    """Raised by :func:`get_single` when no matching entry point is found."""
    def __init__(self, group, name):
        self.group = group
        self.name = name

    def __str__(self):
        return "No {!r} entry point found in group {!r}".format(self.name, self.group)


class EntryPoint(object):
    def __init__(self, name, module_name, object_name, extras=None, distro=None):
        self.name = name
        self.module_name = module_name
        self.object_name = object_name
        self.extras = extras
        self.distro = distro

    def __repr__(self):
        return "EntryPoint(%r, %r, %r, %r)" % \
            (self.name, self.module_name, self.object_name, self.distro)

    def load(self):
        """Load the object to which this entry point refers.
        """
        mod = import_module(self.module_name)
        obj = mod
        if self.object_name:
            for attr in self.object_name.split('.'):
                obj = getattr(obj, attr)
        return obj
    
    @classmethod
    def from_string(cls, epstr, name, distro=None):
        """Parse an entry point from the syntax in entry_points.txt

        :param str epstr: The entry point string (not including 'name =')
        :param str name: The name of this entry point
        :param Distribution distro: The distribution in which the entry point was found
        :rtype: EntryPoint
        :raises BadEntryPoint: if *epstr* can't be parsed as an entry point.
        """
        m = entry_point_pattern.match(epstr)
        if m:
            mod, obj, extras = m.group('modulename', 'objectname', 'extras')
            if extras is not None:
                extras = re.split(',\s*', extras)
            return cls(name, mod, obj, extras, distro)
        else:
            raise BadEntryPoint(epstr)

class Distribution(object):
    def __init__(self, name, version):
        self.name = name
        self.version = version
    
    def __repr__(self):
        return "Distribution(%r, %r)" % (self.name, self.version)


def get_single(group, name, path=None, cache_file=None):
    """Find a single entry point.

    Returns an :class:`EntryPoint` object, or raises :exc:`NoSuchEntryPoint`
    if no match is found.
    """
    for distro, epinfo in iter_all_epinfo(path=path, cache_file=cache_file):
        if epinfo['group'] == group and epinfo['name'] == name:
            distro_obj = Distribution(distro['name'], distro['version'])
            return EntryPoint(
                epinfo['name'], epinfo['module_name'], epinfo['object_name'],
                extras=epinfo['extras'], distro=distro_obj
            )

    raise NoSuchEntryPoint(group, name)

def get_group_named(group, path=None, cache_file=None):
    """Find a group of entry points with unique names.

    Returns a dictionary of names to :class:`EntryPoint` objects.
    """
    result = {}
    for ep in get_group_all(group, path=path, cache_file=cache_file):
        if ep.name not in result:
            result[ep.name] = ep
    return result

def get_group_all(group, path=None, cache_file=None):
    """Find all entry points in a group.

    Returns a list of :class:`EntryPoint` objects.
    """
    result = []
    for distro, epinfo in iter_all_epinfo(path=path, cache_file=cache_file):
        if epinfo['group'] != group:
            continue
        distro_obj = Distribution(distro['name'], distro['version'])
        result.append(EntryPoint(
            epinfo['name'], epinfo['module_name'], epinfo['object_name'],
            extras=epinfo['extras'], distro=distro_obj
        ))
    return result

