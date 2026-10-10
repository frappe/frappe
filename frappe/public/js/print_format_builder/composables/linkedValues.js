import { reactive } from "vue";

export const linked_values = reactive({});

export function linked_target(df, meta, doc) {
	const [link_fieldname, fieldname] = (df.link_path || "").split(".");
	if (!fieldname) return null;
	const link_df = (meta?.fields || []).find(
		(f) => f.fieldname === link_fieldname && f.fieldtype === "Link"
	);
	const name = doc?.[link_fieldname];
	if (!link_df?.options || !name) return null;
	return {
		doctype: link_df.options,
		name,
		fieldname,
		key: `${link_df.options}:${name}:${fieldname}`,
	};
}
