Web Notes Framework
===================

Why Web Notes Framework?
------------------------

This question was not relevant in 2005 when the Framework started being developed, now however,
there are many popular frameworks beginning with Ruby on Rails, Django, GWT etc. Does it make sense to look
at yet another framework? We think yes, here are a few reasons:

* It is a pure meta-data framework, not based on templates that most frameworks support, taking automation
  the next level
* It has back-end and front-end integrated with built-in AJAX
* It has more features out-of-the box than any other framework
* It is extremely light weight and runs on Apache-CGI

See it in action
----------------

Go to http://wnframework.org for more info

Setting Up and Installing
-------------------------

   #. Pre-requisites

      #. Python
      #. MySQL
      #. MySQL-Python

   #. Setting Up Apache

      Changes to httpd.conf to enable execution of CGI files from anywhere

      #. Add ExecCGI to Options directive
      #. Uncomment AddHandler for ExecCGI
      #. Add (to block python files from being directly viewed)::
      
            RewriteEngine on
            RewriteRule \.py - [F]
 
   #. Setting Up Framework

      #. Download the framework to your "www" folder::

            svn checkout http://wnframework.googlecode.com/svn/trunk/v170/

      #. Set mysql root login details in: cgi-bin/defs.py
      #. Go to the cgi-bin python create the base account::

            import server
            server.create_account('accounts')

   #. Start the apache webserver and go to your browser:

         localhost/login.html
		
         account: accounts
         login: Administrator
         password: admin
		
   **You are set!**