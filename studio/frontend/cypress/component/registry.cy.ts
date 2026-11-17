import { ref } from "vue"
import { createRegistry, type RegistryItem } from "@/utils/createRegistry"

const names = (items: RegistryItem[]) => items.map((item) => item.name)

describe("createRegistry", () => {
	it("orders items by registration, then by before and after anchors", () => {
		const registry = createRegistry<RegistryItem>()
		registry.register({ name: "a" })
		registry.register({ name: "c" })
		registry.register({ name: "b", after: "a" })
		registry.register({ name: "start", before: "a" })
		expect(names(registry.all.value)).to.deep.equal(["start", "a", "b", "c"])
	})

	it("puts an item first or last when its anchor is not registered", () => {
		const registry = createRegistry<RegistryItem>()
		registry.register({ name: "a" })
		registry.register({ name: "first", before: "missing" })
		registry.register({ name: "last", after: "missing" })
		expect(names(registry.all.value)).to.deep.equal(["first", "a", "last"])
	})

	it("keeps a re-registered item in its slot unless it brings an anchor", () => {
		const registry = createRegistry<RegistryItem>()
		registry.register({ name: "a" })
		registry.register({ name: "b" })
		registry.register({ name: "a" })
		expect(names(registry.all.value)).to.deep.equal(["a", "b"])
		registry.register({ name: "a", after: "b" })
		expect(names(registry.all.value)).to.deep.equal(["b", "a"])
	})

	it("filters visible by a live condition and keeps hidden items in all", () => {
		const show = ref(false)
		const registry = createRegistry<RegistryItem>()
		registry.register({ name: "a" })
		registry.register({ name: "b", condition: () => show.value })
		expect(names(registry.visible.value)).to.deep.equal(["a"])
		expect(names(registry.all.value)).to.deep.equal(["a", "b"])
		show.value = true
		expect(names(registry.visible.value)).to.deep.equal(["a", "b"])
	})

	it("does not let a replaced registration unregister its replacement", () => {
		const registry = createRegistry<RegistryItem & { label: string }>()
		const unregisterOld = registry.register({ name: "a", label: "old" })
		registry.register({ name: "a", label: "new" })
		unregisterOld()
		expect(registry.all.value.map((item) => item.label)).to.deep.equal(["new"])
	})
})
