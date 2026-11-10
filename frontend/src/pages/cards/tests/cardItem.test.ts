// A card is a link to its record's address; its "⋯" menu sits inside it without following the link.
import { afterEach, describe, expect, it, vi } from "vitest";
import { createApp, nextTick } from "vue";
import { createMemoryHistory, createRouter } from "vue-router";
import CardItem from "../CardItem.vue";

vi.mock("@/pages/list/FieldCell.vue", () => ({ default: { template: "<span>3 days ago</span>" } }));
vi.mock("@framework/ui/RichText", () => ({ RichTextView: { props: ["html"], template: "<div v-html='html' />" } }));
vi.mock("@framework/ui/fields", () => ({ LinkMark: { template: "<i data-mark />" } }));

// Handed to the card as is; the card never builds an address.
const CARD_LINK = "/records/NOTE-1";
const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});

async function mount(props: Record<string, unknown>) {
	const router = createRouter({
		history: createMemoryHistory(),
		routes: [{ path: "/:rest(.*)", component: { template: "<div />" } }],
	});
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(CardItem, {
		row: { name: "NOTE-1", title: "Plan", content: "<p>Hello</p>", owner: "a@b.c" },
		titleField: "title",
		bodyField: "content",
		bodyIsHtml: true,
		link: CARD_LINK,
		menu: [],
		person: { name: "Ada", image: null },
		...props,
	});
	app.use(router);
	app.component("RowMenu", { template: "<button data-menu />" });
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

describe("CardItem", () => {
	it("links to the record's address and shows its title, body, owner and time", async () => {
		const root = await mount({});
		const link = root.querySelector("a")!;

		expect(link.getAttribute("href")).toBe(CARD_LINK);
		expect(link.textContent).toContain("Plan");
		expect(link.textContent).toContain("Hello");
		expect(link.textContent).toContain("Ada");
		expect(link.textContent).toContain("3 days ago");
	});

	it("draws its title in the class the view gives it, else the default", async () => {
		const title = (root: HTMLElement) => root.querySelector("a > div")!.classList;
		expect(title(await mount({}))).toContain("text-ink-gray-9");
		const seen = title(await mount({ titleClass: "text-ink-gray-7" }));
		expect(seen).toContain("text-ink-gray-7");
		expect(seen).not.toContain("text-ink-gray-9");
	});

	it("draws no menu without actions", async () => {
		const root = await mount({});
		expect(root.querySelector("[aria-label='Row actions']")).toBeNull();
	});
});
