:mod:`email_lib` --- Email
==========================

.. module:: email_lib
   :synopsis: Email library

Email object
------------

.. class:: Email(self, sender='', recipients=[], subject='')
   
   Wrapper on the email module. Email object represents emails to be sent to the client. 
   Also provides a clean way to add binary `FileData` attachments
      
   .. attribute:: sender
   
      sender's email
      
   .. attribute:: reply_to
   
      [Optional] if reply_to is not same as sender

   .. attribute:: recipients
   
      `list` of recipients or a string separated by comma (,) or semi-colon (;)
   
   .. attribute:: subject
   
      email subject

   .. attribute:: msg
   
      message object `email.mime.multipart.MIMEMultipart`

   .. attribute:: cc
   
      `list` of cc email ids

   .. method:: set_message(message, mime_type='text/html')
   
      append the message with MIME content
		
   .. method:: attach(file_id)

      attach a file from the `FileData` table
	
   .. method:: validate()
   
      validate the email ids

   .. method:: setup()
   
      setup the SMTP (outgoing) server from `Control Panel` or defs.py
	
   .. method:: send()
   
      send the message

.. method:: validate_email_add(email_id)
   
   Validate the email id
   
.. method:: sendmail(recipients, sender='', msg='', subject='[No Subject]', parts=[], cc=[], attach=[])

   Short cut to method to send an email

Example
-------

Email with attachments::

	# get attachments
	al = sql('select file_list from `tab%s` where name="%s"' % (dt, dn))
	if al:
		al = al[0][0].split('\n')
		
	# create the object
	email = server.EMail('test@webnotestech.com', ['a@webnotestech.com', 'b@webnotestech.com'], 'this is a test')

	# add some intro
	email.set_message(replace_newlines('Hi\n\nYou are being sent %s %s\n\nThanks' % dt, dn))
		
	# add attachments
	for a in al:
		email.attach(a.split(',')[0])

	# send
	email.send()  
	
	