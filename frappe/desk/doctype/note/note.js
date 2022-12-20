frappe.ui.form.on("Note", {
	refresh: function (frm) {
		if (!frm.is_new()) {
			frm.is_note_editable = false;
			frm.events.set_editable(frm, frm.is_note_editable);

			// toggle edit
			frm.add_custom_button("Edit", function () {
				frm.is_note_editable = !frm.is_note_editable;
				frm.events.set_editable(frm, frm.is_note_editable);
			});
		}
	},
	set_editable: function (frm, editable) {
		// toggle "read_only" for content and "hidden" of all other fields

		// content read_only
		frm.set_df_property("content", "read_only", editable ? 0 : 1);

		// hide all other fields
		for (const field of frm.meta.fields) {
			if (field.fieldname !== "content") {
				frm.set_df_property(
					field.fieldname,
					"hidden",
					editable && !field.hidden && frm.get_perm(field.permlevel, "write") ? 0 : 1
				);
			}
		}

		// no label, description for content either
		frm.get_field("content").toggle_label(editable);
		frm.get_field("content").toggle_description(editable);
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
