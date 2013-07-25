INSTALL.txt
===========

Web Notes Framework Installation guide


WNF requires the following applications

1. Python
2. MySQL
3. MySQL-Python (connector)  
4. simplejson (for Python 2.4 or lower)
5. email (for Python 2.4 or lower)
6. pytz (easy_install pytz)
7. Apache
8. PIL (optional - for image processing (thumbnails etc) 
	- yum install libjpeg-devel
	- yum install python-imaging
	)

------------------------------------------------------------------------
1. Create a databse instance for your application

   Call the install script with the following options. For more options use -h
   
   python [folder]/cgi-bin/webnotes/install_lib/install.py MYSQL_ROOT_LOGIN MYSQL_ROOT_PASSWORD DBNAME

------------------------------------------------------------------------
2. Setup defs.py

   The framework picks up the database details from py/webnotes/defs.py
   
   You need to edit this file and set your database name and other options
   
------------------------------------------------------------------------
3. Configuring Apache

see conf/apache.conf
	
------------------------------------------------------------------------
4. Login to application

Start Apache, go to your web-browser and point to the folder where you installed the framework

The default logins are:

login: Administrator
password: admin

------------------------------------------------------------------------

Step by step instructions on CentOS/Fedora:
	0.Check out the source code.
	Modify the v170/cgi-bin/webnotes/defs file to your required settings and rename it to defs.py 

	$ yum install mysql
	$ yum install httpd
	$ yum install MySQL-python
	$ yum install python-setuptools
	$ easy_install pytz
	$ easy_install email
	$ easy_install simplejson suds
	$ easy_install pygeoip (optional for geo ip)
	$ yum install libjpeg-devel (optional)
	$ yum install python-imaging (optional)

	- Edit /etc/httpd/conf/httpd.conf and add the options as mentioned above.	
	- from the trunk/v170/cgi-bin folder run python webnotes/install_lib/install.py install



