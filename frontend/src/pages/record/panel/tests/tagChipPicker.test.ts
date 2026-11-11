// A chip in the identity row opens the real tag picker on its own tag, after the opening search lands.
import { afterEach, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, ref } from "vue";

const TAGS = ["zebra", "alpha", "bravo", "charlie", "delta", "echo", "foxtrot", "golf", "hotel", "india"];

const api = vi.hoisted(() => ({
	listDocuments: vi.fn(async () => ({ data: [] as { name: string; color: string }[] })),
	searchDocuments: vi.fn(async () => ({ data: [] })),
	runMethod: vi.fn(async () => ({ data: null })),
	runPartMethod: vi.fn(async () => ({ data: null })),
}));

vi.mock("@framework/ui/api", () => api);

import { PanelContextKey, type DocInfo } from "../context";
import RecordIdentity from "../RecordIdentity.vue";

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
	vi.restoreAllMocks();
});

it("opens the picker on the clicked chip's tag, scrolled to it and highlighted", async () => {
	api.listDocuments.mockResolvedValue({ data: [...TAGS].sort().map((name) => ({ name, color: "Gray" })) });
	const scrolled = vi.spyOn(Element.prototype, "scrollIntoView").mockImplementation(() => {});
	const root = mountIdentity({
		assignments: [],
		shares: [],
		tags: TAGS,
		users: {},
		permissions: { write: 1 },
	});

	root.querySelector<HTMLElement>('[data-tag-chip="zebra"]')!.click();

	await vi.waitFor(() => expect(api.listDocuments).toHaveBeenCalled());
	await vi.waitFor(() => {
		const highlighted = document.querySelector<HTMLElement>('[role="option"][data-highlighted]');
		expect(highlighted?.textContent).toContain("zebra");
		expect(scrolled.mock.contexts.at(-1)).toBe(highlighted);
	});
	const rows = [...document.querySelectorAll('[role="option"]')].map((row) => row.textContent?.trim());
	expect(rows.at(-1)).toContain("zebra");
	expect(root.querySelector("[data-tags] .lucide-x")).toBeNull();
});

function mountIdentity(info: DocInfo) {
	const context = {
		doctype: "ToDo",
		docname: "T-1",
		doc: ref({}),
		meta: ref(null),
		docinfo: ref<DocInfo | null>(info),
		controller: {
			page: { toast: { error: vi.fn() } },
			quickActions: { visible: () => [] },
			allows: () => true,
		} as any,
		run: vi.fn(),
		reloadDocinfo: vi.fn(async () => {}),
		whileOnRecord: () => () => true,
		onDetails: () => false,
	};
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(defineComponent({ render: () => h(RecordIdentity) }));
	app.provide(PanelContextKey, context);
	app.mount(root);
	mounted.push(app);
	return root;
}
