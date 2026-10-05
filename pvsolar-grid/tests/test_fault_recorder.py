"""Testes do fault_recorder do pvSolar Grid."""

import pytest
from src.core.config import (
    ComplianceStatus,
    FaultType,
    FRTConfig,
    HVRTCurve,
    LVRTCurve,
)
from src.fault_recorder.fault_recorder import FaultRecorder


class TestFaultRecorder:
    def test_create_recorder(self):
        r = FaultRecorder()
        assert len(r.events) == 0

    def test_record_event_frt(self):
        r = FaultRecorder()
        e = r.record_event(FaultType.FRT, 100.0, 0.8)
        assert e.event_type == FaultType.FRT
        assert len(r.events) == 1

    def test_record_event_lvrt_compliant(self):
        config = FRTConfig(
            enabled=True,
            lvrt_curve=[
                LVRTCurve(time_ms=0.0, voltage_pu=0.0),
                LVRTCurve(time_ms=150.0, voltage_pu=0.0),
                LVRTCurve(time_ms=600.0, voltage_pu=0.9),
            ],
        )
        r = FaultRecorder(config)
        e = r.record_event(FaultType.LVRT, 100.0, 0.5)
        assert e.compliance == ComplianceStatus.COMPLIANT

    def test_record_event_lvrt_non_compliant(self):
        config = FRTConfig(
            enabled=True,
            lvrt_curve=[
                LVRTCurve(time_ms=0.0, voltage_pu=0.0),
                LVRTCurve(time_ms=150.0, voltage_pu=0.5),
                LVRTCurve(time_ms=600.0, voltage_pu=0.9),
            ],
        )
        r = FaultRecorder(config)
        e = r.record_event(FaultType.LVRT, 100.0, 0.3)
        assert e.compliance == ComplianceStatus.NON_COMPLIANT

    def test_record_event_hvrt_compliant(self):
        config = FRTConfig(
            enabled=True,
            hvrt_curve=[
                HVRTCurve(time_ms=0.0, voltage_pu=1.3),
                HVRTCurve(time_ms=100.0, voltage_pu=1.2),
                HVRTCurve(time_ms=500.0, voltage_pu=1.1),
            ],
        )
        r = FaultRecorder(config)
        e = r.record_event(FaultType.HVRT, 50.0, 1.25)
        assert e.compliance == ComplianceStatus.COMPLIANT

    def test_record_event_hvrt_non_compliant(self):
        config = FRTConfig(
            enabled=True,
            hvrt_curve=[
                HVRTCurve(time_ms=0.0, voltage_pu=1.3),
                HVRTCurve(time_ms=100.0, voltage_pu=1.2),
            ],
        )
        r = FaultRecorder(config)
        e = r.record_event(FaultType.HVRT, 50.0, 1.4)
        assert e.compliance == ComplianceStatus.NON_COMPLIANT

    def test_record_event_disabled(self):
        config = FRTConfig(enabled=False)
        r = FaultRecorder(config)
        e = r.record_event(FaultType.LVRT, 100.0, 0.5)
        assert e.compliance == ComplianceStatus.UNKNOWN

    def test_get_events_by_type(self):
        r = FaultRecorder()
        r.record_event(FaultType.FRT, 100.0, 0.8)
        r.record_event(FaultType.LVRT, 200.0, 0.5)
        r.record_event(FaultType.FRT, 150.0, 0.9)
        frt = r.get_events_by_type(FaultType.FRT)
        assert len(frt) == 2

    def test_get_non_compliant_events(self):
        config = FRTConfig(
            enabled=True,
            lvrt_curve=[
                LVRTCurve(time_ms=0.0, voltage_pu=0.5),
                LVRTCurve(time_ms=600.0, voltage_pu=0.9),
            ],
        )
        r = FaultRecorder(config)
        r.record_event(FaultType.LVRT, 100.0, 0.8)
        r.record_event(FaultType.LVRT, 100.0, 0.3)
        nc = r.get_non_compliant_events()
        assert len(nc) == 1

    def test_get_event(self):
        r = FaultRecorder()
        e = r.record_event(FaultType.FRT, 100.0, 0.8)
        found = r.get_event(e.id)
        assert found is not None
        assert found.id == e.id

    def test_get_event_none(self):
        r = FaultRecorder()
        assert r.get_event("nonexistent") is None

    def test_delete_event(self):
        r = FaultRecorder()
        e = r.record_event(FaultType.FRT, 100.0, 0.8)
        assert r.delete_event(e.id) is True
        assert len(r.events) == 0

    def test_delete_event_none(self):
        r = FaultRecorder()
        assert r.delete_event("nonexistent") is False

    def test_get_statistics(self):
        r = FaultRecorder()
        r.record_event(FaultType.FRT, 100.0, 0.8)
        r.record_event(FaultType.LVRT, 200.0, 0.5)
        stats = r.get_statistics()
        assert stats["total_events"] == 2

    def test_clear(self):
        r = FaultRecorder()
        r.record_event(FaultType.FRT, 100.0, 0.8)
        count = r.clear()
        assert count == 1
        assert len(r.events) == 0

    def test_interpolate_lvrt_curve(self):
        config = FRTConfig(
            lvrt_curve=[
                LVRTCurve(time_ms=0.0, voltage_pu=0.0),
                LVRTCurve(time_ms=150.0, voltage_pu=0.0),
                LVRTCurve(time_ms=600.0, voltage_pu=0.9),
            ],
        )
        r = FaultRecorder(config)
        v = r._interpolate_lvrt_curve(100.0)
        assert v == 0.0

    def test_interpolate_hvrt_curve(self):
        config = FRTConfig(
            hvrt_curve=[
                HVRTCurve(time_ms=0.0, voltage_pu=1.3),
                HVRTCurve(time_ms=100.0, voltage_pu=1.2),
            ],
        )
        r = FaultRecorder(config)
        v = r._interpolate_hvrt_curve(50.0)
        assert 1.2 <= v <= 1.3
