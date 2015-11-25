# DocType

After creating the Roles, let us create the **DocTypes**

To create a new **DocType**, go to:

> Core > Documents > Doctype > New

<img class="screenshot" alt="New Doctype" src="{{url_prefix}}/assets/img/doctype_new.png">

In the DocType, first the Module, which in our case is **Library Managment**

#### Adding Fields

In the Fields Table, you can add the fields (properties) of the DocType (Article).

Fields are much more than database columns, they can be:

1. Columns in the database
1. For Layout (section / column breaks)
1. Child tables (Table type field)
1. HTML
1. Actions (button)
1. Attachments or Images

Let us add the fields of the Article.

<img class="screenshot" alt="Adding Fields" src="{{url_prefix}}/assets/img/doctype_adding_field.png">

When you add fields, you need to enter the **Type**. **Label** is optional for Section Break and Column Break. **Name** (`fieldname`) is the name of the database table column and also the property of the controller. This has to be *code friendly*, i.e. it has to have small cases are _ instead of " ". If you leave the Fieldname blank, it will be automatically set when you save it.

You can also set other properties of the field like whether it is mandatory, read only etc.

We can add the following fields:

1. Article Name (Data)
1. Author (Data)
1. Status (Select): For Select fields, you will enter the Options. Enter **Issued** and **Available** each on a new line in the Options box. See diagram below
1. Publisher (Data)
1. Language (Data)
1. Image (Attach Image)

#### Add Permissions

After adding the fields, add Permissions. For now, let us give Read, Write, Create, Delete and Report access to **Librarian**. Frappe has a finely grained Role based permission model. You can also change permissions later using the **Role Permissions Manager** from **Setup**.

<img class="screenshot" alt="Adding Permissions" src="{{url_prefix}}/assets/img/doctype_adding_permission.png">

#### Saving

Click on the **Save** button. When the button is clicked, a popup will ask you for the name. Enter it and save the DocType.

Now login into mysql and check the database table created:

	$ bench mysql
	Welcome to the MariaDB monitor.  Commands end with ; or \g.
	Your MariaDB connection id is 3931
	Server version: 5.5.36-MariaDB-log Homebrew

	Copyright (c) 2000, 2014, Oracle, Monty Program Ab and others.

	Type 'help;' or '\h' for help. Type '\c' to clear the current input statement.

	MariaDB [library]> DESC tabArticle;
	+--------------+--------------+------+-----+---------+-------+
	| Field        | Type         | Null | Key | Default | Extra |
	+--------------+--------------+------+-----+---------+-------+
	| name         | varchar(255) | NO   | PRI | NULL    |       |
	| creation     | datetime(6)  | YES  |     | NULL    |       |
	| modified     | datetime(6)  | YES  |     | NULL    |       |
	| modified_by  | varchar(40)  | YES  |     | NULL    |       |
	| owner        | varchar(60)  | YES  |     | NULL    |       |
	| docstatus    | int(1)       | YES  |     | 0       |       |
	| parent       | varchar(255) | YES  | MUL | NULL    |       |
	| parentfield  | varchar(255) | YES  |     | NULL    |       |
	| parenttype   | varchar(255) | YES  |     | NULL    |       |
	| idx          | int(8)       | YES  |     | NULL    |       |
	| article_name | varchar(255) | YES  |     | NULL    |       |
	| status       | varchar(255) | YES  |     | NULL    |       |
	| description  | text         | YES  |     | NULL    |       |
	| image        | varchar(255) | YES  |     | NULL    |       |
	| publisher    | varchar(255) | YES  |     | NULL    |       |
	| isbn         | varchar(255) | YES  |     | NULL    |       |
	| language     | varchar(255) | YES  |     | NULL    |       |
	| author       | varchar(255) | YES  |     | NULL    |       |
	+--------------+--------------+------+-----+---------+-------+
	18 rows in set (0.00 sec)


As you can see, along with the DocFields, a bunch of standard columns have also been added to the table. Important to note here are, the primary key, `name`, `owner` is the user who has created the record, `creation` and `modified` are timestamps for creation and last modification.

{next}

