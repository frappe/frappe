import { computed, ref } from "vue";
import { clone_plain } from "../utils";

const DOCTYPE = "Print Format Snippet";
const LEGACY_KEY = "pfb_section_snippets";

function read_legacy() {
	try {
		return JSON.parse(localStorage.getItem(LEGACY_KEY)) || [];
	} catch {
		return [];
	}
}

export function useSnippets({ insert_section, insert_field, doc_type }) {
	const all_snippets = ref([]);
	const snippets = computed(() => {
		const current = doc_type?.value;
		return all_snippets.value.filter(
			(s) => !s.document_type || !current || s.document_type === current
		);
	});

	function parse(row) {
		try {
			return { ...row, content: JSON.parse(row.content) };
		} catch {
			return null;
		}
	}

	async function reload() {
		let rows;
		try {
			rows = await frappe.db.get_list(DOCTYPE, {
				fields: ["name", "snippet_type", "document_type", "content"],
				limit: 0,
				order_by: "name asc",
			});
		} catch {
			all_snippets.value = [];
			return;
		}
		all_snippets.value = rows.map(parse).filter(Boolean);
	}

	async function save_snippet(name, data, snippet_type = "Section", document_type) {
		name = (name || "").trim();
		if (!name || !data) return;
		const content = JSON.stringify(clone_plain(data));
		const existing = all_snippets.value.find((s) => s.name === name);
		if (existing) {
			await frappe.db.set_value(DOCTYPE, name, { content, snippet_type });
		} else {
			await frappe.db.insert({
				doctype: DOCTYPE,
				__newname: name,
				snippet_type,
				document_type: document_type ?? doc_type?.value ?? "",
				content,
			});
		}
		await reload();
	}

	function insert_snippet(name) {
		const snip = snippets.value.find((s) => s.name === name);
		if (!snip) return;
		if (snip.snippet_type === "Field") insert_field(snip.content);
		else insert_section(snip.content);
	}

	async function delete_snippet(name) {
		await frappe.db.delete_doc(DOCTYPE, name);
		await reload();
	}

	function export_snippets(names) {
		const picked = names?.length
			? snippets.value.filter((s) => names.includes(s.name))
			: snippets.value;
		if (!picked.length) return;
		const payload = {
			version: 1,
			snippets: picked.map((s) => ({
				name: s.name,
				snippet_type: s.snippet_type,
				document_type: s.document_type || "",
				content: s.content,
			})),
		};
		const blob = new Blob([JSON.stringify(payload, null, 2)], { type: "application/json" });
		const a = document.createElement("a");
		a.href = URL.createObjectURL(blob);
		a.download = "print-format-snippets.json";
		document.body.appendChild(a);
		a.click();
		document.body.removeChild(a);
	}

	async function import_snippets(payload) {
		const rows = Array.isArray(payload) ? payload : payload?.snippets;
		if (!Array.isArray(rows)) {
			frappe.throw(__("This file does not contain any snippets"));
		}
		let imported = 0;
		let other_doctypes = 0;
		const current = doc_type?.value;
		for (const row of rows) {
			if (!row?.name || !row?.content) continue;
			const document_type = row.document_type || "";
			await save_snippet(
				row.name,
				row.content,
				row.snippet_type || "Section",
				document_type
			);
			imported++;
			if (document_type && current && document_type !== current) other_doctypes++;
		}
		await reload();
		return { imported, other_doctypes };
	}

	async function migrate_legacy() {
		const legacy = read_legacy();
		if (!legacy.length) return;
		for (const snip of legacy) {
			if (!snip?.name || !snip?.section) continue;
			if (all_snippets.value.some((s) => s.name === snip.name)) continue;
			await save_snippet(snip.name, snip.section, "Section", "");
		}
		localStorage.removeItem(LEGACY_KEY);
		await reload();
	}

	async function init() {
		await reload();
		await migrate_legacy();
	}

	init().catch(() => {});

	return {
		snippets,
		save_snippet,
		insert_snippet,
		delete_snippet,
		export_snippets,
		import_snippets,
		reload_snippets: reload,
	};
}
