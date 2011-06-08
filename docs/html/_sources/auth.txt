:mod:`auth` --- Authentication
==============================

.. module:: auth
   :synopsis: Authentication module

Authentication object
---------------------

.. class:: Authentication(self, form, in_cookies, out_cookies, out)
   
   A new Authenticate object is created at the beginning of any request. It will manage login, session and
   cookies. :method:`update` must be called at the end of the request to update cookies and
   session.
   
   The constructor will also set the global `webnotes.conn`, `webnotes.session` and `webnotes.user`
   
   To enable a login, the :object:form must have a cmd = "login" (see request handling for more details)
   
   .. attribute:: conn
   
      `webnotes.db.Database` object created after authentication
      
   .. attribute:: session
   
      session dictionary of the current session

   .. attribute:: cookies
   
      session dictionary of incoming cookies

   .. attribute:: domain
   
      domain name of the request
      
   .. attribute:: remote_ip
   
      IP address of the reqeust
      
   .. method:: update()
   
      **Must be called at the end of the request, to update the session and clear expired sessions**
         
   .. method:: set_env()
   
   	  Sets the properties `domain` and `remote_ip` from the environmental variables 
   	  
   .. method:: set_db()
   
      In case of a multi-database system, this methods sets the correct database connection.
      
      * It will first search for cookie `account_id`
      * It will next search for cookies or form variable `__account`
      * It will try and search from the domain mapping table `Account Domain` in the `accounts` database
      * It will try and use the default
   
   .. method:: check_ip()
   
      If the current request is from a separate IP than the one which was used to create the session, then 
      this throws an Exception
      
   .. method:: load_session(sid)
   
      Load session from the given session id `sid`
      
   .. method:: login(as_guest = 0)
   
      Will login user from `self.form`. If as_guest is true, it will check if Guest profile is enabled
      
      It will also: 
      
      * validate if approved ips are set in `Profile`
      * start the session
      * set "remember me"
      * return out.message as "Logged In"
      
   .. method:: check_password(user, pwd)
   
      Checks if the user has the pwd and is enabled
      
   .. method:: validate_ip(user)
   
      Validates IP address from the ip_address value in the user's `Profile`

   .. method:: start_session()
   
      Starts a session, and updates last login details in the users's `Profile`
      
   .. method:: clear_expired()
   
      Removes old sessions from `tabSessions` that are older than `session_expiry` in `Control Panel` or 24:00 hrs

   .. method:: set_cookies()
   
      Sets outgoing cookies
   
   .. method:: set_remember_me()
   
      Checks if there is a 'remember_me' property in `form` with a value and if true, its sets the
      expiry of each cookie for `remember_for_days` in `Control Panel` or 7 days

   .. method:: get_cookies()
   
      Loads incoming cookies in `cookies`
