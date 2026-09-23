import SegmentedRow from "./SegmentedRow.vue";
import ToggleRow from "./ToggleRow.vue";
import StepperRow from "./StepperRow.vue";
import SizeRow from "./SizeRow.vue";
import DropdownRow from "./DropdownRow.vue";
import ColorField from "./ColorField.vue";
import LabelField from "./LabelField.vue";
import StyleSection from "./StyleSection.vue";
import VisibilitySection from "./VisibilitySection.vue";
import HtmlBlockRows from "./HtmlBlockRows.vue";
import TypstBlockRow from "./TypstBlockRow.vue";
import StaticTextRow from "./StaticTextRow.vue";
import ImageBlockRows from "./ImageBlockRows.vue";
import BarcodeRows from "./BarcodeRows.vue";
import LinkedFieldRows from "./LinkedFieldRows.vue";
import { align_opts } from "./align_opts";
import { has_align, is_breakable, is_text } from "../../fieldtypes";

const ft = (type) => (df) => df.fieldtype === type;
const SPECIAL = new Set([
	"HTML",
	"Typst",
	"Barcode",
	"Static Text",
	"Linked Field",
	"Spacer",
	"Divider",
]);
const is_image_block = (df) => df.fieldtype === "Image" && !!df.custom;
const is_plain = (df) => !SPECIAL.has(df.fieldtype) && !is_image_block(df);
const has_label = (df) => is_plain(df) || df.fieldtype === "Linked Field";
const is_static_text = ft("Static Text");
const styled_text = (df) => is_text(df) && !is_static_text(df);

const bold = (when) => ({
	key: "bold",
	component: ToggleRow,
	when,
	props: () => ({ label: __("Bold") }),
	get: (df) => !!df.bold,
	set: (df, v, ctx) => ctx.set(df, "bold", v ? 1 : 0, 0),
	mixed: false,
});
const font_size = (when) => ({
	key: "font_size",
	component: StepperRow,
	when,
	props: () => ({
		label: __("Font size"),
		base: 13,
		unit: "px",
		placeholder: __("auto"),
		allowEmpty: true,
	}),
	mixed: null,
});
const color = (key, label) => ({
	key,
	component: ColorField,
	when: is_text,
	props: () => ({ label: label() }),
	get: (df) => df[key] || "",
});

export const FIELD_SECTIONS = [
	{
		key: "field",
		label: () => __("Field"),
		rows: [
			{ key: "html", component: HtmlBlockRows, bare: true, single: true, when: ft("HTML") },
			{
				key: "typst",
				component: TypstBlockRow,
				bare: true,
				single: true,
				when: ft("Typst"),
			},
			{
				key: "image",
				component: ImageBlockRows,
				bare: true,
				single: true,
				when: is_image_block,
			},
			{
				key: "barcode",
				component: BarcodeRows,
				bare: true,
				single: true,
				when: ft("Barcode"),
			},
			{
				key: "text",
				component: StaticTextRow,
				bare: true,
				single: true,
				when: is_static_text,
			},
			{
				key: "linked",
				component: LinkedFieldRows,
				bare: true,
				single: true,
				when: ft("Linked Field"),
			},
			{
				key: "height",
				component: StepperRow,
				when: ft("Spacer"),
				props: () => ({
					label: __("Height"),
					base: 16,
					step: 4,
					unit: "px",
					placeholder: __("auto"),
					allowEmpty: true,
				}),
				mixed: null,
			},
			{
				key: "label",
				component: LabelField,
				single: true,
				when: has_label,
				props: (df) => ({
					label: __("Label"),
					placeholder: __("Field label"),
					showToggle: true,
					show: df.show_label,
				}),
				get: (df) => df.label ?? "",
				set: (df, v) => (df.label = v),
				on: { "update:show": (df, v) => (df.show_label = v) },
			},
			{
				key: "show_label",
				component: ToggleRow,
				multi: true,
				when: has_label,
				props: () => ({ label: __("Show label") }),
				get: (df) => df.show_label !== "hide",
				set: (df, v) => (df.show_label = v ? "show" : "hide"),
				mixed: false,
			},
			bold(is_static_text),
			font_size(is_static_text),
			{
				key: "align",
				component: SegmentedRow,
				when: has_align,
				props: () => ({ label: __("Align"), options: align_opts }),
				get: (df) => df.align ?? "left",
				set: (df, v, ctx) => ctx.set(df, "align", v, "left"),
			},
			{
				key: "width",
				component: SizeRow,
				when: ft("Attach Image"),
				props: () => ({ label: __("Size") }),
				set: (df, v) => (df.width = v),
			},
			{
				key: "label_justify",
				component: DropdownRow,
				when: (df, ctx) =>
					is_plain(df) && ctx.inline(df) && (df.align ?? "left") === "left",
				props: () => ({
					label: __("Spacing"),
					options: [
						{ value: "", label: __("Normal") },
						{ value: "space-between", label: __("Space Between") },
						{ value: "space-evenly", label: __("Space Evenly") },
					],
				}),
				get: (df) => df.label_justify ?? "",
			},
			{
				key: "label_gap",
				component: StepperRow,
				when: (df, ctx) => is_plain(df) && ctx.inline(df),
				props: () => ({
					label: __("Label gap"),
					base: 8,
					step: 2,
					unit: "px",
					placeholder: __("auto"),
					allowEmpty: true,
				}),
				mixed: null,
			},
			{
				key: "allow_page_break",
				component: ToggleRow,
				when: is_breakable,
				props: () => ({ label: __("Split across pages") }),
				get: (df) => !!df.allow_page_break,
				set: (df, v, ctx) => ctx.set(df, "allow_page_break", v, false),
				mixed: false,
			},
		],
	},
	{
		key: "style",
		label: () => __("Style"),
		init_open: false,
		rows: [
			bold(styled_text),
			font_size(styled_text),
			color("label_color", () => __("Label")),
			color("value_color", () => __("Value")),
			{
				key: "hide_colon",
				component: ToggleRow,
				when: (df, ctx) =>
					is_text(df) &&
					!!ctx.print_format?.show_label_colon &&
					!!df.label &&
					df.show_label !== "hide",
				props: () => ({ label: __("Hide colon") }),
				get: (df) => !!df.hide_colon,
				set: (df, v, ctx) => ctx.set(df, "hide_colon", v ? 1 : 0, 0),
				mixed: false,
			},
		],
		after: [
			{
				key: "custom_style",
				component: StyleSection,
				single: true,
				props: () => ({ label: __("Custom CSS") }),
				set: (df, v) => (df.custom_style = v),
			},
		],
	},
	{
		key: "visibility",
		label: () => __("Visibility"),
		init_open: false,
		rows: [
			{
				key: "show_empty",
				component: ToggleRow,
				when: ft("Linked Field"),
				props: () => ({ label: __("Print if empty") }),
				get: (df) => !!df.show_empty,
				set: (df, v, ctx) => ctx.set(df, "show_empty", v ? 1 : 0, 0),
				mixed: false,
			},
		],
		after: [
			{
				key: "visible_if",
				component: VisibilitySection,
				single: true,
				set: (df, v) => (df.visible_if = v),
			},
		],
	},
];
