import { watch } from "vue";
import { useMainStore } from "./store/MainStore";
import { useChangeValueUnit } from "./composables/ChangeValueUnit";

export const refSelectDocumentControl = (ref) => {
	if (!ref || ref.hasChildNodes()) return;
	const MainStore = useMainStore();
	let pages = [];
	const PageUOM = Object.freeze({
		px: "Pixels (px)",
		mm: "Milimeter (mm)",
		cm: "Centimeter (cm)",
		in: "Inch (in)",
	});
	let selectDocument = new frappe.ui.FieldGroup({
		body: $(ref),
		fields: [
			{
				fieldname: "name",
				fieldtype: "Link",
				options: "Sales Invoice",
				default: MainStore.currentDoc,
				change: () => {
					let { name } = selectDocument.get_values();
					if (name && MainStore.currentDoc != name) {
						MainStore.currentDoc = name;
					} else if (!name && MainStore.currentDoc) {
						selectDocument.set_value("name", MainStore.currentDoc);
					}
				},
			},
			{
				fieldname: "page_size",
				fieldtype: "Autocomplete",
				options: [
					"A10",
					"A1",
					"A0",
					"A3",
					"A2",
					"A5",
					"A4",
					"A7",
					"A6",
					"A9",
					"A8",
					"B10",
					"B1+",
					"B4",
					"B5",
					"B6",
					"B7",
					"B0",
					"B1",
					"B2",
					"B3",
					"B2+",
					"B8",
					"B9",
					"C10",
					"C9",
					"C8",
					"C3",
					"C2",
					"C1",
					"C0",
					"C7",
					"C6",
					"C5",
					"C4",
				],
				default: MainStore.currentPageSize,
				change: () => {
					let { page_size } = selectDocument.get_values();
					if (page_size && MainStore.currentPageSize != page_size) {
						MainStore.currentPageSize = page_size;
						MainStore.page.width = MainStore.pageSizes[page_size][0];
						MainStore.page.height = MainStore.pageSizes[page_size][1];
					} else if (!page_size && MainStore.currentPageSize) {
						selectDocument.set_value("page_size", MainStore.currentPageSize);
					}
				},
			},
			{
				fieldname: "uom",
				fieldtype: "Autocomplete",
				options: ["Pixels (px)", "Milimeter (mm)", "Centimeter (cm)", "Inch (in)"],
				default: PageUOM[MainStore.page.UOM],
				change: () => {
					let { uom } = selectDocument.get_values();
					if (uom && PageUOM[MainStore.page.UOM] != uom) {
						uom = Object.entries(PageUOM).find((entry) => entry[1] === uom)[0];
						Object.keys(MainStore.page).forEach((property) => {
							if (property != "UOM") {
								MainStore.page[property] = useChangeValueUnit({
									inputString: MainStore.page[property],
									defaultInputUnit: MainStore.page.UOM,
									convertionUnit: uom,
								}).value;
							}
						});
						MainStore.page.UOM = uom;
					} else if (!uom && PageUOM[MainStore.page.UOM]) {
						selectDocument.set_value("uom", PageUOM[MainStore.page.UOM]);
					}
				},
			},
		],
	});
	selectDocument.make();
	let setCurrentDocIfEmpty = watch(
		() => MainStore.currentDoc,
		() => {
			if (MainStore.currentDoc && !selectDocument.get_values().name) {
				selectDocument.set_value("name", MainStore.currentDoc);
				setCurrentDocIfEmpty();
			}
		}
	);
};
export const refSelectTableControl = (ref) => {
	if (!ref || ref.hasChildNodes()) return;
	const MainStore = useMainStore();
	let fields = [];
	MainStore.getTableMetaFields.map((field) => fields.push(field.fieldname));
	let selectDocument = new frappe.ui.FieldGroup({
		body: $(ref),
		fields: [
			{
				label: __(MainStore.doctype || "Document"),
				fieldname: "name",
				fieldtype: "Link",
				options: "Sales Invoice",
				default: MainStore.currentDoc,
				change: () => {
					let { name } = selectDocument.get_values();
					if (name && MainStore.currentDoc != name) {
						MainStore.currentDoc = name;
					} else if (!name && MainStore.currentDoc) {
						selectDocument.set_value("name", MainStore.currentDoc);
					}
				},
			},
			{
				label: __("Table"),
				fieldname: "table",
				fieldtype: "Autocomplete",
				options: fields,
			},
			{
				label: __("Color"),
				fieldname: "color",
				fieldtype: "Color",
			},
		],
	});
	selectDocument.make();
	let setCurrentDocIfEmpty = watch(
		() => MainStore.currentDoc,
		() => {
			if (MainStore.currentDoc && !selectDocument.get_values().name) {
				selectDocument.set_value("name", MainStore.currentDoc);
				setCurrentDocIfEmpty();
			}
		}
	);
	let setTableOptionsIfEmpty = watch(
		() => MainStore.getTableMetaFields,
		() => {
			if (MainStore.getTableMetaFields.length) {
				MainStore.getTableMetaFields.map((field) => fields.push(field.fieldname));
				setTableOptionsIfEmpty();
			}
		}
	);
};
