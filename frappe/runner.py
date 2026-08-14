# Copyright (c) 2026, Frappe Technologies Pvt. Ltd. and contributors
# License: MIT. See LICENSE
"""Frappe runner: the web app, realtime, the jobs, and the scheduler in one process.
SIGHUP restarts, SIGTERM and SIGINT stop. All the signals support a graceful shutdown of the web app and the jobs.
"""

from __future__ import annotations

import argparse
import asyncio
import logging
import os
import signal
import sys
import threading
import time
from contextlib import contextmanager
from dataclasses import dataclass

from rq.timeouts import TimerDeathPenalty
from rq.worker import StopRequested

import frappe
from frappe.utils.background_jobs import FrappeWorkerNoFork, get_queue_list, get_redis_conn
from frappe.utils.scheduler import start_scheduler

logger = logging.getLogger("frappe.runner")

# The time that the job worker stays in one blocking dequeue. After this time the
# worker looks at the stop flag again.
JOB_POLL_SECONDS = 5
RESTART_CHECK_SECONDS = 10
SOCKETIO_PATH = "/socket.io"
# No user waits for these requests. Thus they do not increase a count, and they do
# not make the process busy.
HEALTH_CHECK_PATHS = ("/api/method/ping",)


@dataclass(frozen=True)
class Config:
	"""The options of the runner. main() makes it from the command line."""

	host: str
	port: int
	queue: str | None
	verbose: bool
	serve_assets: bool
	web_threads: int
	job_threads: int
	restart_after_requests: int
	restart_after_jobs: int
	restart_idle_seconds: float
	request_drain_seconds: float
	job_drain_seconds: float

	@property
	def queue_names(self) -> list[str] | None:
		return [name.strip() for name in self.queue.split(",")] if self.queue else None

	@property
	def has_restart_limit(self) -> bool:
		return bool(self.restart_after_requests or self.restart_after_jobs)


class WebServer:
	"""Uvicorn and the ASGI app of frappe."""

	def __init__(self, config: Config, traffic: Traffic):
		import uvicorn

		self.app = TrafficMiddleware.load(config, traffic)
		self.server = uvicorn.Server(
			uvicorn.Config(
				self.app,
				host=config.host,
				port=config.port,
				log_config=None,
				access_log=False,
				timeout_graceful_shutdown=config.request_drain_seconds,
			)
		)
		self.handle_exit = self.server.handle_exit

	def serve(self, on_signal) -> None:
		"""Run the server until a signal comes. Uvicorn sends its signals to on_signal."""
		self.server.handle_exit = on_signal
		self.server.run()

	def stop(self, sig, frame=None) -> None:
		self.handle_exit(sig, frame)

	def close_realtime(self) -> None:
		self.app.close_realtime()


