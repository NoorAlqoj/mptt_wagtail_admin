mptt_wagtail
============
An integration to gain DraggableMPTTAdmin features in wagtail admin

Installation
------------

.. code:: sh

   $ pip install mptt-wagtail

Usage
-----

1. Add ``mptt_wagtail`` to your ``INSTALLED_APPS``.
2. In your ``admin.py`` file, use ``WagtailDraggableMPTTAdmin``` to add drag and drop behaviour to your ModelAdmin 

.. code:: python
   
   from mptt_wagtail.admin import WagtailDraggableMPTTAdmin

   class YourModelAdmin(WagtailDraggableMPTTAdmin):
       model = YourModel