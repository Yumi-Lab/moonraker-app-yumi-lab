import logging
import subprocess
import threading
import time
import os

_logger = logging.getLogger('obico.ssh_tunnel')

# Default auto-close after 1 hour for security
DEFAULT_TIMEOUT_SECONDS = 3600
SAV_SSH_USER = 'sav'
SAV_SSH_KEY_PATH = os.path.expanduser('~/.ssh/yumi_sav_key')
SAV_SSH_PORT = 20000


class SshTunnel:
    """Passthru target for on-demand reverse SSH tunnel (SAV remote support).

    Opens a reverse SSH tunnel from the pad to app.yumi-lab.com so that
    Yumi support can SSH into the pad remotely.  The tunnel is off by
    default and activated on demand via the passthru WebSocket protocol.

    Port assignment: 20000 + printer_id  (deterministic, no negotiation needed).
    """

    def __init__(self, model, sentry):
        self.model = model
        self.sentry = sentry
        self._process = None
        self._timer = None
        self._active_port = None
        self._lock = threading.Lock()
        self._ensure_ssh_key()

    @property
    def _printer_id(self):
        return self.model.linked_printer.get('id')

    @property
    def _server_host(self):
        """Extract hostname from server URL (e.g. app.yumi-lab.com)."""
        url = self.model.config.server.canonical_endpoint_prefix()
        # strip https:// or http://
        host = url.split('://')[1] if '://' in url else url
        return host.split('/')[0].split(':')[0]

    def open(self, timeout=DEFAULT_TIMEOUT_SECONDS, port=SAV_SSH_PORT):
        """Open reverse SSH tunnel to the VPS.

        Args:
            timeout: Auto-close tunnel after this many seconds (default 3600 = 1h).
            port: Remote port assigned by the server (from pool 20000-20009).

        Returns:
            (dict, error) tuple following passthru convention.
        """
        with self._lock:
            if self._process and self._process.poll() is None:
                return {
                    'status': 'already_open',
                    'remote_port': self._active_port,
                    'printer_id': self._printer_id,
                }, None

            try:
                remote_port = port
                server_host = self._server_host

                cmd = [
                    '/usr/bin/ssh',
                    '-N',
                    '-i', SAV_SSH_KEY_PATH,
                    '-o', 'StrictHostKeyChecking=no',
                    '-o', 'ServerAliveInterval=30',
                    '-o', 'ServerAliveCountMax=3',
                    '-o', 'ExitOnForwardFailure=yes',
                    '-R', f'{remote_port}:localhost:22',
                    f'{SAV_SSH_USER}@{server_host}',
                ]

                _logger.info(f'Opening SAV SSH tunnel: port {remote_port} on {server_host}')
                self._process = subprocess.Popen(
                    cmd,
                    stdout=subprocess.DEVNULL,
                    stderr=subprocess.PIPE,
                )

                # Give autossh a moment to establish or fail
                time.sleep(2)
                if self._process.poll() is not None:
                    stderr = self._process.stderr.read().decode().strip()
                    self._process = None
                    _logger.error(f'SAV SSH tunnel failed to start: {stderr}')
                    return None, f'Tunnel failed to start: {stderr}'

                # Auto-close timer for security
                if timeout and timeout > 0:
                    self._start_timeout(timeout)

                self._active_port = remote_port
                _logger.info(f'SAV SSH tunnel open on port {remote_port} (timeout: {timeout}s)')
                return {
                    'status': 'open',
                    'remote_port': remote_port,
                    'printer_id': self._printer_id,
                    'timeout': timeout,
                }, None

            except FileNotFoundError:
                return None, 'ssh not found on this device'
            except Exception as e:
                self.sentry.captureException()
                return None, str(e)

    def close(self):
        """Close the reverse SSH tunnel.

        Returns:
            (dict, error) tuple following passthru convention.
        """
        with self._lock:
            self._cancel_timeout()

            if not self._process or self._process.poll() is not None:
                self._process = None
                return {'status': 'already_closed'}, None

            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                self._process.kill()
                self._process.wait(timeout=3)

            self._process = None
            self._active_port = None
            _logger.info('SAV SSH tunnel closed')
            return {'status': 'closed'}, None

    def status(self):
        """Return current tunnel status.

        Returns:
            (dict, error) tuple following passthru convention.
        """
        is_open = self._process is not None and self._process.poll() is None
        return {
            'status': 'open' if is_open else 'closed',
            'remote_port': self._active_port if is_open else None,
            'printer_id': self._printer_id,
        }, None

    def _start_timeout(self, timeout):
        self._cancel_timeout()
        self._timer = threading.Timer(timeout, self._auto_close)
        self._timer.daemon = True
        self._timer.start()

    def _cancel_timeout(self):
        if self._timer:
            self._timer.cancel()
            self._timer = None

    def _auto_close(self):
        _logger.info('SAV SSH tunnel auto-closing (timeout reached)')
        self.close()

    def _ensure_ssh_key(self):
        """Generate SSH keypair for SAV tunnel if it doesn't exist."""
        if os.path.exists(SAV_SSH_KEY_PATH):
            return

        ssh_dir = os.path.dirname(SAV_SSH_KEY_PATH)
        os.makedirs(ssh_dir, mode=0o700, exist_ok=True)

        try:
            subprocess.run(
                ['ssh-keygen', '-t', 'ed25519', '-f', SAV_SSH_KEY_PATH,
                 '-N', '', '-C', f'yumi-sav-{os.uname().nodename}'],
                check=True,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            _logger.info(f'Generated SAV SSH key: {SAV_SSH_KEY_PATH}')
        except Exception as e:
            _logger.warning(f'Failed to generate SAV SSH key: {e}')

    def get_public_key(self):
        """Return the public key so the server can provision it.

        Returns:
            (dict, error) tuple following passthru convention.
        """
        pub_key_path = SAV_SSH_KEY_PATH + '.pub'
        if not os.path.exists(pub_key_path):
            return None, 'SSH key not generated yet'

        with open(pub_key_path, 'r') as f:
            public_key = f.read().strip()

        return {
            'public_key': public_key,
            'printer_id': self._printer_id,
            'remote_port': self._remote_port,
        }, None