class TrafficMiddleware:
	"""The ASGI app of the runner. It counts the web requests and the realtime
	requests separately, and it disconnects the realtime clients at shutdown."""

	def __init__(self, app, traffic: Traffic):
		self.app = app
		self.traffic = traffic
		self.loop = None

	@classmethod
	def load(cls, config: Config, traffic: Traffic) -> TrafficMiddleware:
		"""Initialize frappe and get its ASGI app."""
		if config.serve_assets:
			os.environ["FRAPPE_SERVE_ASSETS"] = "1"
		if config.web_threads:
			os.environ["FRAPPE_WEB_THREADS"] = str(config.web_threads)

		# Do this before the import of frappe.asgi. That module reads
		# common_site_config to know if it must add realtime, and it reads
		# FRAPPE_SERVE_ASSETS to know if it must send the static files. frappe.app also
		# needs an initialized frappe.
		frappe.init(site="")

		from frappe.asgi import application
		from frappe.realtime.config import get_config

		if not get_config().embedded:
			logger.warning('socketio_backend is not "python-embedded": the runner serves only the web app')

		return cls(application, traffic)

	async def __call__(self, scope, receive, send):
		if scope["type"] == "lifespan":
			self.loop = asyncio.get_running_loop()
			await self.app(scope, receive, send)
		elif scope["type"] == "websocket" or scope["path"].startswith(SOCKETIO_PATH):
			self.traffic.count("realtime")
			await self.app(scope, receive, send)
		elif scope["path"] in HEALTH_CHECK_PATHS:
			await self.app(scope, receive, send)
		else:
			await self.serve_web(scope, receive, send)

	async def serve_web(self, scope, receive, send):
		recorder = StatusRecorder(send)
		with self.traffic.busy():
			try:
				await self.app(scope, receive, recorder)
			finally:
				self.traffic.count_web(recorder.status)

	def close_realtime(self) -> None:
		"""Disconnect the realtime clients from a different thread.

		An open long-poll request of a client stops the shutdown of uvicorn until
		engine.io gets a timeout. The web requests continue to their end.
		"""
		sio = getattr(self.app, "engineio_server", None)
		if sio is None or self.loop is None:
			return
		asyncio.run_coroutine_threadsafe(self._close_realtime(sio), self.loop)

	async def _close_realtime(self, sio) -> None:
		from engineio import packet

		open_sockets = [s for s in list(sio.eio.sockets.values()) if not (s.closed or s.closing)]
		logger.info("realtime: disconnect %d client(s)", len(open_sockets))
		for socket in open_sockets:
			# The NOOP packet completes the poll request that the client holds. The abort
			# then gives a 400 response to the next poll request. Without the abort, that
			# request waits for one more ping timeout. The client reads the two packets as
			# a failure of the transport, and it connects again. The client reads a CLOSE
			# packet as an intentional disconnection by the server, and does not connect
			# again.
			await socket.send(packet.Packet(packet.NOOP))
			await socket.close(wait=False, abort=True)
		await sio.shutdown()


class StatusRecorder:
	"""The send function of one ASGI request. It keeps the status of the response."""

	def __init__(self, send):
		self.send = send
		self.status = 0

	async def __call__(self, message):
		if message["type"] == "http.response.start":
			self.status = message["status"]
		await self.send(message)


class Traffic:
	"""The counts of the work of the process, and the time of the last web request."""

	def __init__(self):
		self._lock = threading.Lock()
		self.counts = {"web": 0, "realtime": 0, "jobs": 0}
		self.in_flight = 0
		self.last_web_request = time.monotonic()

	@contextmanager
	def busy(self):
		"""Count one web request or one job as work in progress for the block."""
		with self._lock:
			self.in_flight += 1
		try:
			yield
		finally:
			with self._lock:
				self.in_flight -= 1

	def count(self, name: str) -> None:
		with self._lock:
			self.counts[name] += 1

	def count_web(self, status: int) -> None:
		"""Only a 2xx response increases the count. Each request sets the time."""
		with self._lock:
			self.last_web_request = time.monotonic()
			if 200 <= status < 300:
				self.counts["web"] += 1

	@property
	def idle_seconds(self) -> float:
		# Only the web requests set this time. The realtime polls and the scheduled
		# jobs continue always, thus a process that counts them is never idle.
		return time.monotonic() - self.last_web_request

	@property
	def summary(self) -> str:
		return ", ".join(f"{name} {count}" for name, count in self.counts.items())


class BackgroundJobs:
	"""The job threads of the runner. Each thread runs one job at a time."""

	def __init__(self, config: Config, traffic: Traffic):
		self.threads = [JobThread(config, traffic, index) for index in range(config.job_threads)]

	def start(self) -> None:
		for thread in self.threads:
			thread.start()

	def stop(self) -> None:
		for thread in self.threads:
			thread.stop()

	def wait(self, timeout: float) -> None:
		"""Wait for the threads. All of them together get the time of the timeout."""
		deadline = time.monotonic() + timeout
		for thread in self.threads:
			thread.wait(max(0.0, deadline - time.monotonic()))


