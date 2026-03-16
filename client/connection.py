import logging
from typing import Callable

import requests

logger = logging.getLogger("TAM.connection")


class ConnectionMonitor:
    def __init__(self, server_url: str):
        self.server_url = server_url.rstrip("/")
        self._online = False
        self.was_offline = False
        self.on_reconnect: Callable | None = None

    def is_server_reachable(self) -> bool:
        try:
            resp = requests.get(f"{self.server_url}/ping", timeout=3)
            return resp.status_code == 200
        except requests.RequestException:
            return False

    def check_connection(self) -> bool:
        reachable = self.is_server_reachable()

        if reachable and not self._online:
            logger.info("Server connection restored")
            self.was_offline = True
            self._online = True
            if self.on_reconnect:
                try:
                    self.on_reconnect()
                except Exception as exc:
                    logger.error("on_reconnect callback error: %s", exc)
        elif not reachable and self._online:
            logger.warning("Server connection lost")
            self._online = False
        elif not reachable and not self._online:
            pass
        else:
            self.was_offline = False

        return self._online
