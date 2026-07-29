import { computed, ref } from "vue";
import { clone_plain, read_json } from "../utils";

const DOCTYPE = "Print Format Snippet";
const LEGACY_KEY = "pfb_section_snippets";

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

	// frappe.db.get_list never settles its promise on failure, so go through
	// xcall — a permission error must reject, not hang the builder forever.
	async function reload() {
		const rows = await frappe.xcall("frappe.client.get_list", {
			doctype: DOCTYPE,
			fields: ["name", "snippet_type", "document_type", "content"],
			limit_page_length: 0,
			order_by: "name asc",
		});
		all_snippets.value = (rows || []).map(parse).filter(Boolean);
	}

	// Writes without reloading, so bulk callers pay for one round trip instead of N.
	// The optimistic push keeps the "already exists" check honest within a batch.
	async function write_snippet(name, data, snippet_type, document_type) {
		name = (name || "").trim();
		if (!name || !data) return null;
		const parsed = clone_plain(data);
		const content = JSON.stringify(parsed);
		const existing = all_snippets.value.find((s) => s.name === name);
		// The docname is global, so a name taken by another document type would be
		// silently rewritten — refuse instead of destroying a snippet the user can't see.
		const scope = document_type ?? doc_type?.value ?? "";
		if (existing && existing.document_type && existing.document_type !== scope) {
			frappe.throw(
				__("A snippet named {0} already exists for {1}.", [name, existing.document_type])
			);
		}
		if (existing) {
			// Scope is never rewritten by a write: importing a Sales Invoice snippet
			// over a global one would otherwise narrow it and hide it from everyone else.
			const update = { content, snippet_type };
			await frappe.db.set_value(DOCTYPE, name, update);
			Object.assign(existing, update, { content: parsed });
		} else {
			const row = {
				name,
				snippet_type,
				document_type: document_type ?? doc_type?.value ?? "",
				content,
			};
			await frappe.db.insert({ doctype: DOCTYPE, __newname: name, ...row });
			all_snippets.value.push({ ...row, content: parsed });
		}
		return name;
	}

	async function save_snippet(name, data, snippet_type = "Section", document_type) {
		if (await write_snippet(name, data, snippet_type, document_type)) await reload();
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

	// One-time lift of the old browser-local snippets. Anything whose name is already
	// taken on the server stays in localStorage rather than being dropped on the floor.
	async function migrate_legacy() {
		const legacy = read_json(LEGACY_KEY, []);
		if (!legacy.length) return;
		const kept = [];
		for (const snip of legacy) {
			if (!snip?.name || !snip?.section) continue;
			if (all_snippets.value.some((s) => s.name === snip.name)) {
				kept.push(snip);
				continue;
			}
			await write_snippet(snip.name, snip.section, "Section", "");
		}
		if (kept.length) {
			localStorage.setItem(LEGACY_KEY, JSON.stringify(kept));
			frappe.show_alert(
				{
					message: __(
						"{0} saved section(s) already exist by name and were not imported",
						[kept.length]
					),
					indicator: "orange",
				},
				7
			);
		} else {
			localStorage.removeItem(LEGACY_KEY);
		}
		await reload();
	}

	async function init() {
		await reload();
		await migrate_legacy();
	}

	init().catch((e) => console.error("Could not load print format snippets", e));

	return {
		snippets,
		save_snippet,
		insert_snippet,
		delete_snippet,
	};
}