class JobThread:
	"""One no-fork worker of frappe on a daemon thread. It stops between two jobs."""

	def __init__(self, config: Config, traffic: Traffic, index: int):
		self.config = config
		self.traffic = traffic
		self.stopping = threading.Event()
		self.worker = None
		self.thread = threading.Thread(target=self._work, name=f"rq-worker-{index}", daemon=True)

	def start(self) -> None:
		self.thread.start()

	def stop(self) -> None:
		self.stopping.set()
		if self.worker:
			self.worker.stop()

	def wait(self, timeout: float) -> None:
		if not self.thread.is_alive():
			return
		self.thread.join(timeout)
		if self.thread.is_alive():
			logger.warning("the job continues after %.0fs: the runner stops without it", timeout)

	def _work(self) -> None:
		# work() returns after RQ_MAX_JOBS jobs. Thus make a new worker and continue.
		while not self.stopping.is_set():
			queues = get_queue_list(self.config.queue_names, build_queue_name=True)
			self.worker = ThreadedWorker(queues, self.traffic, connection=get_redis_conn())
			logger.info("%s: jobs on %s", self.thread.name, ", ".join(q.name for q in self.worker.queues))
			self.worker.work(logging_level="INFO" if self.config.verbose else "WARNING")


class Scheduler:
	"""The scheduler of frappe on a daemon thread of its own.

	start_scheduler holds a lock file of the bench. A second scheduler, in this
	process or in a different one, sees the lock and stops immediately.
	"""

	def __init__(self):
		self.thread = threading.Thread(target=start_scheduler, name="scheduler", daemon=True)

	def start(self) -> None:
		self.thread.start()


class ThreadedWorker(FrappeWorkerNoFork):
	"""The no-fork worker of frappe, adjusted for a thread that is not the main thread."""

	# SIGALRM operates only on the main thread. TimerDeathPenalty causes the timeout
	# in the applicable thread. RQ also uses TimerDeathPenalty on Windows.
	death_penalty_class = TimerDeathPenalty

	def __init__(self, queues, traffic: Traffic, **kwargs):
		super().__init__(queues, **kwargs)
		self.traffic = traffic

	def stop(self):
		"""Stop the worker in a smooth manner. A job in progress continues to its end."""
		self._stop_requested = True

	def execute_job(self, job, queue):
		with self.traffic.busy():
			super().execute_job(job, queue)
		self.traffic.count("jobs")

	def dequeue_job_and_maintain_ttl(self, timeout, max_idle_time=None):
		# The method of RQ blocks on one long BLPOP, and it does not look at the stop
		# flag while it waits. Short polls make a stop request effective in some
		# seconds. The method returns a job that it got, and does not lose it.
		while not self._stop_requested:
			job = super().dequeue_job_and_maintain_ttl(JOB_POLL_SECONDS, JOB_POLL_SECONDS)
			if job:
				return job
		raise StopRequested

	def kill_horse(self, sig=None):
		# The worker does not fork. Thus the "horse" is this thread. The method of the
		# parent class sends SIGKILL to the process, and this also stops the web app.
		logger.warning("kill_horse ignored: the jobs run on a thread, the job continues")

	def start_frappe_scheduler(self):
		# The Scheduler of the runner owns the scheduler. The method of the parent class
		# starts one more thread at each maintenance cycle of RQ.
		pass

	def _install_signal_handlers(self):
		# signal.signal() causes the error "signal only works in main thread".
		pass


class Runner:
	"""Starts, stops, and restarts the web app, realtime, and the jobs together."""

	def __init__(self, config: Config):
		self.config = config
		self.traffic = Traffic()
		self.web = WebServer(config, self.traffic)
		self.jobs = BackgroundJobs(config, self.traffic)
		self.scheduler = Scheduler()
		self.draining = threading.Event()
		self.restarting = threading.Event()

	def run(self) -> None:
		for sig in (signal.SIGHUP, signal.SIGINT, signal.SIGTERM):
			signal.signal(sig, self.drain)

		if self.config.has_restart_limit:
			RestartWatch(self.config, self.traffic, self.draining).start()
		self.jobs.start()
		self.scheduler.start()

		# Uvicorn takes SIGINT and SIGTERM for the time of run(). It sends them to
		# server.handle_exit, and it sends them again to the process at the end. The
		# runner replaces that function. Thus the jobs stop at the same time as the web
		# app, and not after it.
		self.web.serve(self.drain)

		self.jobs.stop()
		self.jobs.wait(self.config.job_drain_seconds)
		if self.restarting.is_set():
			# execv keeps the PID. Thus a supervisor sees one good process at all times.
			# Use orig_argv and not argv: "-m frappe.runner" must come back in the same
			# form. The path of this file puts the frappe directory on sys.path.
			logger.info("re-exec")
			os.execv(sys.executable, sys.orig_argv)

	def drain(self, sig, frame=None) -> None:
		"""Stop the work in a smooth manner. SIGHUP restarts, SIGINT and SIGTERM stop.

		An exit signal has more priority than SIGHUP. A SIGHUP that comes during the
		shutdown must not start the process again. The restart watch can send such a
		SIGHUP."""
		if sig != signal.SIGHUP:
			self.restarting.clear()
		elif not self.draining.is_set():
			self.restarting.set()

		if not self.draining.is_set():
			self.draining.set()
			logger.info("%s: shutdown starts (%s)", signal.Signals(sig).name, self.traffic.summary)
			self.jobs.stop()
			self.web.close_realtime()
		# Uvicorn stops to accept new requests, completes the open requests, and runs
		# the ASGI lifespan shutdown. In that shutdown realtime releases its redis
		# bridge and its clients. A second signal stops the process immediately.
		self.web.stop(sig, frame)


