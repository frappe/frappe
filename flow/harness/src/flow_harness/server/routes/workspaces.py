"""The web UI's workspaces: named folders its sidebar groups chats under (see
`session/workspaces`). Off with the `workspaces_api` policy switch, and in multi-tenant mode."""

from __future__ import annotations

import asyncio
from collections.abc import Callable

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel, ConfigDict, Field

from flow_harness.server.policy import ServerPolicy, gate
from flow_harness.session.store import SessionStore


class WorkspaceAdd(BaseModel):
	model_config = ConfigDict(extra="forbid")

	path: str = Field(min_length=1)


class WorkspaceRename(BaseModel):
	model_config = ConfigDict(extra="forbid")

	path: str = Field(min_length=1)
	name: str = Field(min_length=1, max_length=200)


def create_workspaces_router(
	resolve_store: Callable[[Request], SessionStore], *, policy: ServerPolicy | None = None
) -> APIRouter:
	"""`resolve_store` picks the store a request acts on — the authenticated site's
	partition in multi-tenant mode, else the daemon's root store."""
	policy = policy or ServerPolicy()
	router = APIRouter(dependencies=gate(policy.workspaces_api))

	# all in a thread: the first listing reads every chat, holding the lock the rest wait on
	@router.get("/workspaces")
	async def list_workspaces(request: Request):
		return {"workspaces": await asyncio.to_thread(resolve_store(request).workspaces.list)}

	@router.post("/workspaces")
	async def add_workspace(request: Request, req: WorkspaceAdd):
		try:
			workspace = await asyncio.to_thread(resolve_store(request).workspaces.add, req.path)
		except ValueError as e:
			raise HTTPException(status_code=400, detail=str(e)) from None
		return {"workspace": workspace}

	@router.patch("/workspaces")
	async def rename_workspace(request: Request, req: WorkspaceRename):
		name = req.name.strip()
		if not name:
			raise HTTPException(status_code=400, detail="name cannot be empty")
		workspace = await asyncio.to_thread(resolve_store(request).workspaces.rename, req.path, name)
		if workspace is None:
			raise HTTPException(status_code=404, detail="workspace not found")
		return {"workspace": workspace}

	@router.delete("/workspaces")
	async def remove_workspace(request: Request, path: str):
		"""Off the list only: the folder and its chats stay."""
		if not await asyncio.to_thread(resolve_store(request).workspaces.remove, path):
			raise HTTPException(status_code=404, detail="workspace not found")
		return {"status": "removed"}

	return router
