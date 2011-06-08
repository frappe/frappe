:mod:`db` --- Database
======================

.. module:: db
   :synopsis: Database Module

database object --- conn
------------------------

.. class:: Database(host='', user='', password='', use_default = 0):

   Open a database connection with the given parmeters, if use_default is True, use the
   login details from `defs.py`. This is called by the request handler and is accessible using
   the `conn` global variable. the `sql` method is also global to run queries
   
   .. attribute:: host
   
      Database host or 'localhost'
      
   .. attribute:: user
   
      Database user
      
   .. attribute:: password
   
      Database password - cleared after connection is made
      
   .. attribute:: is_testing
   
      1 if session is in `Testing Mode` else 0

   .. attribute:: in_transaction
   
      1 if connection is in a Transaction else 0

   .. attribute:: testing_tables
   
      list of tables, tables with `tab` + doctype

   .. method:: connect()
   
      Connect to a database
	
   .. method:: use(db_name)
   
      `USE` db_name
   
   .. method:: set_db(account)
   
      Switch to database of given `account`
   
   .. method:: check_transaction_status(query)
   
      Update *in_transaction* and check if "START TRANSACTION" is not called twice

   .. method:: fetch_as_dict()
   
      Internal - get results as dictionary
	
   .. method:: sql(query, values=(), as_dict = 0, as_list = 0, allow_testing = 1)
   
      * Execute a `query`, with given `values`
      * returns as a dictionary if as_dict = 1
      * returns as a list of lists (with cleaned up dates and decimals) if as_list = 1
   
   .. method:: convert_to_lists(res)
   
      Convert the given result set to a list of lists (with cleaned up dates and decimals)
   
   .. method:: replace_tab_by_test(query)
   
      Relace all ``tab`` + doctype to ``test`` + doctype

   .. method:: get_testing_tables()
   
      Get list of all tables for which `tab` is to be replaced by `test` before a query is executed

   .. method:: get_value(doctype, docname, fieldname)
   
      Get a single value from a record.

      For Single records, let docname be = None

   .. method:: get_description()
   
      Get metadata of the last query
      
   .. method:: field_exists(dt, fn)
   
      Returns True if `fn` exists in `DocType` `dt`

   .. method:: exists(dt, dn)
   
      Returns true if the record exists

   .. method:: close()
   
      Close my connection
