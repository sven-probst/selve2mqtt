"""
Centralized utilities for selve2mqtt bridge.

Provides:
- Unified logger setup (avoids duplicate basicConfig calls)
- Base component class (avoids duplicate config parsing and logger init)
- Centralized error handling helper
- PendingResponse for callback-based waiting instead of fixed sleeps
"""

import asyncio
import logging
import sys
from typing import Dict, Any, Optional, Set


def setup_logger(name: str = "selve2mqtt") -> logging.Logger:
    """
    Creates or retrieves a logger with consistent formatting.
    Only calls basicConfig once (first invocation wins).
    """
    logger = logging.getLogger(name)
    # Only configure root logger once; child loggers inherit format
    if not logging.getLogger().hasHandlers():
        logging.basicConfig(
            level=logging.INFO,
            format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
            handlers=[logging.StreamHandler(sys.stdout)]
        )
    return logger


class BaseComponent:
    """
    Base class for all selve2mqtt components.

    Provides:
    - Self-named logger via `setup_logger`
    - A `safe_execute` helper for uniform error handling
    """

    def __init__(self, config: Optional[Dict[str, Any]] = None):
        self.logger = setup_logger(self.__class__.__name__)
        self._config = config or {}

    # ------------------------------------------------------------------
    # Centralised error handling
    # ------------------------------------------------------------------
    def safe_execute(self, func, *args, exc_msg: str = None, raises: bool = True, **kwargs):
        """
        Execute *func* with *args*/*kwargs* and log any exceptions caught.

        Parameters
        ----------
        func : callable
            The callable to invoke.
        exc_msg : str, optional
            Custom log message prefix.
        raises : bool
            If True (default), re-raise the exception after logging.
        """
        try:
            return func(*args, **kwargs)
        except Exception as e:
            msg = exc_msg or f"Error in {getattr(func, '__name__', 'unknown')}"
            self.logger.error(f"{msg}: {e}", exc_info=True)
            if raises:
                raise
            return None


class PendingResponse:
    """
    Tracks pending gateway responses on a per-device basis.

    Instead of fixed ``asyncio.sleep()`` calls, code can :meth:`wait` for a
    response to arrive and the library callback to fire.  A configurable
    timeout prevents hangs when a response is lost.

    The future is created *before* the command is dispatched, so a response
    that arrives before :meth:`wait` is called will still be captured.

    Usage
    -----
    .. code-block:: python

        tracker = PendingResponse(timeout=10.0)

        # Create a future BEFORE sending the command:
        tracker.expect("device_42")

        # Now send the command ...
        await gateway.moveDeviceUp(device_42)

        # Wait for the response (or timeout):
        received = await tracker.wait("device_42")
        if not received:
            logger.warning("Timeout waiting for device 42")

        # In the callback that processes device updates:
        tracker.signal("device_42")
    """

    def __init__(self, default_timeout: float = 5.0):
        self._default_timeout = default_timeout
        self._futures: Dict[str, asyncio.Future] = {}

    def expect(self, device_id: str) -> None:
        """
        Register a pending response for *device_id* **before** sending the
        command, so a reply that arrives early is still captured.
        """
        loop = asyncio.get_running_loop()
        self._futures[device_id] = loop.create_future()

    async def wait(self, device_id: str, timeout: Optional[float] = None) -> bool:
        """
        Wait for a response for *device_id*.

        Returns ``True`` if the response arrived, ``False`` on timeout.
        """
        timeout = timeout if timeout is not None else self._default_timeout
        future = self._futures.get(device_id)
        if future is None:
            # No expect() was called – create a future now for safety.
            loop = asyncio.get_running_loop()
            future = loop.create_future()
            self._futures[device_id] = future
        try:
            await asyncio.wait_for(future, timeout=timeout)
            return True
        except asyncio.TimeoutError:
            if not future.done():
                future.cancel()
            return False
        finally:
            self._futures.pop(device_id, None)

    def signal(self, device_id: str) -> None:
        """Wake up any waiter for *device_id*."""
        future = self._futures.get(device_id)
        if future is not None and not future.done():
            future.set_result(True)

    @property
    def active_device_ids(self) -> Set[str]:
        """Return the set of device IDs currently being waited on."""
        return set(self._futures.keys())
