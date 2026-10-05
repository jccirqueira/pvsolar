"""
Tests for pvSolar Fleet Comparison Engine.
"""

from src.comparison.comparison_engine import ComparisonEngine, ComparisonResult, SiteRanking
from src.core.config import ComparisonMetric, SiteConfig
from src.sites.site_manager import SiteManager, SiteMetrics


def make_site(id: str, name: str, region: str = "default"):
    return SiteConfig(
        id=id, name=name,
        gateway_url="http://localhost:8000",
        analytics_url="http://localhost:8001",
        capacity_kw=100.0, num_inverters=6,
        latitude=0.0, longitude=0.0, region=region,
    )


class TestSiteRanking:
    def test_create_ranking(self):
        r = SiteRanking("s1", "Site 1", ComparisonMetric.PR, 85.0, 1)
        assert r.site_id == "s1"
        assert r.value == 85.0
        assert r.rank == 1

    def test_to_dict(self):
        r = SiteRanking("s1", "Site 1", ComparisonMetric.PR, 85.0, 1)
        d = r.to_dict()
        assert d["site_id"] == "s1"
        assert d["value"] == 85.0


class TestComparisonResult:
    def test_create_result(self):
        result = ComparisonResult(ComparisonMetric.PR)
        assert result.metric == ComparisonMetric.PR
        assert result.rankings == []

    def test_to_dict(self):
        result = ComparisonResult(ComparisonMetric.PR)
        result.avg_value = 80.0
        result.best_site = "S1"
        d = result.to_dict()
        assert d["avg_value"] == 80.0
        assert d["best_site"] == "S1"


class TestComparisonEngine:
    def setup_method(self):
        self.mgr = SiteManager()
        self.engine = ComparisonEngine(self.mgr)

    def test_create_engine(self):
        assert len(self.engine._history) == 0

    def test_compare_sites(self):
        s1 = make_site("s1", "Site 1")
        s2 = make_site("s2", "Site 2")
        self.mgr.add_site(s1)
        self.mgr.add_site(s2)

        m1 = SiteMetrics("s1")
        m1.pr = 85.0
        self.mgr.add_metrics("s1", m1)

        m2 = SiteMetrics("s2")
        m2.pr = 75.0
        self.mgr.add_metrics("s2", m2)

        result = self.engine.compare_sites(ComparisonMetric.PR)
        assert len(result.rankings) == 2
        assert result.rankings[0].site_id == "s1"
        assert result.rankings[0].rank == 1
        assert result.best_site == "Site 1"
        assert result.worst_site == "Site 2"

    def test_compare_all_metrics(self):
        s1 = make_site("s1", "Site 1")
        self.mgr.add_site(s1)
        m1 = SiteMetrics("s1")
        m1.pr = 85.0
        m1.efficiency = 90.0
        self.mgr.add_metrics("s1", m1)

        results = self.engine.compare_all_metrics()
        assert "pr" in results
        assert "efficiency" in results

    def test_get_vs_average(self):
        s1 = make_site("s1", "S1")
        s2 = make_site("s2", "S2")
        self.mgr.add_site(s1)
        self.mgr.add_site(s2)

        m1 = SiteMetrics("s1")
        m1.pr = 80.0
        self.mgr.add_metrics("s1", m1)

        m2 = SiteMetrics("s2")
        m2.pr = 60.0
        self.mgr.add_metrics("s2", m2)

        result = self.engine.get_vs_average("s1", ComparisonMetric.PR)
        assert result["site_value"] == 80.0
        assert result["fleet_avg"] == 70.0
        assert result["diff"] == 10.0

    def test_get_vs_best(self):
        s1 = make_site("s1", "S1")
        s2 = make_site("s2", "S2")
        self.mgr.add_site(s1)
        self.mgr.add_site(s2)

        m1 = SiteMetrics("s1")
        m1.pr = 80.0
        self.mgr.add_metrics("s1", m1)

        m2 = SiteMetrics("s2")
        m2.pr = 90.0
        self.mgr.add_metrics("s2", m2)

        result = self.engine.get_vs_best("s1", ComparisonMetric.PR)
        assert result["site_value"] == 80.0
        assert result["best_value"] == 90.0
        assert result["diff"] == 10.0

    def test_get_best_performers(self):
        for i in range(5):
            s = make_site(f"s{i}", f"S{i}")
            self.mgr.add_site(s)
            m = SiteMetrics(f"s{i}")
            m.pr = 60.0 + i * 5
            self.mgr.add_metrics(f"s{i}", m)

        best = self.engine.get_best_performers(ComparisonMetric.PR, 3)
        assert len(best) == 3
        assert best[0].rank == 1

    def test_get_worst_performers(self):
        for i in range(5):
            s = make_site(f"s{i}", f"S{i}")
            self.mgr.add_site(s)
            m = SiteMetrics(f"s{i}")
            m.pr = 60.0 + i * 5
            self.mgr.add_metrics(f"s{i}", m)

        worst = self.engine.get_worst_performers(ComparisonMetric.PR, 3)
        assert len(worst) == 3

    def test_history(self):
        s1 = make_site("s1", "S1")
        self.mgr.add_site(s1)
        m1 = SiteMetrics("s1")
        m1.pr = 85.0
        self.mgr.add_metrics("s1", m1)

        self.engine.compare_sites(ComparisonMetric.PR)
        self.engine.compare_sites(ComparisonMetric.PR)
        history = self.engine.get_comparison_history(2)
        assert len(history) == 2

    def test_compare_empty_fleet(self):
        result = self.engine.compare_sites(ComparisonMetric.PR)
        assert len(result.rankings) == 0
        assert result.avg_value == 0.0
