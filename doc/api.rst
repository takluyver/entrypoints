entrypoints API
===============

.. module:: entrypoints

High-level API
--------------

.. autofunction:: get_single

.. autofunction:: get_group_named

.. autofunction:: get_group_all

These functions will all use ``sys.path`` by default if you don't specify the
*path* parameter. This is normally what you want, so you shouldn't need to
pass *path*.

EntryPoint objects
------------------

.. autoclass:: EntryPoint

   .. attribute:: name

      The name identifying this entry point

   .. attribute:: module_name

      The name of an importable module to which it refers

   .. attribute:: object_name

      The dotted object name within the module, or *None* if the entry point
      refers to a module itself.

   .. attribute:: extras

      Extra setuptools features related to this entry point as a list, or *None*

   .. attribute:: distro

      The distribution which advertised this entry point -
      a :class:`Distribution` instance or None

   .. automethod:: load

   .. automethod:: from_string

.. autoclass:: Distribution

   .. attribute:: name

      The name of this distribution

   .. attribute:: version

      The version of this distribution, as a string

Exceptions
----------

.. autoexception:: BadEntryPoint

.. autoexception:: NoSuchEntryPoint
