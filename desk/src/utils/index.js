export function get_random(len) {
	let text = ""
	const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

	Array.from({ length: len }).forEach(() => {
		text += possible.charAt(Math.floor(Math.random() * possible.length))
	})

	return text
}
