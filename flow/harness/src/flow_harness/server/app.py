"""The daemon's HTTP boundary: thin handlers over the Session verbs.

Assembly only — auth/origin middleware, error mapping, and the route groups
(`routes/sessions`, `routes/providers`, `routes/fs`, `routes/skills`, `routes/tools`,
`routes/settings`, `routes/workspaces`). The run/stream ergonomics are documented on
`routes/sessions`."""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager, nullcontext
from dataclasses import replace
from functools import partial
from typing import Any
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles
from starlette.types import Lifespan

from flow_harness import config as server_config
from flow_harness.model.auth import AuthError
from flow_harness.server.audit import AuditLog
from flow_harness.server.policy import ServerPolicy
from flow_harness.server.request_limits import RequestSizeLimit
from flow_harness.server.routes.fs import create_fs_router
from flow_harness.server.routes.providers import create_providers_router
from flow_harness.server.routes.sessions import create_sessions_router
from flow_harness.server.routes.settings import create_settings_router
from flow_harness.server.routes.skills import create_skills_router
from flow_harness.server.routes.tools import create_tools_router
from flow_harness.server.routes.workspaces import create_workspaces_router
from flow_harness.server.tenants import SITE_HEADER, Tenant, TenantTemplate
from flow_harness.server.utils.provider_auth import OAuthCoordinator
from flow_harness.session.attachments import AttachmentError
from flow_harness.session.session import ResumeError, RewindError, SessionConflict
from flow_harness.session.skills import SkillError
from flow_harness.session.store import PolicyError, SessionStore


