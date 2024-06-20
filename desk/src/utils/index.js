export function getRandom(len) {
	let text = ""
	const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

	Array.from({ length: len }).forEach(() => {
		text += possible.charAt(Math.floor(Math.random() * possible.length))
	})

	return text
}

export function cloneObject(obj) {
	return JSON.parse(JSON.stringify(obj))
}
