"""
Data Collector Module.

Collects data from pvSolar Gateway and Analytics APIs.
"""

import asyncio
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

import aiohttp
import structlog

from src.core.config import AnalyticsConfig, GatewayConfig

logger = structlog.get_logger(__name__)


class TelemetryData:
    """Represents collected telemetry data."""

    def __init__(self):
        self.timestamp: datetime = datetime.now(timezone.utc)
        self.power_kw: float = 0.0
        self.energy_kwh: float = 0.0
        self.irradiance: float = 0.0
        self.temperature: float = 0.0
        self.efficiency: float = 0.0
        self.inverters: List[Dict[str, Any]] = []
        self.weather: Dict[str, Any] = {}

    def to_dict(self) -> Dict[str, Any]:
        return {
            "timestamp": self.timestamp.isoformat(),
            "power_kw": self.power_kw,
            "energy_kwh": self.energy_kwh,
            "irradiance": self.irradiance,
            "temperature": self.temperature,
            "efficiency": self.efficiency,
            "inverters": self.inverters,
            "weather": self.weather,
        }


class AlarmData:
    """Represents alarm data."""

    def __init__(self, alarm_id: str, level: str, message: str, source: str, timestamp: datetime):
        self.alarm_id = alarm_id
        self.level = level
        self.message = message
        self.source = source
        self.timestamp = timestamp
        self.acknowledged: bool = False

    def to_dict(self) -> Dict[str, Any]:
        return {
            "alarm_id": self.alarm_id,
            "level": self.level,
            "message": self.message,
            "source": self.source,
            "timestamp": self.timestamp.isoformat(),
            "acknowledged": self.acknowledged,
        }


class PerformanceData:
    """Represents performance scoring data."""

    def __init__(self):
        self.overall_score: float = 0.0
        self.grade: str = "--"
        self.pr: float = 0.0
        self.cef: float = 0.0
        self.availability: float = 0.0
        self.efficiency: float = 0.0
        self.recommendations: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "overall_score": self.overall_score,
            "grade": self.grade,
            "pr": self.pr,
            "cef": self.cef,
            "availability": self.availability,
            "efficiency": self.efficiency,
            "recommendations": self.recommendations,
        }


class MaintenanceData:
    """Represents maintenance prediction data."""

    def __init__(self):
        self.predictions: List[Dict[str, Any]] = []
        self.risk_level: str = "low"
        self.next_maintenance: Optional[str] = None
        self.urgent_actions: List[str] = []

    def to_dict(self) -> Dict[str, Any]:
        return {
            "predictions": self.predictions,
            "risk_level": self.risk_level,
            "next_maintenance": self.next_maintenance,
            "urgent_actions": self.urgent_actions,
        }


