/** Whether the work that asked is still wanted when its slow answer lands. */
export type Current = () => boolean;

/** One async job whose slow answer must not land after a later one: the latest request wins. */
export class LatestWins {
	private latest = 0;
	private epoch = 0;
	private stopped = false;

	/** Starts a request. It stays current until another `begin`, a `cancel` or a `stop`. */
	begin(): Current {
		const mine = ++this.latest;
		return () => !this.stopped && mine === this.latest;
	}

	/** Follows the work as it is now: only a `cancel` or a `stop` ends it, not a later `begin`. */
	watch(): Current {
		const mine = this.epoch;
		return () => !this.stopped && mine === this.epoch;
	}

	/** Ends every request and watch so far. */
	cancel() {
		this.latest++;
		this.epoch++;
	}

	/** Ends every request and watch, and every later one: the page is gone. */
	stop() {
		this.stopped = true;
	}

	get isStopped() {
		return this.stopped;
	}
}
