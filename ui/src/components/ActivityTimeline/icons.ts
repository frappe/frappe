import { h } from 'vue'

// Tailwind's JIT only emits a `lucide-*` mask class when that exact string
// appears in scanned source — a dynamic `'lucide-' + name` is invisible to it.
// Keep the full literal class names here (this file is in the tailwind content
// globs) so the gutter icons actually render.
export const LUCIDE_ICON_CLASS: Record<string, string> = {
	heart: 'lucide-heart',
	paperclip: 'lucide-paperclip',
	'trash-2': 'lucide-trash-2',
	'git-branch': 'lucide-git-branch',
	info: 'lucide-info',
	lock: 'lucide-lock',
	eye: 'lucide-eye',
}

const svgAttrs = {
	width: '16',
	height: '16',
	viewBox: '0 0 16 16',
	fill: 'none',
	xmlns: 'http://www.w3.org/2000/svg',
}

// helpdesk's DotIcon — a plain filled dot, used for assignment timeline entries
export const DotIcon = () =>
	h('svg', svgAttrs, [
		h('circle', { cx: '8', cy: '8', r: '3.5', fill: 'currentColor' }),
	])

export const CommentIcon = () =>
	h('svg', svgAttrs, [
		h('path', {
			'fill-rule': 'evenodd',
			'clip-rule': 'evenodd',
			d: 'M8 2.5C4.2911 2.5 1.5 4.84419 1.5 7.5C1.5 9.14452 2.54729 10.6518 4.25112 11.5816C4.50048 11.7177 4.758 12.0041 4.7326 12.4082C4.71107 12.7508 4.61659 13.2533 4.47175 13.6657C4.44071 13.7541 4.40789 13.8389 4.37434 13.9195C4.62005 13.8524 4.91964 13.7411 5.26646 13.5579C5.48882 13.4404 5.69385 13.2901 5.9102 13.1207C5.95058 13.089 5.9922 13.056 6.03481 13.0222C6.20816 12.8848 6.39803 12.7342 6.58835 12.6102C6.7875 12.4803 7.01146 12.4447 7.20831 12.4631C7.46767 12.4875 7.73186 12.5 8 12.5C11.7089 12.5 14.5 10.1558 14.5 7.5C14.5 4.84419 11.7089 2.5 8 2.5ZM0.5 7.5C0.5 4.08068 3.97691 1.5 8 1.5C12.0231 1.5 15.5 4.08068 15.5 7.5C15.5 10.9193 12.0231 13.5 8 13.5C7.70158 13.5 7.40709 13.4861 7.11751 13.459C6.97583 13.5528 6.83777 13.6621 6.67569 13.7905C6.62832 13.828 6.5789 13.8671 6.52674 13.908C6.30071 14.085 6.03818 14.2812 5.73354 14.4421C4.73389 14.9702 3.9948 15.0302 3.62977 15.0147C3.39759 15.0048 3.20936 14.8646 3.12194 14.6754C3.03801 14.4938 3.05143 14.2816 3.15736 14.1099C3.24804 13.963 3.40655 13.6808 3.52825 13.3343C3.62961 13.0457 3.70134 12.6878 3.72712 12.4347C1.81521 11.3748 0.5 9.58517 0.5 7.5Z',
			fill: 'currentColor',
		}),
	])
