To execute code when a DocType is inserted, validated (before saving), updated, submitted, cancelled, deleted, you must write in the DocType's controller module. 

#### 1. Controller Module

The controller module exists in the `doctype` folder in the Module of the `DocType`. For example, the controller for **ToDo** exists in `frappe/desk/doctype/todo/todo.py` (version 5). A controller template is created when the DocType is created. which looks like

    from __future__ import unicode_literals
    
    import frappe
    from frappe.model.document import Document
    
    class CustomType(Document):
        pass

#### 2. Document Properties

All the fields and child tables are available to the class as attributes. For example the **name** property is `self.name`

#### 3. Adding Methods

In this module, you can add standard methods to the class that are called when a document of that type is created. Standard Handlers are:

1. `autoname`: Called while naming. You can set the `self.name` property in the method.
1. `before_insert`: Called before a document is inserted.
1. `validate`: Called before document is saved. You can throw an exception if you don't want the document to be saved
1. `on_update`: Called after the document is inserted or updated in the database.
1. `on_submit`: Called after submission.
1. `on_cancel`: Called after cancellation.
1. `on_trash`: Called after document is deleted.
