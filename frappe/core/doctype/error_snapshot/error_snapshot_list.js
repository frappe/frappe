frappe.listview_settings["Error Snapshot"] = {
	add_fields: ["parent_error_snapshot", "relapses", "seen"],
	filters:[
		["parent_error_snapshot","=",null],
		["seen", "=", false]
	],
	get_indicator: function(doc){
		if (doc.parent_error_snapshot && doc.parent_error_snapshot.length){
			return [__("Relapsed"), !doc.seen ? "orange" : "blue", "parent_error_snapshot,!=,"];
		} else {
			return [__("First Level"), !doc.seen ? "red" : "green", "parent_error_snapshot,=,"];
		}
	}
}
