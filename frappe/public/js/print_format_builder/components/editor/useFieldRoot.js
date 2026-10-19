import { computed } from "vue";
import { parse_inline_style } from "../../utils";

export function useFieldStyles(props) {
	const custom_style = computed(() => parse_inline_style(props.df.custom_style));
	const text_style = computed(() => ({
		...(props.df.bold ? { fontWeight: 700 } : {}),
		...(props.df.font_size ? { fontSize: props.df.font_size + "px" } : {}),
	}));
	const static_text_style = computed(() => ({
		whiteSpace: "pre-line",
		...text_style.value,
		...(props.df.align ? { textAlign: props.df.align } : {}),
	}));
	return { custom_style, text_style, static_text_style };
}

// Mirrors the root markup of templates/print_format/macros/*.html per fieldtype
export function useFieldRoot(props, preview_doc) {
	const { custom_style, text_style } = useFieldStyles(props);

	const preview_root = computed(() => {
		const df = props.df;
		const custom = custom_style.value;
		if (df.fieldtype === "Table") {
			return {
				classes: [
					"child-table",
					`child-table--${df.table_style || "lined"}`,
					df.table_header === "plain" ? "child-table--plain-header" : "",
					df.table_bordered !== false ? "child-table--bordered" : "",
				],
				style: custom,
			};
		}
		if (df.fieldtype === "Repeater") return { classes: ["pfb-repeater"], style: custom };
		if (df.fieldtype === "HTML") return { classes: ["custom-html"], style: custom };
		if (df.fieldtype === "Field Template")
			return { classes: ["field-template"], style: custom };
		if (df.fieldtype === "Spacer")
			return {
				classes: [],
				style: { height: df.height ? `${df.height}px` : "1em", ...custom },
			};
		if (df.fieldtype === "Divider") {
			return {
				classes: [],
				style: {
					height: "1px",
					margin: "0.5em 0",
					borderBottom: "1px solid",
					borderBottomColor: "var(--dark-border-color)",
					...custom,
				},
			};
		}
		if (df.fieldtype === "Image" || df.fieldtype === "Barcode") {
			return {
				classes: [
					"field",
					df.fieldtype === "Image" ? "print-image" : "print-barcode",
					df.align ? `field-align-${df.align}` : "",
				],
				style: custom,
			};
		}
		const lr = props.field_orientation === "left-right";
		const style = {};
		if ((lr || df.show_label === "inline") && df.label_gap != null) {
			style.gap = df.label_gap + "px";
		}
		return {
			classes: [
				"field",
				lr ? "left-right" : "",
				!lr && df.show_label === "inline" ? "field-inline" : "",
				df.align ? `field-align-${df.align}` : "",
				lr && df.label_justify && !["center", "right"].includes(df.align)
					? `field-justify-${df.label_justify}`
					: "",
			],
			style: { ...style, ...text_style.value, ...custom },
		};
	});

	// Spacer/Divider carry no data attributes on the server either
	function preview_data_attr(value) {
		if (!preview_doc.value || !value) return undefined;
		if (props.df.fieldtype === "Spacer" || props.df.fieldtype === "Divider") return undefined;
		return value;
	}

	return { preview_root, preview_data_attr };
}
