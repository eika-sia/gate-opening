from pwn import serialtube
import re
import time

_ANSI_RE = re.compile(rb'\x1B\[[0-9;?]*[A-Za-z]')

class SerialIO:
    def __init__(self, device: str, baud: int = 115200, line_ending: bytes = b"\r", timeout: float = 1.0):
        """
        device: path to tty (e.g. /dev/serial/by-id/...)
        baud: serial baudrate
        line_ending: bytes appended automatically to sent text (default CR)
        timeout: default recv timeout in seconds
        """
        if not isinstance(line_ending, (bytes, bytearray)):
            raise TypeError("line_ending must be bytes")
        self.device = device
        self.baud = baud
        self.line_ending = line_ending
        self.timeout = timeout

        # Create pwntools serialtube (thin wrapper over pyserial)
        self._io = serialtube(self.device, baudrate=self.baud, convert_newlines=False)
        # ensure non-blocking-ish default
        self._io.timeout = self.timeout

    # ----- low-level helpers -----
    def _to_bytes(self, data):
        if isinstance(data, (bytes, bytearray)):
            return bytes(data)
        if isinstance(data, str):
            return data.encode('utf-8')
        raise TypeError("data must be str or bytes")

    def _clean(self, data: bytes) -> bytes:
        """Remove ANSI control sequences and trailing whitespace newlines."""
        if not data:
            return b""
        cleaned = _ANSI_RE.sub(b"", data)
        return cleaned.rstrip(b"\r\n ")

    # ----- public API -----
    def send(self, data, add_line_ending: bool = True):
        """
        Send a command.
        - data: str or bytes
        - add_line_ending: if True, append self.line_ending (default True)
        Returns number of bytes sent.
        """
        b = self._to_bytes(data)
        if add_line_ending:
            b = b + self.line_ending
        # use serialtube.send (expects bytes)
        self._io.send(b)
        return len(b)

    def recv(self, timeout: float = None, max_bytes: int = 4096) -> bytes:
        """
        Read up to max_bytes (or until timeout). Returns cleaned bytes (ANSI stripped).
        """
        t = self.timeout if timeout is None else timeout
        # pwntools tube: recvrepeat waits until no new data arrives for timeout seconds
        data = self._io.recvrepeat(t)
        return self._clean(data[:max_bytes])

    def send_and_wait(self, data, wait: float = None) -> bytes:
        """
        Convenience: send(data) then recv(wait) and return response (cleaned).
        """
        self.send(data, add_line_ending=True)
        return self.recv(timeout=wait)

    def interactive(self):
        """
        Drop to pwntools' interactive console (duplex keyboard<->device).
        Use Ctrl+C to return (pwntools handles the raw mode).
        """
        try:
            print("[Entering interactive mode — Ctrl+C to exit]")
            self._io.interactive()
        except KeyboardInterrupt:
            # interactive returns on Ctrl+C
            print("\n[Exited interactive mode]")

    def close(self):
        try:
            self._io.close()
        except Exception:
            pass

    # Context manager
    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        self.close()

    # For convenience, expose raw tube (if you need advanced pwntools ops)
    @property
    def raw(self):
        return self._io
