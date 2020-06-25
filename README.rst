Entry points are a way for Python packages to advertise objects with some
common interface. The most common examples are ``console_scripts`` entry points,
which define shell commands by identifying a Python function to run.

*Groups* of entry points, such as ``console_scripts``, point to objects with
similar interfaces. An application might use a group to find its plugins, or
multiple groups if it has different kinds of plugins.

The **entrypoints** module contains functions to find and load entry points.
You can install it from PyPI with ``pip install entrypoints``.

To advertise entry points when distributing a package, see
`entry_points in the Python Packaging User Guide
<https://packaging.python.org/guides/distributing-packages-using-setuptools/#entry-points>`_.

The ``importlib.metadata` module distributed with ``Python``
provides the preferred way to discover entrypoints `<https://docs.python.org/3/library/importlib.metadata.html#entry-points>_.

The ``pkg_resources`` module distributed with ``setuptools`` provides a way to
discover entrypoints as well, but it contains other functionality unrelated to
entrypoint discovery, and it does a lot of work at import time.  Merely
*importing* ``pkg_resources`` causes it to scan the files of all installed
packages. Thus, in environments where a large number of packages are installed,
importing ``pkg_resources`` can be very slow (several seconds).

By contrast, ``entrypoints`` is focused solely on entrypoint discovery and it
is faster. Importing ``entrypoints`` does not scan anything, and getting a
given entrypoint group performs a more focused scan.
