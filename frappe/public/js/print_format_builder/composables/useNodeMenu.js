function paste_option(store) {
	return {
		label: __("Paste"),
		icon: "clipboard-paste",
		condition: () => !!store.clipboard.value,
		onclick: () => store.paste_clipboard(),
	};
}

function delete_group(label, onclick, condition) {
	return {
		group: "",
		hide_label: true,
		options: [{ label, icon: "trash", theme: "red", condition, onclick }],
	};
}

export function field_menu_options(store, df, { paste = true } = {}) {
	return [
		{ label: __("Copy"), icon: "copy", onclick: () => store.copy_field(df) },
		{ label: __("Duplicate"), icon: "copy-plus", onclick: () => store.duplicate_field(df) },
		{
			label: __("Save as snippet"),
			icon: "bookmark-plus",
			onclick: () => store.prompt_snippet(df, "Field"),
		},
		...(paste ? [paste_option(store)] : []),
		delete_group(__("Delete"), () => store.remove_field(df)),
	];
}

export function section_menu_options(store, section, { paste = true, condition } = {}) {
	return [
		{
			label: __("Copy section"),
			icon: "copy",
			condition,
			onclick: () => store.copy_section(section),
		},
		{
			label: __("Duplicate section"),
			icon: "copy-plus",
			condition,
			onclick: () => store.duplicate_section(section),
		},
		{
			label: __("Save as snippet"),
			icon: "bookmark-plus",
			condition,
			onclick: () => store.prompt_snippet(section, "Section"),
		},
		...(paste ? [paste_option(store)] : []),
		delete_group(__("Delete section"), () => store.remove_section(section), condition),
	];
}