class DataCollector:
    """
    Collects data from Gateway and Analytics APIs.

    Features:
    - Async HTTP requests
    - Data aggregation for reports
    - Caching for repeated queries
    - Error handling with fallbacks
    """

    def __init__(self, gateway_config: GatewayConfig, analytics_config: AnalyticsConfig):
        self.gateway = gateway_config
        self.analytics = analytics_config
        self._session: Optional[aiohttp.ClientSession] = None
        self._cache: Dict[str, Any] = {}

    async def start(self) -> None:
        self._session = aiohttp.ClientSession()
        logger.info("collector.started")

    async def stop(self) -> None:
        if self._session:
            await self._session.close()
        logger.info("collector.stopped")

    def _headers(self, config) -> Dict[str, str]:
        headers = {"Content-Type": "application/json"}
        if config.api_key:
            headers["Authorization"] = f"Bearer {config.api_key}"
        return headers

    async def _get(self, base_url: str, path: str, config) -> Optional[Dict[str, Any]]:
        if not self._session:
            return None
        try:
            url = f"{base_url}{path}"
            async with self._session.get(
                url, headers=self._headers(config), timeout=aiohttp.ClientTimeout(total=config.timeout)
            ) as resp:
                if resp.status == 200:
                    return await resp.json()
                logger.warning("collector.http_error", url=url, status=resp.status)
        except Exception as e:
            logger.error("collector.request_error", path=path, error=str(e))
        return None

    async def get_telemetry(self, device_id: str, date: Optional[datetime] = None) -> Optional[TelemetryData]:
        target = date or datetime.now(timezone.utc)
        result = await self._get(self.gateway.url, f"/api/v1/telemetry/{device_id}", self.gateway)
        if not result:
            return None

        data = TelemetryData()
        data.timestamp = target
        data.power_kw = result.get("power_kw", 0.0)
        data.energy_kwh = result.get("energy_kwh", 0.0)
        data.irradiance = result.get("irradiance", 0.0)
        data.temperature = result.get("temperature", 0.0)
        data.efficiency = result.get("efficiency", 0.0)
        return data

    async def get_inverters_status(self) -> List[Dict[str, Any]]:
        result = await self._get(self.gateway.url, "/api/v1/inverters", self.gateway)
        return result.get("inverters", []) if result else []

    async def get_alarms(self, start: datetime, end: datetime) -> List[AlarmData]:
        params = f"?start={start.isoformat()}&end={end.isoformat()}"
        result = await self._get(self.gateway.url, f"/api/v1/alarms{params}", self.gateway)
        if not result:
            return []

        alarms = []
        for a in result.get("alarms", []):
            alarms.append(AlarmData(
                alarm_id=a.get("id", ""),
                level=a.get("level", "info"),
                message=a.get("message", ""),
                source=a.get("source", ""),
                timestamp=datetime.fromisoformat(a.get("timestamp", datetime.now(timezone.utc).isoformat())),
            ))
        return alarms

    async def get_performance(self) -> Optional[PerformanceData]:
        result = await self._get(self.analytics.url, "/api/v1/performance/current", self.analytics)
        if not result:
            return None

        perf = PerformanceData()
        perf.overall_score = result.get("overall_score", 0.0)
        perf.grade = result.get("grade", "--")
        perf.pr = result.get("pr", 0.0)
        perf.cef = result.get("cef", 0.0)
        perf.availability = result.get("availability", 0.0)
        perf.efficiency = result.get("efficiency", 0.0)
        perf.recommendations = result.get("recommendations", [])
        return perf

    async def get_maintenance(self) -> Optional[MaintenanceData]:
        result = await self._get(self.analytics.url, "/api/v1/maintenance/predictions", self.analytics)
        if not result:
            return None

        maint = MaintenanceData()
        maint.predictions = result.get("predictions", [])
        maint.risk_level = result.get("risk_level", "low")
        maint.next_maintenance = result.get("next_maintenance")
        maint.urgent_actions = result.get("urgent_actions", [])
        return maint

    async def get_anomalies(self, start: datetime, end: datetime) -> List[Dict[str, Any]]:
        params = f"?start={start.isoformat()}&end={end.isoformat()}"
        result = await self._get(self.analytics.url, f"/api/v1/anomalies/detect{params}", self.analytics)
        return result.get("anomalies", []) if result else []

    async def get_forecast(self, days: int = 1) -> Optional[Dict[str, Any]]:
        result = await self._get(self.analytics.url, f"/api/v1/forecast/energy?days={days}", self.analytics)
        return result

    async def collect_daily_data(self, date: Optional[datetime] = None) -> Dict[str, Any]:
        target = date or datetime.now(timezone.utc)
        start = target.replace(hour=0, minute=0, second=0, microsecond=0)
        end = start + timedelta(days=1)

        results = await asyncio.gather(
            self.get_inverters_status(),
            self.get_alarms(start, end),
            self.get_performance(),
            self.get_maintenance(),
            self.get_anomalies(start, end),
            self.get_forecast(1),
            return_exceptions=True,
        )

        inverters = results[0] if not isinstance(results[0], Exception) else []
        alarms = results[1] if not isinstance(results[1], Exception) else []
        performance = results[2] if not isinstance(results[2], Exception) else None
        maintenance = results[3] if not isinstance(results[3], Exception) else None
        anomalies = results[4] if not isinstance(results[4], Exception) else []
        forecast = results[5] if not isinstance(results[5], Exception) else None

        total_power = sum(inv.get("power_kw", 0) for inv in inverters)
        total_energy = sum(inv.get("energy_kwh", 0) for inv in inverters)
        active_count = sum(1 for inv in inverters if inv.get("status") == "online")

        return {
            "date": target.strftime("%Y-%m-%d"),
            "plant": {
                "total_power_kw": total_power,
                "total_energy_kwh": total_energy,
                "active_inverters": active_count,
                "total_inverters": len(inverters),
            },
            "inverters": inverters,
            "alarms": [a.to_dict() for a in alarms],
            "performance": performance.to_dict() if performance else None,
            "maintenance": maintenance.to_dict() if maintenance else None,
            "anomalies": anomalies,
            "forecast": forecast,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    async def collect_weekly_data(self, end_date: Optional[datetime] = None) -> Dict[str, Any]:
        target = end_date or datetime.now(timezone.utc)
        start = target - timedelta(days=7)

        daily_data = []
        current = start
        while current <= target:
            day_data = await self.collect_daily_data(current)
            daily_data.append(day_data)
            current += timedelta(days=1)

        return {
            "period": f"{start.strftime('%Y-%m-%d')} to {target.strftime('%Y-%m-%d')}",
            "daily_data": daily_data,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }

    async def collect_monthly_data(self, year: int, month: int) -> Dict[str, Any]:
        import calendar
        days_in_month = calendar.monthrange(year, month)[1]
        start = datetime(year, month, 1, tzinfo=timezone.utc)
        end = datetime(year, month, days_in_month, tzinfo=timezone.utc)

        daily_data = []
        current = start
        while current <= end:
            day_data = await self.collect_daily_data(current)
            daily_data.append(day_data)
            current += timedelta(days=1)

        return {
            "period": f"{year}-{month:02d}",
            "daily_data": daily_data,
            "collected_at": datetime.now(timezone.utc).isoformat(),
        }
