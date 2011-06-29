Using the Administrator Interface
=================================

Applications are built using the web based administrator interface of the framework.

Let us start discuss how to build applications using the basic building blocks

What is an Application?
-----------------------

Let us define a typical web application as being a set of:

   #. Users - who use the application
   #. Roles - roles assigned to users for various functions
   #. Pages - where users navigate and see relevant information
   #. Forms - where users enter new data
   #. Reports - where users get a tabulated view of their data
   #. Permission Rules - that define what each role is allowed to do or not do
   #. Logic - Automatic actions that are performed at various events
   #. Validations - Checks that ensure the data entered by the users is valid
   #. Print Formats - Printable documents based on the data users have entered
   #. UI Widgets - Menus, Lists, Dialogs that are used for navigating, entering or displaying information
   #. Module - So that you can group Roles, Forms, Pages, Reports for more complex applications
   
Let us now start building these entities in the wnframework

Administrator Login
-------------------

An application is built via the browser front end. To have the right access to build applications, you must
login as an Administrator.

If you are in a new system that does not have any application, your first login as "Administrator" is the
Administrator login.

Creating Entities
-----------------

To create any entity, you must have the relevant permission. Once you have the relevant permission, you can
create new entities from the top toolbar.

Look out for the "New" button on the top left of the page. Via the "New" dialog box, you can create any 
entity you have rights to create.

.. note::

   * Entities in wnframework are known by their "name". Name has the same concept as id - its a unique key 
     for that entity (same as a Primary Key).
   * Every entity also has an "owner" - By default this is the user who creates that entity.
   
Managing Roles
---------------

Roles are assigned to users so that you can define a group of users and set permission (or other) rules.

   #. To create a new role, click "New" on the top toolbar and select "Role"
   #. Give the Role name, use descriptive names here like - "Contact Manager"
   #. Set the module, (use the standard; if you want create a new module, go ahead!)
   #. Click on the green "Save" button
   
Your new Roles is created! To check, click on the "Search" button on the top toolbar and select "Role"
Click on "Search" and see that your new Role is added to the list of already existing roles:

.. note::

   Pre-defined roles. There are 3 basic roles that are pre-defined in the system. It is suggested,
   you leave them as it is!
   
      #. Administrator: Role given to the application builder / maintainer
      #. All: All logged in users have the role "All"
      #. Guest: Users who are not yet logged in.
      
Creating Users (Profile)
------------------------

A Profile (=user) has a unique identity in the system and can be tagged as an "onwer" to a data record. 
Profiles can also be assigned Roles that restrict what they can do. You can also define custom logic 
for a Profile

To create a new Profile:

   #. Create a new Profile via "New" on the top toolbar
   #. Enter the mandatory "First Name" and "Email" values
   #. "Save" the profile via the "Save" button
   #. The user will be sent an email with her random-genereated password. You can also set a custom password
      by clicking on the "Password" tab and setting the password.
   #. *To assign a role, click on the "Roles" tab and add a "Role" in the table.*
      
Once a Profile is created, the user can login with the login id (email) and password.
      
.. note::
   
   Profiles are given an id that is the same as their email id. Why did we do this?
   
      * Email Ids are good unique identifiers. Your users may have the same first and last names,
        but they would have separate Email Ids
      * People usually remember their email ids
      * Email Ids are these days the de-facto way to define login-ids
