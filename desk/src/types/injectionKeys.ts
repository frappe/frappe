import type { InjectionKey } from "vue"
import type { ModuleSidebarItem, UpdateSidebarItemAction } from "@/types"

const updateSidebarItemFnKey = Symbol("updateSidebarItem") as InjectionKey<
	(item: ModuleSidebarItem, action: UpdateSidebarItemAction) => void
>

const fetchListFnKey = Symbol("fetchList") as InjectionKey<(updateCount?: boolean) => Promise<void>>

const renderListFnKey = Symbol("renderList") as InjectionKey<() => Promise<void>>

export { updateSidebarItemFnKey, fetchListFnKey, renderListFnKey }
