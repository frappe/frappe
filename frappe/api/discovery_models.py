from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict


class DiscoveryModel(BaseModel):
	model_config = ConfigDict(extra="forbid")


class ResourceCounts(DiscoveryModel):
	methods: int


class DiscoveryLinks(DiscoveryModel):
	self: str
	search: str
	methods: str
	method: str


class MethodSummary(DiscoveryModel):
	path: str
	allow_guest: bool | None = None
	description: str | None = None


class SearchEntry(DiscoveryModel):
	type: Literal["method"]
	path: str | None = None
	allow_guest: bool | None = None
	description: str | None = None


class RootDiscovery(DiscoveryModel):
	type: Literal["discovery"]
	resources: ResourceCounts
	links: DiscoveryLinks
	module: str | None = None


class SearchDiscovery(DiscoveryModel):
	query: str
	results: list[SearchEntry]


class MethodIndexDiscovery(DiscoveryModel):
	type: Literal["method_index"]
	methods: list[MethodSummary]


class MethodParameter(DiscoveryModel):
	name: str
	required: bool
	default: Any = None
	type: str | None = None


class MethodDiscovery(DiscoveryModel):
	type: Literal["method"]
	path: str
	name: str
	http_methods: list[str]
	params: list[MethodParameter]
	endpoint: str
	docstring: str | None = None
	allow_guest: bool | None = None
