:mod:`webnotes` --- Webnotes Module
===================================

.. module:: webnotes
   :synopsis: Global objects that are used to generate the HTTP response

Global Attributes
-----------------

.. data:: version

   'v170'

.. data:: conn

   The database connection :class:`webnotes.db.Database` setup by :mod:`auth`

.. data:: form

   The cgi.FieldStorage() object (Dictionary representing the formdata from the URL)

.. data:: session

   Global session dictionary.

   * session['user'] - Current user   
   * session['data'] - Returns a dictionary of the session cache

.. data:: is_testing

   Flag to identify if system is in :term:`Testing Mode`
      
.. data:: add_cookies

   Dictionary of additional cookies appended by custom code

.. data:: response

   The JSON response object. Default is::
   
   {'message':'', 'exc':''}

.. data:: debug_log

   List of exceptions to be shown in the :term:`Error Console`

.. data:: message_log

   List of messages to be shown to the user in a popup box at the end of the request

Global Functions
----------------

.. function:: errprint(msg)

   Append to the :data:`debug log`
   
.. function:: msgprint(msg)

   Append to the :data:`message_log`
