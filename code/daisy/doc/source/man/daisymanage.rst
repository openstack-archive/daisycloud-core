=============
daisy-manage
=============

-------------------------
daisy Management Utility
-------------------------

:Author: daisy@lists.launchpad.net
:Date:   2014-01-16
:Copyright: OpenStack LLC
:Version: 2014.1
:Manual section: 1
:Manual group: cloud computing

SYNOPSIS
========

  daisy-manage [options]

DESCRIPTION
===========

daisy-manage is a utility for managing and configuring a daisy installation.
One important use of daisy-manage is to setup the database. To do this run::

    daisy-manage db_sync

Note: daisy-manage commands can be run either like this::

    daisy-manage db sync

or with the db commands concatenated, like this::

    daisy-manage db_sync



COMMANDS
========

  **db**
        This is the prefix for the commands below when used with a space
        rather than a _. For example "db version".

  **db_version**
        This will print the current migration level of a daisy database.

  **db_upgrade <VERSION>**
        This will take an existing database and upgrade it to the
        specified VERSION.

  **db_downgrade <VERSION>**
        This will take an existing database and downgrade it to the
        specified VERSION.

  **db_version_control**
        Place the database under migration control.

  **db_sync <VERSION> <CURRENT_VERSION>**
        Place a database under migration control and upgrade, creating
        it first if necessary.

  **db_export_metadefs**
        Export the metadata definitions into json format. By default the
        definitions are exported to /etc/daisy/metadefs directory.

  **db_load_metadefs**
        Load the metadata definitions into daisy database. By default the
        definitions are imported from /etc/daisy/metadefs directory.

  **db_unload_metadefs**
        Unload the metadata definitions. Clears the contents of all the daisy
        db tables including metadef_namespace_resource_types, metadef_tags,
        metadef_objects, metadef_resource_types, metadef_namespaces and
        metadef_properties.

OPTIONS
=======

  **General Options**

  .. include:: general_options.rst

  **--sql_connection=CONN_STRING**
        A proper SQLAlchemy connection string as described
        `here <http://www.sqlalchemy.org/docs/05/reference/sqlalchemy/connections.html?highlight=engine#sqlalchemy.create_engine>`_

  .. include:: footer.rst

CONFIGURATION
=============

The following paths are searched for a ``daisy-manage.conf`` file in the
following order:

* ``~/.daisy``
* ``~/``
* ``/etc/daisy``
* ``/etc``

All options set in ``daisy-manage.conf`` override those set in
``daisy-registry.conf`` and ``daisy-api.conf``.
