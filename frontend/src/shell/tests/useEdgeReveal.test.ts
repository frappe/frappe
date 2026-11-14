// The floating rail's reveal: the edge band, the end side's wait, the stay band, focus and Escape.
import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { createApp, defineComponent, h, ref } from "vue";
import { END_WAIT, STAY_BAND, useEdgeReveal } from "../useEdgeReveal";

function mountReveal(side: "left" | "right", scrollbarSide: boolean) {
	const rail = document.createElement("div");
	const inner = document.createElement("button");
	rail.append(inner);
	document.body.append(rail);
	let reveal!: ReturnType<typeof useEdgeReveal>;
	const app = createApp(
		defineComponent({
			setup() {
				reveal = useEdgeReveal({ side: () => side, scrollbarSide: () => scrollbarSide, rail: ref(rail) });
				return () => h("div");
			},
		})
	);
	app.mount(document.createElement("div"));
	return { reveal, rail, inner, stop: () => (app.unmount(), rail.remove()) };
}

function move(x: number, init: PointerEventInit = {}, target: Element | Document = document) {
	const event = new MouseEvent("pointermove", { clientX: x, bubbles: true, ...init });
	target.dispatchEvent(event);
}

describe("useEdgeReveal", () => {
	beforeEach(() => {
		vi.useFakeTimers();
		Object.defineProperty(document.documentElement, "clientWidth", { value: 1000, configurable: true });
	});
	afterEach(() => vi.useRealTimers());

	it("opens at once on the start side, at the left edge or the right", () => {
		const left = mountReveal("left", false);
		move(5);
		expect(left.reveal.open.value).toBe(false);
		move(0);
		expect(left.reveal.open.value).toBe(true);
		left.stop();

		const right = mountReveal("right", false);
		move(999);
		expect(right.reveal.open.value).toBe(true);
		right.stop();
	});

	it("waits 200 ms on the end side, and a press, leaving the band or a thumb cancels", () => {
		const { reveal, stop } = mountReveal("right", true);
		move(999);
		vi.advanceTimersByTime(END_WAIT - 1);
		expect(reveal.open.value).toBe(false);
		vi.advanceTimersByTime(1);
		expect(reveal.open.value).toBe(true);
		reveal.close();

		move(999);
		document.dispatchEvent(new MouseEvent("pointerdown"));
		vi.advanceTimersByTime(END_WAIT);
		expect(reveal.open.value).toBe(false);

		move(999);
		move(900);
		vi.advanceTimersByTime(END_WAIT);
		expect(reveal.open.value).toBe(false);

		const thumb = document.createElement("div");
		thumb.dataset.slot = "scroll-area-thumb";
		document.body.append(thumb);
		move(999, {}, thumb);
		vi.advanceTimersByTime(END_WAIT);
		expect(reveal.open.value).toBe(false);

		move(999, { buttons: 1 });
		vi.advanceTimersByTime(END_WAIT);
		expect(reveal.open.value).toBe(false);
		thumb.remove();
		stop();
	});

	it("stays within the stay band and over the rail, and closes beyond it", () => {
		const { reveal, rail, inner, stop } = mountReveal("left", false);
		move(0);
		move(STAY_BAND);
		expect(reveal.open.value).toBe(true);
		move(STAY_BAND + 1, {}, rail);
		expect(reveal.open.value).toBe(true);
		move(STAY_BAND + 1);
		expect(reveal.open.value).toBe(false);

		move(0);
		inner.setAttribute("aria-expanded", "true");
		move(STAY_BAND + 50);
		expect(reveal.open.value).toBe(true);
		inner.removeAttribute("aria-expanded");
		move(STAY_BAND + 50);
		expect(reveal.open.value).toBe(false);
		stop();
	});

	it("opens on focus in the rail, and Escape closes it and moves focus to main", () => {
		const main = document.createElement("main");
		main.tabIndex = -1;
		document.body.append(main);
		const { reveal, inner, stop } = mountReveal("left", false);
		inner.focus();
		expect(reveal.open.value).toBe(true);
		document.dispatchEvent(new KeyboardEvent("keydown", { key: "Escape" }));
		expect(reveal.open.value).toBe(false);
		expect(document.activeElement).toBe(main);
		main.remove();
		stop();
	});

	it("does not open while a button is held, and a press away from the rail closes it", () => {
		const { reveal, rail, stop } = mountReveal("left", false);
		move(0, { buttons: 1 });
		expect(reveal.open.value).toBe(false);

		move(0);
		expect(reveal.open.value).toBe(true);
		rail.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
		expect(reveal.open.value).toBe(true);
		document.body.dispatchEvent(new MouseEvent("pointerdown", { bubbles: true }));
		expect(reveal.open.value).toBe(false);
		stop();
	});
});
