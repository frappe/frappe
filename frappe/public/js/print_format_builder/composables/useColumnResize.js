import { onUnmounted } from "vue";

export function useColumnResize() {
	let end = null;

	function start(handle, active_class, on_move) {
		handle.classList.add(active_class);
		document.body.classList.add("pfb-col-resizing");
		const on_up = () => {
			document.removeEventListener("pointermove", on_move);
			document.removeEventListener("pointerup", on_up);
			document.removeEventListener("pointercancel", on_up);
			handle.classList.remove(active_class);
			document.body.classList.remove("pfb-col-resizing");
			end = null;
		};
		document.addEventListener("pointermove", on_move);
		document.addEventListener("pointerup", on_up);
		document.addEventListener("pointercancel", on_up);
		end = on_up;
	}

	onUnmounted(() => end?.());

	return { start };
}
