Accessing Local Data
====================

Local records are maintained in the :term:`locals` dictionary. Some useful functions to access local data:

.. function:: LocalDB.add(dt, dn)

   Add a new record to `locals`
   
.. function:: LocalDB.delete_doc(dt, dn)

   Delete a record and all child records from `locals`
   
.. function:: LocalDB.set_default_values(doc)

   Set default values for the given `doc`. Will only work if the metadata (`DocType`) is also loaded
   
.. function:: LocalDB.create(dt, n)

   Create a new record and set default values. If n is null, n is set as "Unsaved .."

.. function:: LocalDB.delete_record(dt, dn)

   Mark for deletion (called when a row is deleted from the table)
   
.. function:: LocalDB.get_default_value(fieldname, fieldtype, default)

   Get default value for the given field details for `default` keyword
   
   * If `default` is '__user' or '_Login' - return username
   * If `default` is 'Today' or '__today' - return today's date
   * Return `default` if `default` is not null.
   * If field name matches user or system default, then return the default

.. function:: LocalDB.add_child(doc, childtype, parentfield)

   Return a child record, with parentfield set (optionally). Called when a row is added to the table
   
.. function:: LocalDB.copy(dt, dn, from_amend)

   Create and return a copy of record specified by `dt` and `dn`. Called by `Copy` and `Amend`
   
.. function:: make_doclist(dt, dn)

   Return the required record and all child records from `locals`.