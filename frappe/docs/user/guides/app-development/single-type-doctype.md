DocTypes have a table associated with them. For example DocType **Customer** will have a table `tabCustomer` associated with it.

**Single** type DocTypes have no table associated and there is only one Document for it. This is similar to the Singleton pattern in Java. Single DocTypes are ideal for saving Settings (that are globally applicable) and for wizard / helper type forms that have no documents, but when the DocType is used for the Form UI.

The data in Single DocType is stored in `tabSingles` (`doctype`, `field`, `value`)

#### Examples 

In Frappe, Single types are **System Settings** and **Customize Form**