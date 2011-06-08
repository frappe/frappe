Creating A Form (DocType)
=========================

In wnframework, a Form is a :term:`DocType`. A DocType represents the description of a form with its
fields, permissions and associated logic. Every entity in the system that has to be saved is a DocType.
DocTypes can be created and maintained like any other entity in the system via the front end.

Let us assume we want to create a Form (DocType) for a Contact table with name, address, phone and email.

   #. Create a new DocType via "New" on the top toolbar
   #. In the "Permissions" tab, add a row. Enter the role (for example "All") in the roles cell and
      check the columns for "Read", "Write" and "Create"
   #. In the "Field" tab, add fields in each row. For each row enter the field "Label" and the "Type"
      For discussion on field types, see 
   #. "Save" the DocType, it will ask you for a name, for our example, you can call it "Contact"
   #. To check how your form looks, you can click on "Tools" -> "Clear Cache" and refresh the page (or open in a new tab)
      Click on "New" and you should find your newly created DocType in the list if you have given it correct
      permissions.
   #. Give it a naming system. See discussion below on what options are there to name DocTypes

Database Table
--------------

When you save a DocType, a correspoinding table gets created in your database, this table has a name
"tab" + the name of the DocType. This means that if you create a Contact DocType, it becomes
tabContact.

.. _naming:

Naming DocTypes
---------------

DocTypes can be named in 3 ways

   #. By a field. To name a DocType by a field, just set "field:" + the field name in the *Autoname* field
      For Example, you can use **field:email** if you want to keep the name (ID) of that record as the email id
   #. By a numbering series. Add the prefix in the *Autoname* field followed by hashes (#) for the number
      of digits. For example **CID.#####** will name your records as CID00001, CID00002 and so on.
      See the rules below:

         **Numbering rules:**
      
            * The key is separated by '.'
            * '####' represents a series. The string before this part becomes the prefix:
              Example: ABC.#### creates a series ABC0001, ABC0002 etc
            * 'MM' represents the current month
            * 'YY' and 'YYYY' represent the current year
   
         *Example:*
   
            * DE/./.YY./.MM./.##### will create a series like
              DE/09/01/0001 where 09 is the year, 01 is the month and 0001 is the series
              
   #. By declaring the "autoname" method in the server code, you can set any naming scheme you like.

Giving Permissions
------------------

Permissions can be set by defining them in the Permissions tab. There are 6 types of permissions

   +------------+----------------------------------------------------+
   |Permission  | Meaning                                            |
   +============+====================================================+
   | Read       | Allows the role to read the record                 |
   +------------+----------------------------------------------------+
   | Write      | Allows the role to edit the record                 |
   +------------+----------------------------------------------------+
   | Create     | Allows the role to create a new record of the      |
   |            | DocType                                            |
   +------------+----------------------------------------------------+
   | Submit     | Allows the role to submit a saved record so that it|
   |            | becomes permanant (read about Save-Submit)         |
   +------------+----------------------------------------------------+
   | Cancel     | Allows the role to cancel a submitted record       |
   +------------+----------------------------------------------------+
   | Amend      | Allows the role to amend a cancelled record        |
   +------------+----------------------------------------------------+
   
You can add multiple permission rules by adding to the table.

**Using match**

You can add an additional key to the permissions by setting the "match" property.

Suppose your users are divided into four groups, and you want to restrict each user to only read records
belonging to that group. To do this:

  #. In your record you must have a "group" (or any such) field to identify which group 
     this record belongs.
  #. In your Profile, or Role default table, you must add a row with key "group" (or the field name)
     and a value for that field.

So when the property of the record **matches** the default of the user, the permission rule kicks in.

Setting Fields
--------------

You can add properties to the DocType by adding them in the field table. The field table has two major
classes, data fields and UI fields.

Data fields hold data have corresponding columns in the database, UI fields are place holders or identify
Section / Column breaks.

.. note::
   You must only specify the "Label". the Field Name is automatically generated by making all letters
   lowercase and replacing a space ( ) by underscore (_)
   
   The Fieldname value is used in the code and is the column name in the database

List of data field types:

   +------------+--------------------------------------+--------------+
   |Field type  | Meaning                              | Length       |
   +============+======================================+==============+
   | Data       | Simple input box                     | 255          |
   +------------+--------------------------------------+--------------+
   | Int        | Integer                              | 11           |
   +------------+--------------------------------------+--------------+
   | Float      | Float                                | 14,6         |
   +------------+--------------------------------------+--------------+
   | Currency   | Foat with 2 decimals                 | 14,2         |
   +------------+--------------------------------------+--------------+
   | Select     | Drop-down                            | 255          |
   +------------+--------------------------------------+--------------+
   | Link       | Foreign key (link to another record) | 255          |
   +------------+--------------------------------------+--------------+
   | Check      | Checkbox                             | 1            |
   +------------+--------------------------------------+--------------+
   | Text       | Multi-line text box                  | Text         |
   +------------+--------------------------------------+--------------+
   | Small Text | Small multi-line text box            | Text         |
   +------------+--------------------------------------+--------------+
   | Code       | Multi-line text box                  | Text         |
   |            | (with fixed-width font)              |              |
   +------------+--------------------------------------+--------------+
   | Text Editor| Multi-line text box                  | Text         |
   |            | (with WYSIWYG editor)                |              |
   +------------+--------------------------------------+--------------+
   | Blob       | Binary Object                        | BLOB         |
   +------------+--------------------------------------+--------------+

