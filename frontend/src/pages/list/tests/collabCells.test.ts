// The collaboration cells: avatar stacks, tag chips, the Document Status badge, the comment
// count and the Favourite star, whose click never follows the row's link.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, nextTick, type Component } from "vue";
import { seedRowParts } from "@/list/rowParts";
import { tagColor } from "../../record/panel/people";
import AvatarStackCell from "../AvatarStackCell.vue";
import CommentsCell from "../CommentsCell.vue";
import DocstatusCell from "../DocstatusCell.vue";
import FavouriteCell from "../FavouriteCell.vue";
import TagsCell from "../TagsCell.vue";

const api = vi.hoisted(() => ({ addFavourite: vi.fn(), removeFavourite: vi.fn() }));
vi.mock("@framework/ui/api", () => api);
vi.mock("frappe-ui", async (actual) => ({
	...(await actual<typeof import("frappe-ui")>()),
	Avatar: defineComponent({
		props: ["label"],
		setup: (props) => () => h("span", { "data-avatar": props.label }),
	}),
}));

const mounted: ReturnType<typeof createApp>[] = [];

afterEach(() => {
	for (const app of mounted.splice(0)) app.unmount();
	document.body.innerHTML = "";
});
beforeEach(() => vi.clearAllMocks());

async function render(cell: Component, props: Record<string, unknown>, onRowClick = vi.fn()) {
	const root = document.createElement("div");
	document.body.appendChild(root);
	const app = createApp(
		defineComponent({ render: () => h("a", { href: "#row", onClick: onRowClick }, [h(cell, props)]) })
	);
	app.provide("boot", { session: { user: { name: "me" } } });
	app.mount(root);
	mounted.push(app);
	await nextTick();
	return root;
}

describe("list collaboration cells", () => {
	it("draws Tags from the comma string in their record colours, ignoring the leading comma", async () => {
		const root = await render(TagsCell, { value: ",a,b" });
		expect(root.textContent?.replace(/\s/g, "")).toBe("ab");
		expect(root.querySelectorAll("[aria-hidden]")[0].className).toContain(tagColor("a"));
	});

	it("names Document Status and colours it as v1 does", async () => {
		const draft = await render(DocstatusCell, { value: 0 });
		const submitted = await render(DocstatusCell, { value: 1 });
		expect(draft.textContent).toBe("Draft");
		expect(draft.innerHTML).toContain("red");
		expect(submitted.textContent).toBe("Submitted");
		expect(submitted.innerHTML).toContain("blue");
	});

	it("shows 0 comments while no count is known", async () => {
		const root = await render(CommentsCell, { doctype: "ToDo", name: "x" });
		expect(root.textContent?.trim()).toBe("0");
	});

	it("names a lone user beside the avatar; a stack shows three avatars and counts the rest", async () => {
		seedRowParts("ToDo", { users: { "a@x": { full_name: "Ann Lee" } } }, []);
		const one = await render(AvatarStackCell, { value: '["a@x"]' });
		const two = await render(AvatarStackCell, { value: '["a@x","b@x"]' });
		const five = await render(AvatarStackCell, { value: '["a@x","b","c","d","e"]' });
		const bad = await render(AvatarStackCell, { value: "{oops" });
		expect(one.querySelectorAll("[data-avatar]")).toHaveLength(1);
		expect(one.textContent).toContain("Ann Lee");
		expect(two.querySelectorAll("[data-avatar]")).toHaveLength(2);
		expect(two.textContent).not.toContain("Ann Lee");
		expect(five.querySelectorAll("[data-avatar]")).toHaveLength(3);
		expect(five.textContent).toContain("+2");
		expect(bad.querySelector("[data-avatar]")).toBeNull();
	});

	it("stars in place and does not let the click reach the row link", async () => {
		api.addFavourite.mockResolvedValue({});
		const onRow = vi.fn();
		const root = await render(FavouriteCell, { doctype: "ToDo", name: "t1" }, onRow);
		root.querySelector<HTMLElement>("[data-favourite]")!.click();
		await nextTick();
		expect(api.addFavourite).toHaveBeenCalledWith("ToDo", "t1");
		expect(onRow).not.toHaveBeenCalled();
	});
});
