frappe.ui.form.on("Note", {
	refresh: function (frm) {
		if (frm.doc.__islocal) {
			frm.events.set_editable(frm, true);
		} else {
			if (!frm.doc.content) {
				frm.doc.content = "<span></span>";
			}

			// toggle edit
			frm.add_custom_button("Edit", function () {
				frm.events.set_editable(frm, !frm.is_note_editable);
			});
			frm.events.set_editable(frm, false);
		}
	},
	set_editable: function (frm, editable) {
		// hide all fields other than content

		// no permission
		if (editable && !frm.perm[0].write) return;

		// content read_only
		frm.set_df_property("content", "read_only", editable ? 0 : 1);

		// hide all other fields
		$.each(frm.fields_dict, function (fieldname) {
			if (fieldname !== "content") {
				frm.set_df_property(fieldname, "hidden", editable ? 0 : 1);
			}
		});

		// no label, description for content either
		frm.get_field("content").toggle_label(editable);
		frm.get_field("content").toggle_description(editable);

		// set flag for toggle
		frm.is_note_editable = editable;
	},
});

frappe.tour["Note"] = [
	{
		fieldname: "title",
		title: "Title of the Note",
		description: "This is the name by which the note will be saved, you can change this later",
	},
	{
		fieldname: "public",
		title: "Sets the Note to Public",
		description:
			"You can change the visibility of the note with this, setting it to public will allow other users to view it.",
	},
];
