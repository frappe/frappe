export class LRUCache<T> {
	max: number
	cache: Map<string, T>
	constructor(max = 10) {
		this.max = max
		this.cache = new Map<string, T>()
	}

	get(key: string): T | undefined {
		const item = this.cache.get(key)
		if (item !== undefined) {
			// Move to end (most recently used)
			this.cache.delete(key)
			this.cache.set(key, item)
		}
		return item
	}

	set(key: string, val: T) {
		// refresh key
		if (this.cache.has(key))
			this.cache.delete(key)
		// evict oldest
		else if (this.cache.size === this.max)
			this.cache.delete(this.first()!)
		this.cache.set(key, val)
	}

	first() {
		return this.cache.keys().next().value
	}

	clear() {
		this.cache.clear()
	}
}