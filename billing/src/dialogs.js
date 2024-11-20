import { Dialog, ErrorMessage } from 'frappe-ui'
import { reactive, ref, h } from 'vue'

let dialogs = ref([])

export let Dialogs = {
	name: 'Dialogs',
	render() {
		return dialogs.value.map((dialog) => {
			return h(
				Dialog,
				{
					options: dialog,
					modelValue: dialog.show,
					'onUpdate:modelValue': (val) => (dialog.show = val),
					onClose: () => {
						let index = dialogs.value.indexOf(dialog)
						dialogs.value.splice(index, 1)
						dialog.onClose && dialog.onClose()
					},
				},
				{
					'body-content': () => {
						return [
							dialog.message &&
								h('p', { class: 'text-p-base text-gray-700' }, dialog.message),
							dialog.html && h('div', { innerHTML: dialog.html }),
							dialog.component && h(dialog.component),
							h(ErrorMessage, { class: 'mt-2', message: dialog.error }),
						]
					},
				}
			)
		})
	},
}

export function createDialog(dialogOptions) {
	let dialog = reactive(dialogOptions)
	dialog.key = 'dialog-' + dialogs.value.length
	dialog.show = false
	setTimeout(() => (dialog.show = true), 0)
	dialogs.value.push(dialog)
}
