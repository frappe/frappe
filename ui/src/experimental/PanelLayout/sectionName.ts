import type { Section } from "../../components/FormLayout/types";

// Verbs on the panelSections surface target names only, so every section must
// carry one: real when the layout doc stores it, else synthesized from the
// label — which changes when the label does, the reason authors should set real names.
export function sectionName(section: Section) {
	return section.name ?? slugified(section.label) ?? "";
}

function slugified(label?: string) {
	if (!label) return undefined;
	return label
		.toLowerCase()
		.replace(/[^a-z0-9]+/g, "_")
		.replace(/^_+|_+$/g, "");
}