List of UI field types:

   +----------------+--------------------------------------+--------------+
   |Field type      | Meaning                              | Length       |
   +================+======================================+==============+
   | Section Break  | Section Break                        | NA           |
   +----------------+--------------------------------------+--------------+
   | Column Break   | Column Break                         | NA           |
   +----------------+--------------------------------------+--------------+
   | HTML           | Place holder where you can add any   | NA           |
   |                | custom HTML                          |              |
   +----------------+--------------------------------------+--------------+
   | Image          | Displays the first attachment        | NA           |
   +----------------+--------------------------------------+--------------+

Along with the Field Label and Type, there are also many other properties that can be set

  #. **Options:** Options has different meaning for different field types:
        * *Link:* It represents a foriegn key (DocType)
        * *Select:* List of options (each on a new line).
          or "link:" + DocType - if you want populate the list from a DocType
          
          For example: If you have a table "Country" and want the user to select one of already
          create Countries, set "link:Country" in the Options
        * *HTML:* For HTML fields, you can put the HTML code in there that will be displayed near 
          the field
  
  
  #. **Perm Level:** (Integer) permission level. Use this same id to filter permissions while setting
     permission rules. You can use same permlevel for many fields. Default is 0.

  #. **Width:** Width of the field in px (e.g. 200px). For Column Breaks this is in % (e.g. 50%)
  
  #. **Reqd:** Check if the field is mandatory

  #. **Index:** Check if you want to index the database column (Text and BLOB type fields cannot be indexed)
  
  #. **Hidden:** Check if the field is hidden

  #. **Print Hide:** Check if you want to hide the field in Print

  #. **Description:** Description of the field (a "?" sign will appear next to the label to see the field)

  #. **Trigger:** If you want to trigger a client function at the "onchange" event, set it to "Client"
  
  #. **Default:** Set default value of the field. For user id use "__user", for today's date, use "__today"


Adding Tables to the form
-------------------------

You can add a "grid" to a form (DocType). This pattern is useful for many standard applications where you have
a many to many relationship. For example in an Invoice, you have a many-to-many relationship between
an "Item" and "Invoice" (like one Invoice can have multiple Items and one Item can be in multiple Invoices)

The Grid pattern is also useful as it makes for a very intuitive form layout.

   #. To add a table to a form, create another DocType for the table record. In our earlier example,
      you can create an Invoice DocType and an "Invoice Detail" DocType.
      
   #. In the **child** DocType (Invoice Detail), check the "Is Table" property in the first tab of the DocType
   
   #. In the **parent** DocType (Invoice), add a field of type "Table" and in the Options, set the child DocType.

.. note::

   **Note 1: How is the parent identified**

   For all child DocTypes, there are extra (hidden) properties set. These help identify the "parent" of the
   record. These values are:

      * **parent**: ID (name) of the parent record
      * **parenttype**: DocType of the parent
      * **parentfield**: Field name in the parent that defines the link to the record

.. note::

   **Note 2: How is the sequence maintained**

   This sequence of the child records under a parent is maintained by another hidden property called "idx"
   
.. _singleton:

Single DocTypes (Singleton pattern)
-----------------------------------
      
   * Single DocTypes help you maintain a library of user classes and global variables.
   
   * There is no table associated with Single DocTypes
   
   * All values of of the Single record are maintained in one table "tabSingles"
   
"Control Panel" is an example of a Single DocType

.. _attachments:

Adding Attachments
------------------

You can allow attachments to be added to records. All attachments are stored in a separate table called "File Data"

To setup attachments

  #. Check Allow Attach
  
  #. Create a hidden field called "file_list" of type Text (this is where a log of all attachment is maintained)
  
**Note: Attachments are always addded at the end of the form, irrespective of where you add the file_list field**

Other Properties
----------------

There are many other properties you can set in a DocType. These are

   #. Autoname: Naming pattern of the record. See :ref:`naming`

   #. Namecase: Set if you want the ID to be in a particular case (UPPER, lower or Title)
   
   #. Is Table: Check if the DocType represents a table (you do not need to set autoname then)
   
   #. In Dialog: Form opens in a Dialog (overlay)
   
   #. Is Single: Singleton pattern See :ref:`singleton`
   
   #. Show Print First: Show a simple "Print" layout first
   
   #. Hide Options: Various hide options to hide Heading, Copy, Email, Toolbar etc
   
   #. Allow Attach: Allow user to add attachments. See :ref:`attachments`