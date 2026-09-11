import type { Section } from "@framework/ui/components/FormLayout/types";

// Every section needs a name a verb can target: the stored one, else one slugified from
// the label, which moves when the label does.
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
