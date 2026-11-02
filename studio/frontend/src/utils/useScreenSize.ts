import { reactive, computed, onMounted, onUnmounted } from "vue"

export function useScreenSize() {
	const MOBILE_BREAKPOINT = 576
	const TABLET_BREAKPOINT = 768
	// const DESKTOP_BREAKPOINT = 1024

	const size = reactive({
		width: window.innerWidth,
		height: window.innerHeight,
	})

	const currentBreakpoint = computed(() => {
		if (size.width < MOBILE_BREAKPOINT) {
			return "mobile"
		} else if (size.width < TABLET_BREAKPOINT) {
			return "tablet"
		}
		return "desktop"
	})

	const onResize = () => {
		size.width = window.innerWidth
		size.height = window.innerHeight
	}

	onMounted(() => {
		window.addEventListener("resize", onResize)
	})

	onUnmounted(() => {
		window.removeEventListener("resize", onResize)
	})

	return { size, currentBreakpoint }
}