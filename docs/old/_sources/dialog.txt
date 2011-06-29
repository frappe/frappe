Dialog Boxes
============

This document outlines the basic API of the Dialog widget. Dialog boxes are DIV Elements with a border
and are placed at a higher z-index. There is also a basic Form API within the Dialog boxes

Dialog Class
------------

.. class:: Dialog(w, h, title, content)

   To create a basic Dialog box, specify its width, height and title. Optionally, `content` is a list of 
   form input widgets. For more info, see `make_body`

   .. attribute:: wrapper
   
      Enclosing outer DIV element

   .. attribute:: head
   
      Element containing the head of the Dialog which contains the title and close btn

   .. attribute:: body

      Element containing the body of the Dialog
      
   .. attribute:: widgets
   
      Dictionary containing the form widgets. These can be accessed by their labels
      
   .. method:: make_body(content)
   
      content is the list of form input widgets that are to be created. The structure of the `content`
      list is a list-in-a-list.
      
      Field widget types are:
      
      * HTML
      * Check
      * Data
      * Select
      * Password
      * Text
      * Button
      
      The widgets are declared as [`type`, `label`, `comment or HTML content`]
      
   .. method:: show()
   
      Show the Dialog
      
   .. method:: hide()
   
      Hide the Dialog
   
   .. method:: set_title(t)
   
      Set the Dialog title
      
   .. method:: no_cancel()
   
      Stop the user from cancelling the Dialog. (The closing of this Dialog must be scripted)
        
Example
-------

Example showing creation of a Email Dialog::
      
   var d = new Dialog(440, 440, "Send Email");
         
   d.make_body([
     ['Data','To','Example: abc@hotmail.com, xyz@yahoo.com']
     ,['Select','Format']
     ,['Data','Subject']
     ,['Data','From','Optional']
     ,['Check','Send With Attachments','Will send all attached documents (if any)']
     ,['Text','Message']
     ,['Button','Send',email_go]]
   );
   
   // Reference to a form widget
   var emailfrom = d.widgets['From'].value;
   
   // show the dialog
   d.show()
   