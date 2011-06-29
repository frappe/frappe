:mod:`doctype` --- DocType
==========================

.. module:: doctype
   :synopsis: DocType module

_DocType object
---------------------

.. method:: get(dt)

   returns a :term:`doclist` of :term:`DocType`, `dt`

.. class:: _DocType(name)
   
   The _DocType object is created internally using the module's `get` method.
      
   .. attribute:: name
   
      name of the doctype
      
   .. method:: is_modified()
   
      returns 3 objects:
      
      * last modified date of the `DocType`
      * whether the doctypes is modified after it was cached
      * last modified date of the `DocType` from the cache

   .. method:: get_parent_dt()
   
      return the **first** parent DocType of the current doctype


   .. method:: make_doclist()
   
      returns the :term:`doclist` for consumption by the client
      
      * it cleans up the server code
      * executes all `$import` tags in client code
      * replaces `link:` in the `Select` fields
      * loads all related `Search Criteria`
      * updates the cache
   
.. method:: get()

   execute `Request` to load a `DocType`
   
.. method:: update_doctype(doclist)

   method to be called to update the DocType
   
   * creates field names from labels
   * updates schema
   * saves compiled code
   * marks cache for clearing