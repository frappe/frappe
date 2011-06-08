Database API Functions
----------------------

Common Database functions. These are a part of the :mod:`db` Module and reproduced here because these are
global and used in API

.. function:: sql(query, values=(), as_dict = 0, as_list = 0, allow_testing = 1)
  
   * Execute a `query`, with given `values`
   * returns as a dictionary if as_dict = 1
   * returns as a list of lists (with cleaned up dates and decimals) if as_list = 1

.. function:: convert_to_lists(res)
   
   Convert the given result set to a list of lists (with cleaned up dates and decimals)
   
.. function:: get_value(dt, dn, fieldname)

   Return the value of the given field in the given record. For Single Type, set dn = None
   
.. function:: set(doc, field, val)

   Set a field value in the :class:`doc.Document` and upate it in the Database.