class RestartWatch:
	"""Send SIGHUP to the process when it is at a limit and the web side is quiet."""

	def __init__(self, config: Config, traffic: Traffic, draining: threading.Event):
		self.config = config
		self.traffic = traffic
		self.draining = draining
		self.thread = threading.Thread(target=self._watch, name="restart-watch", daemon=True)

	def start(self) -> None:
		self.thread.start()

	@property
	def is_limit_reached(self) -> bool:
		counts = self.traffic.counts
		config = self.config
		return bool(config.restart_after_requests and counts["web"] >= config.restart_after_requests) or bool(
			config.restart_after_jobs and counts["jobs"] >= config.restart_after_jobs
		)

	@property
	def is_quiet(self) -> bool:
		return not self.traffic.in_flight and self.traffic.idle_seconds >= self.config.restart_idle_seconds

	def _watch(self) -> None:
		while not self.draining.wait(RESTART_CHECK_SECONDS):
			if self.is_limit_reached and self.is_quiet:
				logger.info(
					"limit reached (%s), idle %.0fs: restart",
					self.traffic.summary,
					self.traffic.idle_seconds,
				)
				os.kill(os.getpid(), signal.SIGHUP)
				return


class HelpFormatter(argparse.ArgumentDefaultsHelpFormatter, argparse.RawDescriptionHelpFormatter):
	"""Show the default of each flag, and keep the line breaks of the description."""


def main() -> None:
	"""Read the command line and run the process. Each flag has the name of a field
	of Config, thus the namespace of argparse is the config."""
	parser = argparse.ArgumentParser(description=__doc__, formatter_class=HelpFormatter)
	parser.add_argument("--host", default="127.0.0.1", help="address to listen on")
	parser.add_argument("--port", type=int, default=8000, help="port to listen on")
	parser.add_argument("--queue", help="comma separated queues; unset means all of them")
	parser.add_argument("--verbose", action="store_true", help="log each job and each realtime packet")
	parser.add_argument(
		"--serve-assets", action="store_true", help="send /assets and /files, as when there is no proxy"
	)
	parser.add_argument(
		"--web-threads", type=int, default=0, help="concurrent web requests (0 = the default of frappe.asgi)"
	)
	parser.add_argument("--job-threads", type=int, default=1, help="concurrent background jobs")
	parser.add_argument(
		"--restart-after-requests", type=int, default=5000, help="web requests before a restart (0 = never)"
	)
	parser.add_argument(
		"--restart-after-jobs", type=int, default=500, help="jobs before a restart (0 = never)"
	)
	parser.add_argument(
		"--restart-idle-seconds", type=float, default=300, help="quiet time to wait for before a restart"
	)
	parser.add_argument(
		"--request-drain-seconds", type=float, default=60, help="how long to wait for the open requests"
	)
	parser.add_argument(
		"--job-drain-seconds", type=float, default=600, help="how long to wait for a job in progress"
	)

	config = Config(**vars(parser.parse_args()))
	logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
	if config.verbose:
		logging.getLogger("frappe.realtime.packets").setLevel(logging.INFO)
	Runner(config).run()


if __name__ == "__main__":
	main()
