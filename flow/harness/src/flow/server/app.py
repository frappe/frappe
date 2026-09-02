"""The daemon's HTTP boundary: thin handlers over the Session verbs.

Assembly only — auth/origin middleware, error mapping, and the route groups
(`routes/sessions`, `routes/providers`, `routes/fs`). The run/stream ergonomics
are documented on `routes/sessions`."""

from __future__ import annotations

import logging
import os
import secrets
from collections.abc import Sequence
from dataclasses import replace
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.routing import APIRoute
from fastapi.staticfiles import StaticFiles

from flow import config as server_config
from flow.model.auth import AuthError
from flow.server.audit import AuditLog
from flow.server.policy import ServerPolicy
from flow.server.request_limits import RequestSizeLimit
from flow.server.routes.fs import create_fs_router
from flow.server.routes.providers import create_providers_router
from flow.server.routes.sessions import create_sessions_router
from flow.server.tenants import Tenant, load_tenants
from flow.server.utils.provider_auth import OAuthCoordinator
from flow.session.attachments import AttachmentError
from flow.session.session import ResumeError, RewindError, SessionConflict
from flow.session.skills import SkillError
from flow.session.store import PolicyError, SessionStore


def create_app(
	store: SessionStore,
	*,
	auth_token: str | None = None,
	tenants: Sequence[Tenant] = (),
	tenants_file: str | None = None,
	cors_origins: list[str] | None = None,
	webui_dir: str | None = None,
	system_append: str | None = None,
	policy: ServerPolicy | None = None,
) -> FastAPI:
	"""`system_append` is text the operator adds to every session's system prompt
	(`flow web --append-system-prompt`); it lands after whatever the client sends.
	`policy` gates tools and route groups; None means the permissive local default.
	`tenants` turns on multi-tenant mode: each tenant token authenticates as its
	site, and the request then acts on that site's own partition of `store`.
	`tenants_file` is the path those tenants came from: when a token matches
	nothing, the file is re-read, so sites added while the daemon runs (a signup
	bench) are picked up without a restart."""
	policy = policy or ServerPolicy()
	if policy.require_auth and not auth_token and not tenants:
		raise ValueError("this server policy requires auth; pass auth_token or tenants")
	# docs off: those routes would be reachable without a bearer beside the web UI
	app = FastAPI(title="flow server", version="0.1.0", docs_url=None, redoc_url=None, openapi_url=None)
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
	session_store_by_tenant = {
		tenant.site: store.for_site(tenant.site, tenant.allowed_roots) for tenant in tenants
	}

	def resolve_store(request: Request) -> SessionStore:
		site = getattr(request.state, "site", None)
		return session_store_by_tenant[site] if site else store

	tenants = list(tenants)
	tenants_mtime = _stat_mtime(tenants_file)

	def refresh_tenants() -> None:
		"""Re-read the tenants file so sites added while the daemon runs are picked
		up without a restart. Called only when a token matches nothing, so the steady
		state never stats the file; a broken file keeps the last good list."""
		nonlocal tenants, tenants_mtime
		if tenants_file is None:
			return
		mtime = _stat_mtime(tenants_file)
		if mtime is None or mtime == tenants_mtime:
			return
		try:
			fresh = load_tenants(tenants_file)
		except (OSError, ValueError) as error:
			logging.getLogger("flow").warning(
				"tenants file reload failed, keeping the last good list: %s", error
			)
			return
		fresh_by_site = {tenant.site: tenant for tenant in fresh}
		for old in tenants:
			new = fresh_by_site.get(old.site)
			if new is None or new.allowed_roots != old.allowed_roots:
				session_store_by_tenant.pop(old.site, None)  # rebuilt on next match, if any
		tenants = fresh
		tenants_mtime = mtime

	if auth_token or tenants:

		def match_tenant(supplied: str) -> Tenant | None:
			for tenant in tenants:
				if secrets.compare_digest(supplied.encode(), tenant.token.encode()):
					return tenant
			return None

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
				tenant = match_tenant(supplied)
				if tenant is None and tenants_file:
					refresh_tenants()
					tenant = match_tenant(supplied)
				if tenant is not None:
					if tenant.site not in session_store_by_tenant:
						# a site added after startup gets its partition on first use
						session_store_by_tenant[tenant.site] = store.for_site(
							tenant.site, tenant.allowed_roots
						)
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

	# the credential store is daemon-wide, so no site token may manage it
	providers_policy = replace(policy, providers_api=False) if tenants else policy
	routers = (
		create_providers_router(store.credential_store, oauth, policy=providers_policy),
		create_fs_router(resolve_store, policy=policy),
		create_sessions_router(resolve_store, system_append=system_append, policy=policy),
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


def _stat_mtime(path: str | None) -> int | None:
	if not path:
		return None
	try:
		return os.stat(path).st_mtime_ns
	except OSError:
		return None
