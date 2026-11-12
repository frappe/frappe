// A tag's dot class comes from the colour stored on its Tag, gray without one.
import { describe, expect, it, vi } from "vitest";
import { runMethod } from "@framework/ui/api";
import { colorClass, seedTagColors, TAG_COLOR_NAMES, TAG_COLORS, tagColorClass } from "@/tagColors";
import { recolourTag } from "@/tagApi";

vi.mock("@framework/ui/api", () => ({ runMethod: vi.fn(async () => "Blue") }));

describe("tag colours", () => {
	it("offers Helpdesk's colour names, Gray first", () => {
		expect(TAG_COLOR_NAMES).toEqual([
			"Gray", "Black", "Blue", "Green", "Red", "Pink", "Orange",
			"Amber", "Yellow", "Cyan", "Teal", "Violet", "Purple",
		]);
	});

	it("draws a tag in its stored colour, and gray when it has none or an unknown one", () => {
		seedTagColors({ urgent: "Red", odd: "Mauve", blank: null });
		expect(tagColorClass("urgent")).toBe("bg-surface-red-6");
		expect(tagColorClass("odd")).toBe(TAG_COLORS.Gray);
		expect(tagColorClass("blank")).toBe(TAG_COLORS.Gray);
		expect(tagColorClass("never-read")).toBe(TAG_COLORS.Gray);
		expect(colorClass("Black")).toBe("bg-surface-gray-10");
	});

	it("ignores a part that is not a map", () => {
		seedTagColors(undefined);
		seedTagColors(["Red"]);
		expect(tagColorClass("0")).toBe(TAG_COLORS.Gray);
	});

	it("recolours a tag through set_tag_color and repaints its chips", async () => {
		seedTagColors({ repaint: "Red" });
		await recolourTag("repaint", "Blue");
		expect(runMethod).toHaveBeenCalledWith("frappe.desk.doctype.tag.tag.set_tag_color", {
			tag: "repaint",
			color: "Blue",
		}, { nullable: true });
		expect(tagColorClass("repaint")).toBe(TAG_COLORS.Blue);
	});
});
