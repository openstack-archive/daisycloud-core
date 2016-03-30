===================
daisy-cache-pruner
===================

-------------------
daisy cache pruner
-------------------

:Author: daisy@lists.launchpad.net
:Date:   2014-01-16
:Copyright: OpenStack LLC
:Version: 2014.1
:Manual section: 1
:Manual group: cloud computing

SYNOPSIS
========

  daisy-cache-pruner [options]

DESCRIPTION
===========

Prunes images from the daisy cache when the space exceeds the value
set in the image_cache_max_size configuration option. This is meant
to be run as a periodic task, perhaps every half-hour.

OPTIONS
========

  **General options**

  .. include:: general_options.rst

FILES
=====

  **/etc/daisy/daisy-cache.conf**
        Default configuration file for the daisy Cache

  .. include:: footer.rst
