import { watch } from "vue";
import { useMainStore } from "./MainStore";
export const fetchMeta = () => {
	return new Promise((resolve) => {
		const MainStore = useMainStore();
		frappe.model.clear_doc("Print Format", MainStore.print_design_name);
		frappe.model.with_doc("Print Format", MainStore.print_design_name, () => {
			let print_format = frappe.get_doc("Print Format", MainStore.print_design_name);
			MainStore.doctype = print_format.doc_type;

			frappe.model.with_doctype(print_format.doc_type, () => {
				let metaFields = frappe.get_meta(print_format.doc_type).fields.filter((df) => {
					if (
						["Section Break", "Column Break", "Tab Break"].includes(df.fieldtype) ||
						(df.print_hide == 1 && df.fieldtype != "Link")
					) {
						return false;
					} else {
						return true;
					}
				});
				metaFields.map((field) => {
					if (field["print_hide"] && field["fieldtype"] != "Link") return;
					let obj = {};
					["fieldname", "fieldtype", "label", "options"].forEach((attr) => {
						obj[attr] = field[attr];
					});
					MainStore.metaFields.push({ ...obj });
				});
				metaFields.map((field) => {
					if (field["fieldtype"] != "Table" || field["print_hide"]) return;
					getMeta(field.options, field.fieldname);
				});
				fetchDoc();
			});
		});
	});
};

export const getMeta = async (doctype, parentField) => {
	const MainStore = useMainStore();
	const parentMetaField = MainStore.metaFields.find((o) => o.fieldname == parentField);
	if (MainStore.metaFields.find((o) => o.fieldname == parentField)["childfields"]) {
		return MainStore.metaFields[parentField]["childfields"];
	}
	let result;
	const exculdeFields = ["Section Break", "Column Break", "Tab Break", "HTML"];
	if (parentMetaField.fieldtype != "Table") {
		// Remove Link Field
		exculdeFields.push("Link");
	}
	await frappe.model.with_doctype(doctype, async () => {
		result = await frappe.get_meta(doctype);
	});
	let childfields = result.fields.filter((df) => {
		if (exculdeFields.includes(df.fieldtype) || df.print_hide == 1) {
			return false;
		} else {
			return true;
		}
	});

	let fields = [];
	childfields.map((field) => {
		let obj = {};
		["fieldname", "fieldtype", "label", "options", "print_hide"].forEach((attr) => {
			obj[attr] = field[attr];
		});
		fields.push({ ...obj });
	});
	parentMetaField["childfields"] = fields;
	return fields;
};
export const getValue = async (doctype, name, fieldname) => {
	const result = await frappe.db.get_value(doctype, name, fieldname);

	const value = await result.message[fieldname];
	return value;
};

export const fetchDoc = async (id = null) => {
	const MainStore = useMainStore();
	let doctype = MainStore.doctype;
	let doc;
	if (!id) {
		let latestdoc = await frappe.db.get_list(doctype, {
			fields: ["name"],
			order_by: "modified desc",
			limit: 1,
		});
		id = latestdoc[0].name;
	}
	watch(
		() => MainStore.currentDoc,
		async () => {
			doc = await frappe.db.get_doc(doctype, MainStore.currentDoc);
			Object.keys(doc).forEach((element) => {
				if (
					!MainStore.metaFields.find((o) => o.fieldname == element) &&
					element != "name"
				) {
					delete doc[element];
				}
			});
			MainStore.docData = doc;
			await frappe.dom.freeze();
			MainStore.dynamicData.forEach(async (el) => {
				if (el.is_static) return;
				let value = el.parentField
					? await getValue(el.doctype, MainStore.docData[el.parentField], el.fieldname)
					: MainStore.docData[el.fieldname];
				if (!value) {
					if (["Image, Attach Image"].indexOf(el.fieldtype)) {
						value = null;
					} else {
						value = `{{ ${el.parentField ? el.parentField + "." : ""}${
							el.fieldname
						} }}`;
					}
				}
				el.value = value;
			});
			await frappe.dom.unfreeze();
		}
	);
	MainStore.currentDoc = id;
};
