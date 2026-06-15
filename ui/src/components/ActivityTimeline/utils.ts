import { dayjsLocal } from 'frappe-ui'
import { ref, type Ref } from 'vue'

export const dateTooltipFormat = 'ddd, MMM D, YYYY h:mm A'

export function dateFormat(date: string, format = dateTooltipFormat) {
	if (!date) return ''
	return dayjsLocal(date).format(format)
}

export function timeAgo(date: string) {
	if (!date) return ''
	return dayjsLocal(date).fromNow()
}

const COLOR_PROPS = new Set(['color', 'background', 'background-color', 'border-color'])

// Strip color-related inline styles + bgcolor/color attrs so iframe CSS controls colors.
export function stripEmailColors(html: string): string {
	if (!html) return html
	const div = document.createElement('div')
	div.innerHTML = html

	div.querySelectorAll('[style]').forEach((el) => {
		const styles = el.getAttribute('style') || ''
		const filtered = styles
			.split(';')
			.map((s) => s.trim())
			.filter((s) => {
				if (!s) return false
				const prop = s.split(':')[0].trim().toLowerCase()
				return !COLOR_PROPS.has(prop)
			})
			.join('; ')
		if (filtered) el.setAttribute('style', filtered)
		else el.removeAttribute('style')
	})

	div.querySelectorAll('[bgcolor]').forEach((el) => el.removeAttribute('bgcolor'))
	div.querySelectorAll('font[color]').forEach((el) => el.removeAttribute('color'))

	return div.innerHTML
}

// Reactive mirror of <html data-theme>. Lazy singleton: the MutationObserver
// is created on first use, not at import time, and shared by all callers.
// (frappe-ui's useTheme is a controller — it writes data-theme/localStorage —
// while this only observes whatever the host app set.)
let dataTheme: Ref<string> | null = null

export function useDataTheme(): Ref<string> {
	if (!dataTheme) {
		const current = () => document.documentElement.getAttribute('data-theme') || 'light'
		dataTheme = ref(current())
		new MutationObserver(() => {
			dataTheme!.value = current()
		}).observe(document.documentElement, {
			attributes: true,
			attributeFilter: ['data-theme'],
		})
	}
	return dataTheme
}

// Split a comma separated recipients string, respecting quoted display names
// e.g. '"Doe, John" <john@x.com>, jane@x.com'
export function splitRecipients(
	field: string | string[],
	valuesToExclude: string[] = [],
): string[] {
	let arr: string[] = []
	let current = ''
	let inQuotes = false
	if (typeof field === 'string') {
		for (const char of field) {
			if (char === '"') {
				inQuotes = !inQuotes
				current += char
			} else if (char === ',' && !inQuotes) {
				arr.push(current.trim())
				current = ''
			} else {
				current += char
			}
		}
		if (current) arr.push(current.trim())
	} else {
		arr = field || []
	}
	return arr.filter(Boolean).filter((item) => !valuesToExclude.includes(item))
}
