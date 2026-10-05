"""
pvSolar Gateway - Core Module

Enterprise-grade solar inverter monitoring gateway with MQTT integration.
"""

import asyncio
import contextlib
import signal

import structlog
from prometheus_client import start_http_server

from .config import load_config
from .metrics import MetricsCollector

logger = structlog.get_logger(__name__)


class SolarGateway:
    """
    Main gateway class that orchestrates all components.

    Features:
    - Multi-inverter support via Modbus TCP/RTU
    - MQTT publishing with TLS 1.3
    - Edge computing with store-and-forward
    - pvbrowser integration
    - Cloud connectivity (AWS IoT, Azure IoT Hub)
    """

    def __init__(self, config_path: str):
        self.config = load_config(config_path)
        self.metrics = MetricsCollector(self.config.gateway.name)
        self._running = False
        self._tasks: list[asyncio.Task] = []

        # Components (initialized in start())
        self.mqtt_client = None
        self.drivers = []
        self.edge_store = None
        self.pvbinder = None
        self.web_app = None

        logger.info(
            "gateway.initializing",
            name=self.config.gateway.name,
            location=self.config.gateway.location
        )

    async def start(self):
        """Start all gateway components."""
        self._running = True

        # Setup signal handlers
        # (Windows nao suporta add_signal_handler - ignora la)
        loop = asyncio.get_event_loop()
        for sig in (signal.SIGINT, signal.SIGTERM):
            with contextlib.suppress(NotImplementedError, RuntimeError, ValueError):
                loop.add_signal_handler(sig, lambda: asyncio.create_task(self.stop()))

        # Start Prometheus metrics server
        if self.config.metrics.enabled:
            start_http_server(self.config.metrics.port)
            logger.info("metrics.started", port=self.config.metrics.port)

        # Initialize components
        await self._init_mqtt()
        await self._init_drivers()
        await self._init_edge_store()
        await self._init_pvbinder()
        await self._init_web_dashboard()

        # Start all components
        tasks = [
            self._run_mqtt(),
            self._run_drivers(),
            self._run_edge_sync(),
        ]

        if self.config.pvbrowser.enabled:
            tasks.append(self._run_pvbinder())

        if self.config.web.enabled:
            tasks.append(self._run_web_dashboard())

        self._tasks = [asyncio.create_task(t) for t in tasks]

        logger.info("gateway.started", components=len(self._tasks))

        # Wait for all tasks
        with contextlib.suppress(asyncio.CancelledError):
            await asyncio.gather(*self._tasks)

    async def stop(self):
        """Gracefully stop all components."""
        logger.info("gateway.stopping")
        self._running = False

        # Cancel all tasks
        for task in self._tasks:
            task.cancel()

        # Wait for tasks to finish
        await asyncio.gather(*self._tasks, return_exceptions=True)

        # Cleanup components
        if self.mqtt_client:
            await self.mqtt_client.disconnect()

        for driver in self.drivers:
            await driver.disconnect()

        if self.edge_store:
            await self.edge_store.close()

        logger.info("gateway.stopped")

    async def _init_mqtt(self):
        """Initialize MQTT client."""
        from mqtt.client import MQTTClient

        self.mqtt_client = MQTTClient(self.config.mqtt)
        await self.mqtt_client.connect()
        logger.info("mqtt.initialized", broker=self.config.mqtt.broker)

    async def _init_drivers(self):
        """Initialize inverter drivers."""
        from drivers.base import create_driver

        for inverter_config in self.config.inverters:
            driver = create_driver(inverter_config)
            await driver.connect()
            self.drivers.append(driver)
            logger.info(
                "driver.initialized",
                inverter=inverter_config.id,
                driver=inverter_config.driver
            )

    async def _init_edge_store(self):
        """Initialize edge store-and-forward."""
        if not self.config.edge.store_and_forward.enabled:
            return

        from edge.store import EdgeStore

        self.edge_store = EdgeStore(self.config.edge.store_and_forward)
        await self.edge_store.initialize()
        logger.info("edge_store.initialized")

    async def _init_pvbinder(self):
        """Initialize pvbrowser binder."""
        if not self.config.pvbrowser.enabled:
            return

        from pvbinder.bridge import PVBrowserBridge

        self.pvbinder = PVBrowserBridge(self.config.pvbrowser)
        await self.pvbinder.start()
        logger.info("pvbinder.initialized", port=self.config.pvbrowser.socket_port)

    async def _init_web_dashboard(self):
        """Initialize web dashboard."""
        if not self.config.web.enabled:
            return

        from web.app import create_app

        self.web_app = create_app(self.config, self.drivers, self.metrics)
        logger.info("web.initialized", port=self.config.web.port)

    async def _run_mqtt(self):
        """Run MQTT client loop."""
        while self._running:
            try:
                await self.mqtt_client.loop()
            except Exception as e:
                logger.error("mqtt.error", error=str(e))
                await asyncio.sleep(5)

    async def _run_drivers(self):
        """Run all inverter drivers."""
        while self._running:
            for driver in self.drivers:
                try:
                    data = await driver.read_all()

                    # Publish to MQTT
                    if self.mqtt_client and data:
                        await self.mqtt_client.publish_telemetry(
                            driver.config.id,
                            data
                        )

                    # Store in edge buffer
                    if self.edge_store and data:
                        await self.edge_store.store_reading(
                            driver.config.id,
                            data
                        )

                    # Update metrics
                    if data:
                        self.metrics.update_inverter(driver.config.id, data)

                    # Send to pvbrowser
                    if self.pvbinder and data:
                        await self.pvbinder.update_data(driver.config.id, data)

                except Exception as e:
                    logger.error(
                        "driver.read_error",
                        inverter=driver.config.id,
                        error=str(e)
                    )

            await asyncio.sleep(1)

    async def _run_edge_sync(self):
        """Sync edge store to cloud."""
        if not self.edge_store:
            return

        while self._running:
            try:
                await self.edge_store.sync_to_cloud()
            except Exception as e:
                logger.error("edge.sync_error", error=str(e))

            await asyncio.sleep(self.config.edge.store_and_forward.sync_interval)

    async def _run_pvbinder(self):
        """Run pvbrowser binder."""
        while self._running:
            try:
                await self.pvbinder.run()
            except Exception as e:
                logger.error("pvbinder.error", error=str(e))
                await asyncio.sleep(1)

    async def _run_web_dashboard(self):
        """Run web dashboard server."""
        import uvicorn

        config = uvicorn.Config(
            self.web_app,
            host="0.0.0.0",
            port=self.config.web.port,
            log_level="info"
        )
        server = uvicorn.Server(config)
        await server.serve()


def main():
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(
        description="pvSolar Gateway - Solar Inverter Monitoring"
    )
    parser.add_argument(
        "-c", "--config",
        default="config/gateway.yaml",
        help="Path to configuration file"
    )
    parser.add_argument(
        "-v", "--verbose",
        action="store_true",
        help="Enable verbose logging"
    )

    args = parser.parse_args()

    # Configure logging
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer()
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Run gateway
    gateway = SolarGateway(args.config)
    asyncio.run(gateway.start())


if __name__ == "__main__":
    main()
