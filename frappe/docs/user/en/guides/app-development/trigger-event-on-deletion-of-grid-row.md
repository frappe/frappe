# Trigger Event On Deletion Of Grid Row

To trigger an event when a row from a Child Table has been deleted (when user clicks on `delete` button), you need to add a handler the `fieldname_remove` event to Child Table, where fieldname is the fieldname of the Child Table in Parent Table declaration.

 For example:

 Assuming that your parent DocType is named `Item` has a Table Field linked to `Item Color` DocType with decloration name `color`.

 In order to "catch" the delete event:

	frappe.ui.form.on('Item Color', {
		color_remove: function(frm) {
			// You code here
			// If you console.log(frm.doc.color) you will get the remaining color list
		}
	);

 The same process is used to trigger the add event (when user clicks on `add row` button):

	frappe.ui.form.on('Item Color', {
		color_remove: function(frm) {
			// You code here
			// If you console.log(frm.doc.color) you will get the remaining color list
		},
		color_add: function(frm) {
		}
	});

 Notice that the handling is be made on Child DocType Table `form.ui.on` and not on Parent Doctype so a minimal full example is:


 ```javascript
    frappe.ui.form.on('Item',{
    	// Your client side handling for Item
    });

    frappe.ui.form.on('Item Color', {
      color_remove: function(frm) {
         // Deleting is triggered here
      }
   );
 ```
Handlers are:

1. fieldname_add
1. fieldname_move
1. fieldname_before_remove
1. fieldname_remove

