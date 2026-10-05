"""
pvSolar SCADA Application.

Main application that initializes and runs the SCADA system.
"""

import asyncio
import signal

import structlog
from src.core.config import SCADAConfig, load_config
from src.core.data_manager import DataManager
from src.core.screens import ScreenManager
from src.core.server import PVBrowserServer
from src.screens.factory import ScreenFactory

logger = structlog.get_logger(__name__)


class PVSolarSCADA:
    """
    pvSolar SCADA Application.

    Main application class that initializes and manages:
    - pvBrowser server for HMI communication
    - Screen manager for SCADA screens
    - Data manager for MQTT and API integration
    - Alarm management
    """

    def __init__(self, config: SCADAConfig | None = None, config_path: str | None = None):
        if config:
            self.config = config
        else:
            self.config = load_config(config_path)

        self.screen_manager: ScreenManager | None = None
        self.server: PVBrowserServer | None = None
        self.data_manager: DataManager | None = None
        self._running = False

    async def start(self) -> None:
        """Start the SCADA application."""
        logger.info(
            "app.starting",
            title=self.config.pvbrowser.title,
            plant=self.config.plant.name,
        )

        try:
            screen_factory = ScreenFactory(self.config)
            self.screen_manager = screen_factory.create_all_screens()

            self.server = PVBrowserServer(self.config.pvbrowser)

            self.data_manager = DataManager(
                mqtt_config=self.config.mqtt,
                gateway_config=self.config.gateway,
                analytics_config=self.config.analytics,
            )

            self._register_commands()
            self._register_data_callbacks()

            await self.data_manager.start()
            await self.server.start()

            self._running = True

            logger.info(
                "app.started",
                port=self.config.pvbrowser.port,
                screens=len(self.screen_manager.screens),
            )

        except Exception as e:
            logger.error("app.start_error", error=str(e))
            raise

    async def stop(self) -> None:
        """Stop the SCADA application."""
        logger.info("app.stopping")

        self._running = False

        if self.server:
            await self.server.stop()

        if self.data_manager:
            await self.data_manager.stop()

        logger.info("app.stopped")

    def _register_commands(self) -> None:
        """Register command handlers."""
        if self.server:
            self.server.register_command_handler("navigate", self._handle_navigate)
            self.server.register_command_handler("ack_alarm", self._handle_ack_alarm)
            self.server.register_command_handler("set_power_limit", self._handle_set_power_limit)
            self.server.register_command_handler("restart_inverter", self._handle_restart_inverter)

    def _register_data_callbacks(self) -> None:
        """Register data update callbacks."""
        if self.data_manager:
            self.data_manager.register_callback("telemetry", self._on_telemetry)
            self.data_manager.register_callback("alarm", self._on_alarm)
            self.data_manager.register_callback("alarm_ack", self._on_alarm_ack)

    def _handle_navigate(self, params: dict) -> dict:
        """Handle screen navigation command."""
        screen_name = params.get("screen")
        if screen_name and self.screen_manager:
            success = self.screen_manager.set_current_screen(screen_name)
            return {"success": success, "screen": screen_name}
        return {"success": False, "error": "Invalid screen name"}

    def _handle_ack_alarm(self, params: dict) -> dict:
        """Handle alarm acknowledgment command."""
        alarm_id = params.get("alarm_id")
        user = params.get("user", "operator")

        if alarm_id and self.data_manager:
            success = self.data_manager.acknowledge_alarm(alarm_id, user)
            return {"success": success, "alarm_id": alarm_id}
        return {"success": False, "error": "Invalid alarm ID"}

    def _handle_set_power_limit(self, params: dict) -> dict:
        """Handle power limit command."""
        inverter_id = params.get("inverter_id")
        limit_kw = params.get("limit_kw")

        if inverter_id is not None and limit_kw is not None:
            logger.info("app.power_limit_set", inverter=inverter_id, limit=limit_kw)
            return {"success": True, "inverter_id": inverter_id, "limit_kw": limit_kw}
        return {"success": False, "error": "Invalid parameters"}

    def _handle_restart_inverter(self, params: dict) -> dict:
        """Handle inverter restart command."""
        inverter_id = params.get("inverter_id")

        if inverter_id is not None:
            logger.info("app.inverter_restart_requested", inverter=inverter_id)
            return {"success": True, "inverter_id": inverter_id, "message": "Restart command sent"}
        return {"success": False, "error": "Invalid inverter ID"}

    def _on_telemetry(self, device_id: str, telemetry: object) -> None:
        """Handle telemetry update."""
        if self.server and hasattr(telemetry, 'values'):
            self.server.update_widget("current_power", telemetry.values.get("power", 0.0))
            self.server.update_widget("daily_energy", telemetry.values.get("energy", 0.0))
            self.server.update_widget("efficiency", f"{telemetry.values.get('efficiency', 0.0):.1f}%")
            self.server.update_widget("irradiance", telemetry.values.get("irradiance", 0.0))
            self.server.update_widget("temperature", telemetry.values.get("temperature", 25.0))

    def _on_alarm(self, alarm_id: str, alarm: object) -> None:
        """Handle new alarm."""
        if self.server and hasattr(alarm, 'level'):
            critical = self.data_manager.get_alarms(acknowledged=False) if self.data_manager else []
            count = sum(1 for a in critical if hasattr(a, 'level') and a.level == "critical")
            self.server.update_widget("critical_count", str(count))

    def _on_alarm_ack(self, alarm_id: str, alarm: object) -> None:
        """Handle alarm acknowledgment."""
        pass

    @property
    def is_running(self) -> bool:
        """Check if application is running."""
        return self._running


def main() -> None:
    """Main entry point."""
    import argparse

    parser = argparse.ArgumentParser(description="pvSolar SCADA")
    parser.add_argument("-c", "--config", help="Config file path")
    parser.add_argument("--debug", action="store_true", help="Enable debug mode")
    args = parser.parse_args()

    import structlog
    structlog.configure(
        processors=[
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    config = load_config(args.config)
    if args.debug:
        config.debug = True

    app = PVSolarSCADA(config)

    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)

    def signal_handler(sig, frame):
        logger.info("app.signal_received", signal=sig)
        loop.create_task(app.stop())

    signal.signal(signal.SIGINT, signal_handler)
    signal.signal(signal.SIGTERM, signal_handler)

    try:
        loop.run_until_complete(app.start())
        loop.run_forever()
    except KeyboardInterrupt:
        loop.run_until_complete(app.stop())
    finally:
        loop.close()


if __name__ == "__main__":
    main()
