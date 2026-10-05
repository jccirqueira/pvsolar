"""
Tests for pvSolar Fleet Site Manager.
"""

from src.core.config import SiteConfig, SiteStatus
from src.sites.site_manager import SiteInfo, SiteManager, SiteMetrics


def make_site_config(id: str = "site_1", name: str = "Test Site", region: str = "default"):
    return SiteConfig(
        id=id, name=name,
        gateway_url="http://localhost:8000",
        analytics_url="http://localhost:8001",
        capacity_kw=100.0, num_inverters=6,
        latitude=-23.55, longitude=-46.63, region=region,
    )


class TestSiteInfo:
    def test_create_site_info(self):
        config = make_site_config()
        site = SiteInfo(config)
        assert site.id == "site_1"
        assert site.name == "Test Site"
        assert site.status == SiteStatus.OFFLINE
        assert site.capacity_kw == 100.0

    def test_to_dict(self):
        config = make_site_config()
        site = SiteInfo(config)
        d = site.to_dict()
        assert d["id"] == "site_1"
        assert d["status"] == "offline"
        assert d["capacity_kw"] == 100.0

    def test_update_status(self):
        config = make_site_config()
        site = SiteInfo(config)
        site.update_status(SiteStatus.ONLINE)
        assert site.status == SiteStatus.ONLINE
        assert site.last_update is not None

    def test_update_info(self):
        config = make_site_config()
        site = SiteInfo(config)
        site.update_info(name="New Name", capacity_kw=200.0)
        assert site.name == "New Name"
        assert site.capacity_kw == 200.0


class TestSiteMetrics:
    def test_create_metrics(self):
        metrics = SiteMetrics("site_1")
        assert metrics.site_id == "site_1"
        assert metrics.power_kw == 0.0

    def test_to_dict(self):
        metrics = SiteMetrics("site_1")
        metrics.power_kw = 50.0
        metrics.pr = 82.5
        d = metrics.to_dict()
        assert d["site_id"] == "site_1"
        assert d["power_kw"] == 50.0
        assert d["pr"] == 82.5


class TestSiteManager:
    def test_create_manager(self):
        mgr = SiteManager()
        assert mgr.get_site_count() == 0

    def test_add_site(self):
        mgr = SiteManager()
        site = mgr.add_site(make_site_config())
        assert site.id == "site_1"
        assert mgr.get_site_count() == 1

    def test_remove_site(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config())
        result = mgr.remove_site("site_1")
        assert result is True
        assert mgr.get_site_count() == 0

    def test_remove_nonexistent(self):
        mgr = SiteManager()
        result = mgr.remove_site("nonexistent")
        assert result is False

    def test_get_site(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config())
        site = mgr.get_site("site_1")
        assert site is not None
        assert site.name == "Test Site"

    def test_get_all_sites(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config(id="s1", name="S1"))
        mgr.add_site(make_site_config(id="s2", name="S2"))
        sites = mgr.get_all_sites()
        assert len(sites) == 2

    def test_get_sites_by_region(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config(id="s1", region="north"))
        mgr.add_site(make_site_config(id="s2", region="south"))
        mgr.add_site(make_site_config(id="s3", region="north"))
        north = mgr.get_sites_by_region("north")
        assert len(north) == 2

    def test_get_regions(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config(id="s1", region="north"))
        mgr.add_site(make_site_config(id="s2", region="south"))
        regions = mgr.get_regions()
        assert len(regions) == 2
        assert "north" in regions
        assert "south" in regions

    def test_add_metrics(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config())
        metrics = SiteMetrics("site_1")
        metrics.power_kw = 50.0
        result = mgr.add_metrics("site_1", metrics)
        assert result is True

    def test_get_latest_metrics(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config())
        m1 = SiteMetrics("site_1")
        m1.power_kw = 40.0
        mgr.add_metrics("site_1", m1)
        m2 = SiteMetrics("site_1")
        m2.power_kw = 50.0
        mgr.add_metrics("site_1", m2)
        latest = mgr.get_latest_metrics("site_1")
        assert latest is not None
        assert latest.power_kw == 50.0

    def test_get_total_capacity(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config(id="s1", name="S1"))
        c2 = make_site_config(id="s2", name="S2")
        c2.capacity_kw = 200.0
        mgr.add_site(c2)
        assert mgr.get_total_capacity() == 300.0

    def test_fleet_summary(self):
        mgr = SiteManager()
        mgr.add_site(make_site_config(id="s1"))
        mgr.add_site(make_site_config(id="s2"))
        summary = mgr.get_fleet_summary()
        assert summary["total_sites"] == 2
        assert summary["total_capacity_kw"] == 200.0
