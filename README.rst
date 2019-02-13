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
<https://packaging.python.org/en/latest/distributing.html#entry-points>`_.

When there are multiple versions of the same distribution in different
directories on ``sys.path``, ``entrypoints`` follows the rule that the first
one wins.  In most cases, this follows the logic of imports.  Similarly,
Entrypoints relies on ``pip`` to ensure that only one ``.dist-info`` or
``.egg-info`` directory exists for each installed package.  There is no reliable
way to pick which of several `.dist-info` folders accurately relates to the
importable modules.