def create_app(
	store: SessionStore,
	*,
	auth_token: str | None = None,
	tenants: TenantTemplate | None = None,
	cors_origins: list[str] | None = None,
	webui_dir: str | None = None,
	system_append: str | None = None,
	policy: ServerPolicy | None = None,
	lifespan: Lifespan[FastAPI] | None = None,
) -> FastAPI:
	"""`system_append` is text the operator adds to every session's system prompt
	(`flow web --append-system-prompt`); it lands after whatever the client sends.
	`policy` gates tools and route groups; None means the permissive local default.
	`tenants` turns on multi-tenant mode: a request names its site in `X-Flow-Site`
	and acts on that site's own partition of `store`."""
	policy = policy or ServerPolicy()
	if policy.require_auth and not auth_token and tenants is None:
		raise ValueError("this server policy requires auth; pass auth_token or tenants")

	@asynccontextmanager
	async def serve_lifespan(app: FastAPI) -> AsyncIterator[Any]:
		async with lifespan(app) if lifespan else nullcontext() as state:
			# the last daemon may have stopped before a client confirmed a run's end
			store.report_unconfirmed_run_ends()
			if tenants is not None:
				for site in tenants.sites():
					try:
						if (tenant := tenants.lookup(site)) is not None:
							partition_for(tenant)
					except (OSError, ValueError) as error:  # one broken site must not stop the rest
						logging.getLogger("flow").warning("cannot open site %s: %s", site, error)
			yield state

	# docs off: those routes would be reachable without a bearer beside the web UI
	app = FastAPI(
		title="flow server",
		version="0.1.0",
		docs_url=None,
		redoc_url=None,
		openapi_url=None,
		lifespan=serve_lifespan,
	)
	oauth = OAuthCoordinator(store.credential_store)

	origins = cors_origins if cors_origins is not None else server_config.CORS_ORIGINS
	if origins:
		app.add_middleware(
			CORSMiddleware,
			allow_origins=origins,
			allow_methods=["*"],
			allow_headers=["Authorization", "Content-Type"],
		)

	if policy.max_request_bytes is not None:
		# registered before auth, so the auth middleware wraps (and precedes) it
		app.add_middleware(RequestSizeLimit, max_bytes=policy.max_request_bytes)

	@app.exception_handler(SessionConflict)
	@app.exception_handler(ResumeError)
	@app.exception_handler(RewindError)
	async def state_conflict(request: Request, error: Exception):
		"""A session verb refused by the session's current state answers 409."""
		return JSONResponse({"detail": str(error)}, status_code=409)

	@app.exception_handler(AttachmentError)
	@app.exception_handler(SkillError)
	@app.exception_handler(PolicyError)
	async def input_error(request: Request, error: Exception):
		"""PolicyError also fires on load, when a stored session no longer passes a
		tightened fence — still the caller's 400, never a 500."""
		return JSONResponse({"detail": str(error)}, status_code=400)

	@app.exception_handler(AuthError)
	async def auth_error(request: Request, error: AuthError):
		"""Provider setup problems are client errors, never 500s."""
		return JSONResponse({"detail": str(error)}, status_code=400)

	# path prefixes of all API routes, e.g. "/sessions"
	api_roots: set[str] = set()

	# one isolated store per site; a request only ever sees its own site's store
	partitions: dict[str, SessionStore] = {}

	def partition_for(tenant: Tenant) -> SessionStore:
		"""The site's partition, made on first use and again if a reinstall deleted its folder."""
		partition = partitions.get(tenant.site)
		if partition is None or not os.path.isdir(partition.sessions_dir):
			partition = partitions[tenant.site] = store.for_site(
				tenant.site,
				tenant.allowed_roots,
				tenant.callback_hosts,
				ignore_hidden_files=tenant.ignore_hidden_files,
				data_dir=tenant.data_dir,
				extensions=tenant.extensions,
				callback_headers=tenant.callback_headers,
				relocate=partial(tenants.path_for_site, tenant.site) if tenants is not None else None,
			)
			partition.report_unconfirmed_run_ends()
		return partition

	def resolve_store(request: Request) -> SessionStore:
		site = getattr(request.state, "site", None)
		return partitions[site] if site else store

	if auth_token or tenants is not None:

		@app.middleware("http")
		async def authenticate(request: Request, call_next):
			if request.url.path == "/healthz":
				return await call_next(request)
			if request.method == "OPTIONS":
				return await call_next(request)  # preflights carry no Authorization
			# the static shell must load before the page can send a bearer
			if (
				webui_dir
				and request.method in ("GET", "HEAD")
				and "/" + request.url.path.split("/")[1] not in api_roots
			):
				return await call_next(request)
			scheme, _, supplied = request.headers.get("Authorization", "").partition(" ")
			if scheme.lower() == "bearer":
				if auth_token and secrets.compare_digest(supplied.encode(), auth_token.encode()):
					return await call_next(request)
				tenant = tenants.lookup(request.headers.get(SITE_HEADER, "")) if tenants is not None else None
				if tenant is not None and secrets.compare_digest(supplied.encode(), tenant.token.encode()):
					partition_for(tenant)
					request.state.site = tenant.site  # scopes this request to the site
					return await call_next(request)
			return JSONResponse({"detail": "unauthorized"}, status_code=401)
	else:
		# Tokenless mode trusts the local machine, so browsers are the threat:
		# DNS rebinding forges a loopback Host, cross-site requests a foreign Origin.
		allowed_origins = set(origins or [])
		loopback_hosts = ("127.0.0.1", "localhost", "::1")

		@app.middleware("http")
		async def guard_browser_boundaries(request: Request, call_next):
			server = request.scope.get("server")
			if server is None or server[1] is None:
				return await call_next(request)  # unix socket
			if server[0] in loopback_hosts and request.url.hostname not in loopback_hosts:
				return JSONResponse({"detail": "invalid host header"}, status_code=400)
			origin = request.headers.get("origin")
			if origin and origin not in allowed_origins:
				if urlsplit(origin).hostname not in loopback_hosts:
					return JSONResponse({"detail": "cross-origin request refused"}, status_code=403)
			return await call_next(request)

	if policy.audit_log:
		# registered last = outermost, so rows carry the auth verdict and the site
		audit = AuditLog(os.path.join(store.data_dir, "audit.jsonl"))

		@app.middleware("http")
		async def audit_sensitive(request: Request, call_next):
			response = await call_next(request)
			if request.method not in ("GET", "HEAD", "OPTIONS") or response.status_code in (401, 403):
				audit.record(
					method=request.method,
					path=request.url.path,
					status=response.status_code,
					site=getattr(request.state, "site", None),
				)
			return response

	@app.get("/healthz")
	async def healthz():
		return {"ok": True}

	# the credential store, the settings file and the home folder (the default workspace's) are
	# daemon-wide, so no site token may manage them
	providers_policy = (
		replace(policy, providers_api=False, settings_api=False, workspaces_api=False)
		if tenants is not None
		else policy
	)
	routers = (
		create_providers_router(store.credential_store, oauth, policy=providers_policy),
		create_fs_router(resolve_store, policy=policy),
		create_sessions_router(resolve_store, system_append=system_append, policy=policy),
		create_skills_router(resolve_store, policy=policy),
		create_tools_router(resolve_store, policy=policy),
		create_settings_router(policy=providers_policy),
		create_workspaces_router(resolve_store, policy=providers_policy),
	)
	for router in routers:
		app.include_router(router)
		api_roots.update(
			"/" + route.path.split("/")[1] for route in router.routes if isinstance(route, APIRoute)
		)

	if webui_dir:
		# registered last, so every API route above wins; "/" serves index.html
		app.mount("/", StaticFiles(directory=webui_dir, html=True), name="webui")

	return app
