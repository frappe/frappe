:mod:`webservice` --- Remote Framework Access via HTTP
======================================================

.. module:: webservice
   :synopsis: Class for Remote Framework Access via HTTP

Framework Server Class
----------------------

..class:: FrameworkServer(remote_host, path, user='', password='', account='', cookies={}, opts={}, https = 0)

   Connect to a remote server via HTTP (webservice).
   
   * `remote_host` is the the address of the remote server
   * `path` is the path of the Framework (excluding index.cgi)

   .. method:: http_get_response(method, args)
   
      Run a method on the remote server, with the given arguments
      
   .. method:: runserverobj(doctype, docname, method, arg='')

      Returns the response of a remote method called on a system object specified by `doctype` and `docname`

Example
-------

Connect to a remote server a run a method `update_login` on `Login Control` on a remote server::

   # connect to a remote server
   remote = FrameworkServer('s2.iwebnote.com', '/v170', 'testuser', 'testpwd', 'testaccount')
   
   # update the login on a remote server
   response = remote.runserverobj('Login Control', 'Login Control', 'update_login', session['user'])