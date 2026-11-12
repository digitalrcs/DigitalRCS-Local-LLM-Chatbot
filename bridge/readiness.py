"""Cached readiness checks; background work never holds up the control page."""
import threading


class ReadinessMonitor:
    def __init__(self, checks, interval=30):
        # name -> (probe returning a user-safe message, safe failure message)
        self._checks = checks
        self._interval = interval
        self._lock = threading.Lock()
        self._stop = threading.Event()
        self._threads = []
        self._results = {
            name: {"status": "starting", "message": "Checking availability…"}
            for name in checks
        }

    def snapshot(self):
        with self._lock:
            checks = {name: dict(result) for name, result in self._results.items()}
        statuses = {check["status"] for check in checks.values()}
        status = "degraded" if "error" in statuses else "starting" if "starting" in statuses else "ready"
        return {"status": status, "checks": checks}

    def check_once(self, name):
        probe, failure = self._checks[name]
        try:
            result = {"status": "ready", "message": probe()}
        except Exception:
            # Provider exceptions can carry URLs, headers or private diagnostics.
            # The UI gets only our fixed, actionable message.
            result = {"status": "error", "message": failure}
        with self._lock:
            self._results[name] = result
        return result["status"] == "ready"

    def _run(self, name):
        while not self._stop.is_set():
            ok = self.check_once(name)
            # Loaded speech models stay resident. Retry failed loads; refresh
            # upstream availability even after a successful check.
            if ok and name != "chat":
                return
            if self._stop.wait(self._interval):
                return

    def start(self):
        if self._threads:
            return
        for name in self._checks:
            worker = threading.Thread(target=self._run, args=(name,), daemon=True,
                                      name="franky-ready-" + name)
            self._threads.append(worker)
            worker.start()

    def stop(self):
        self._stop.set()
        # Model loading can take time. Daemon workers must not delay shutdown.
