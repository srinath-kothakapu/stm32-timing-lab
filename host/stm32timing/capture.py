"""Record raw lines from one or more boards' virtual COM ports.

Each port is read in its own thread and written verbatim to its own log file,
preceded by ``# key=value`` metadata lines. Logs are the primary record of a
run; all numbers in the report are recomputed from them.
"""

from __future__ import annotations

import datetime as dt
import platform
import threading
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class PortSpec:
    port: str
    label: str

    @classmethod
    def parse(cls, spec: str, index: int) -> "PortSpec":
        # "COM5", "COM5:boardA", "/dev/ttyACM0:boardB"
        if ":" in spec and not (len(spec) > 1 and spec[1] == ":" and spec[0].isalpha()):
            port, label = spec.rsplit(":", 1)
        else:
            port, label = spec, f"p{index}"
        return cls(port, label)


class _Recorder(threading.Thread):
    def __init__(self, spec: PortSpec, baud: int, path: Path, meta: dict, stop: threading.Event):
        super().__init__(daemon=True)
        self.spec, self.baud, self.path, self.meta, self.stop = spec, baud, path, meta, stop
        self.captures = 0
        self.header = ""
        self.error: Exception | None = None

    def run(self) -> None:
        import serial  # pyserial

        try:
            with serial.Serial(self.spec.port, self.baud, timeout=0.2) as ser, self.path.open("w", newline="\n") as f:
                for k, v in self.meta.items():
                    f.write(f"# {k}={v}\n")
                f.write(f"# port={self.spec.port}\n# label={self.spec.label}\n")
                ser.reset_input_buffer()
                buf = b""
                while not self.stop.is_set():
                    buf += ser.read(4096)
                    *lines, buf = buf.split(b"\n")
                    for raw in lines:
                        line = raw.decode("ascii", errors="replace").strip()
                        if not line:
                            continue
                        f.write(line + "\n")
                        if line.startswith("C,"):
                            self.captures += 1
                        elif line.startswith("H,"):
                            self.header = line
                f.flush()
        except Exception as e:  # reported by the main thread
            self.error = e


def record(ports: list[str], seconds: float, out_dir: str | Path, name: str, baud: int = 460800, note: str = "") -> list[Path]:
    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    stop = threading.Event()
    started = dt.datetime.now(dt.timezone.utc).isoformat(timespec="seconds")
    meta = {"started_utc": started, "host": platform.node(), "baud": baud, "planned_s": seconds, "note": note.replace("\n", " ")}
    recs = []
    for i, p in enumerate(ports):
        spec = PortSpec.parse(p, i)
        path = out / f"{name}_{spec.label}.log"
        recs.append(_Recorder(spec, baud, path, meta, stop))
    for r in recs:
        r.start()
    t0 = time.monotonic()
    try:
        while time.monotonic() - t0 < seconds:
            time.sleep(1.0)
            status = "  ".join(f"[{r.spec.label}] {r.captures} edges" for r in recs)
            print(f"\r{time.monotonic() - t0:6.0f}/{seconds:.0f} s  {status}", end="", flush=True)
            if any(r.error for r in recs):
                break
    except KeyboardInterrupt:
        print("\nstopped by user")
    stop.set()
    for r in recs:
        r.join(timeout=3)
    print()
    for r in recs:
        if r.error:
            raise RuntimeError(f"{r.spec.port}: {r.error}")
        if not r.header:
            print(f"warning: {r.spec.port} produced no header line - wrong port or baud rate?")
        print(f"{r.path}: {r.captures} edges  {r.header}")
    return [r.path for r in recs]
