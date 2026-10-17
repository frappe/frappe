import { nextTick, ref, watch } from "vue";
import { zone_of, zones } from "../layout";

export function useTreeNavigation({ layout, letterhead, selection, scroll_target }) {
	const {
		selected_field,
		selected_section,
		selected_letterhead,
		selected_lh_footer,
		is_multi_select,
		select_field,
		select_section,
		select_letterhead,
	} = selection;

	const collapsed_nodes = ref(new Set());
	const is_collapsed = (node) => collapsed_nodes.value.has(node);
	function set_collapsed(node, collapsed) {
		if (is_collapsed(node) === collapsed) return;
		const next = new Set(collapsed_nodes.value);
		collapsed ? next.add(node) : next.delete(node);
		collapsed_nodes.value = next;
	}
	const toggle_collapse = (node) => set_collapsed(node, !is_collapsed(node));
	watch(layout, () => (collapsed_nodes.value = new Set()));

	function visible_nodes() {
		const nodes = [];
		for (const section of zones(layout.value)) {
			nodes.push({ section });
			if (is_collapsed(section)) continue;
			if (zone_of(layout.value, section) && letterhead.value) {
				nodes.push({ section, letterhead: true });
			}
			for (const col of section.columns || []) {
				if (section.columns.length > 1 && is_collapsed(col)) continue;
				for (const field of col.fields || []) {
					if (!field.remove) nodes.push({ section, field });
				}
			}
		}
		return nodes;
	}

	function current_index(nodes) {
		const field = selected_field.value;
		if (field) {
			const i = nodes.findIndex((n) => n.field === field);
			if (i !== -1) return i;
			return nodes.findIndex(
				(n) =>
					!n.field &&
					!n.letterhead &&
					n.section.columns?.some((c) => c.fields?.includes(field))
			);
		}
		if (selected_letterhead.value || selected_lh_footer.value) {
			const zone = selected_lh_footer.value ? layout.value.footer : layout.value.header;
			return nodes.findIndex((n) => n.letterhead && n.section === zone);
		}
		if (selected_section.value) {
			return nodes.findIndex(
				(n) => !n.field && !n.letterhead && n.section === selected_section.value
			);
		}
		return -1;
	}

	function select_node(node) {
		if (node.field) select_field(node.field);
		else if (node.letterhead)
			select_letterhead({ footer: node.section === layout.value.footer });
		else select_section(node.section);
		scroll_target.value = node.field || node.section;
		const tree_focused = !!document.activeElement?.closest(".pfb-tree");
		nextTick(() => {
			const row = document.querySelector(".pfb-tree-row.active");
			row?.scrollIntoView({ block: "nearest" });
			if (tree_focused) row?.focus({ preventScroll: true });
		});
	}

	function navigate(key) {
		if (!layout.value || is_multi_select.value) return false;
		const nodes = visible_nodes();
		const i = current_index(nodes);
		if (i === -1) return false;
		const node = nodes[i];
		const is_section = !node.field && !node.letterhead;
		if (key === "ArrowUp" || key === "ArrowDown") {
			const next = nodes[i + (key === "ArrowUp" ? -1 : 1)];
			if (next) select_node(next);
		} else if (key === "ArrowLeft") {
			if (is_section) set_collapsed(node.section, true);
			else select_node({ section: node.section });
		} else if (key === "ArrowRight" && is_section) {
			if (is_collapsed(node.section)) set_collapsed(node.section, false);
			else if (nodes[i + 1]?.section === node.section) select_node(nodes[i + 1]);
		}
		return true;
	}

	return { is_collapsed, toggle_collapse, navigate };
}
