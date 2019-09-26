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

The ``pkg_resources`` module distributed with ``setuptools`` provides a way to
discover entrypoints as well, but merely *importing* ``pkg_resources`` causes
every package installed with ``setuptools`` to be imported. Illustration:

.. code:: python

   >>> import sys
   >>> len(sys.modules)
   67
   >>> import pkg_resources
   >>> len(sys.modules)  # result scales with number of installed packages
   174

By contrast, importing ``entrypoints`` does not scan every installed package;
it just imports its own dependencies.

.. code:: python

   >>> import sys
   >>> len(sys.modules)
   67
   >>> import entrypoints
   >>> len(sys.modules)  # result is fixed
   97

Further, discovering an entry point does not cause anything to be imported.

.. code:: python

   >>> eps = entrypoints.get_group_named('some_group')
   >>> len(sys.modules)  # same result as above
   97

Only upon *loading* the entrypoints are relevant packages imported.
