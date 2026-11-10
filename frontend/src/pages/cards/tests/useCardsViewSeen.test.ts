// Track Seen on the cards view: `_seen` joins the read, and the title class follows the row's seen state.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, ref } from "vue";
import { useCardsView, type CardsView } from "../useCardsView";

const fake = vi.hoisted(() => ({ track: 0 as 0 | 1, query: null as null | (() => { fields: string[] } | null) }));

vi.mock("@framework/ui/api", () => ({ listDocuments: vi.fn() }));
vi.mock("@framework/ui/useDocPermissions", () => ({ useDocPermissions: () => ({ fieldAccess: () => "write" }) }));
vi.mock("@framework/ui/useDoctypeMeta", () => ({
	useDoctypeMeta: () => ({ meta: ref({ title_field: "title", track_seen: fake.track, fields: [] }) }),
}));
vi.mock("@framework/ui/useSession", () => ({ currentSession: () => ({ user: { name: "alice@example.com" } }) }));
vi.mock("@/contributions/registry", () => ({ listHandlersFor: () => [] }));
vi.mock("@/list/pageState", () => ({ useRememberedPageSize: () => ref(20) }));
vi.mock("@/list/useListView", () => ({ deleteRows: vi.fn(), filtersDict: () => ({}) }));
vi.mock("@/list/useListRows", () => ({
	useListRows: (_doctype: string, query: () => { fields: string[] } | null) => {
		fake.query = query;
		return { rows: ref([]) };
	},
}));

const apps: ReturnType<typeof createApp>[] = [];

function cardsView(): CardsView {
	let result!: CardsView;
	const view = { doctype: "Lead", seeded: ref(true), filters: ref([]), sort: ref([]), settings: ref({}) };
	const app = createApp({
		setup() {
			result = useCardsView(view as never);
			return () => null;
		},
	});
	app.provide("boot", { session: { user: { name: "alice@example.com" } } });
	app.mount(document.createElement("div"));
	apps.push(app);
	return result;
}

afterEach(() => {
	for (const app of apps.splice(0)) app.unmount();
	fake.track = 0;
});

describe("cards view on a Track Seen doctype", () => {
	it("reads _seen and bolds the title of a card the user has not opened", () => {
		fake.track = 1;
		const view = cardsView();
		expect(fake.query!()!.fields).toContain("_seen");
		expect(view.titleClassOf({ name: "A", _seen: '["bob@example.com"]' })).toContain("font-medium");
		expect(view.titleClassOf({ name: "A", _seen: '["alice@example.com"]' })).not.toContain("font-medium");
	});

	it("leaves a doctype that does not track seen as it is", () => {
		const view = cardsView();
		expect(fake.query!()!.fields).not.toContain("_seen");
		expect(view.titleClassOf({ name: "A" })).toBe("");
	});
});
