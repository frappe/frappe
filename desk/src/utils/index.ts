export function getRandom(len: number): string {
	let text = ""
	const possible = "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz"

	Array.from({ length: len }).forEach(() => {
		text += possible.charAt(Math.floor(Math.random() * possible.length))
	})

	return text
}

export function cloneObject<Type>(obj: object): Type {
	return JSON.parse(JSON.stringify(obj))
}
