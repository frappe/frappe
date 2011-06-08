:mod:`utils` --- Utilities Module
=================================

.. module:: utils
   :synopsis: Utility functions

Date and Time Functions
-----------------------

.. data:: user_format

   User format specified in :term:`Control Panel`
   
   Examples:
   
   * dd-mm-yyyy
   * mm-dd-yyyy
   * dd/mm/yyyy
   
.. function:: getdate(string_date)

   Coverts string date (yyyy-mm-dd) to datetime.date object

.. function:: add_days(string_date, days)

   Adds `days` to the given `string_date`

.. function:: now()

   Returns `time.strftime('%Y-%m-%d %H:%M:%S')`
	
.. function:: nowdate()

   Returns time.strftime('%Y-%m-%d')

.. function:: get_first_day(date, d_years=0, d_months=0)

   Returns the first day of the month for the date specified by date object
   Also adds `d_years` and `d_months` if specified


.. function:: get_last_day(dt)

   Returns last day of the month using:
   `get_first_day(dt, 0, 1) + datetime.timedelta(-1)`

.. function:: formatdate(dt)

   Convers the given string date to :data:`user_format`


Datatype Conversions
--------------------

.. function:: dict_to_str(args, sep='&')

   Converts a dictionary to URL

.. function:: isNull(v)

   Returns true if v='' or v is `None`

.. function:: has_common(l1, l2)

   Returns true if there are common elements in lists l1 and l2

.. function:: flt(s)

   Convert to float (ignore commas)

.. function:: cint(s)

   Convert to integer

.. function:: cstr(s)

   Convert to string
		
.. function:: str_esc_quote(s)

   Escape quotes

.. function:: replace_newlines(s)

   Replace newlines by '<br>'

.. function:: parse_val(v)

   Converts to simple datatypes from SQL query results
   
.. function:: fmt_money(amount, fmt = '%.2f')

   Convert to string with commas for thousands, millions etc
	
Defaults
--------

.. function:: get_defaults()

   Get dictionary of default values from the :term:`Control Panel`

.. function:: set_default(key, val)

   Set / add a default value to :term:`Control Panel`


File (BLOB) Functions
---------------------

.. function:: get_file(fname)

   Returns result set of ((fieldname, blobcontent, lastmodified),) for a file of name or id `fname`


Email Functions
---------------

.. function:: validate_email_add(email_str)

   Validates the email string
   
.. function:: sendmail(recipients, sender='', msg='', subject='[No Subject]', parts=[], cc=[], attach=[])

   Send an email. For more details see :func:`email_lib.sendmail`

Other Functions
---------------

.. function:: getCSVelement(v)

   Returns the CSV value of `v`, For example: 
   
   * apple becomes "apple"
   * hi"there becomes "hi""there"

.. function:: generate_hash()

   Generates reandom hash for session id

.. function:: getTraceback()

   Returns the traceback of the Exception
