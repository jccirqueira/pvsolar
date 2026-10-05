"""Performance scoring routes."""

from datetime import UTC

from fastapi import APIRouter, HTTPException, Query

from src.core.app import get_perf_benchmark, get_perf_calculator, get_store

router = APIRouter()


@router.get("/performance/{inverter_id}")
async def get_performance_score(inverter_id: str):
    """
    Get performance score for an inverter.

    Returns PR, CEF, availability, efficiency, and overall score.
    """
    calculator = get_perf_calculator()

    if calculator is None:
        raise HTTPException(
            status_code=503,
            detail="Performance calculator not initialized",
        )

    score = calculator.calculate(inverter_id)

    if score is None:
        # Try from store
        store = get_store()
        score = await store.get_performance_score(inverter_id)
        if score is None:
            raise HTTPException(
                status_code=404,
                detail="No performance score available for this inverter",
            )
        return score

    return score.to_dict()


@router.get("/performance/{inverter_id}/benchmark")
async def get_performance_benchmark(inverter_id: str):
    """
    Get benchmark comparison for an inverter.

    Returns ranking, fleet percentile, and comparison metrics.
    """
    benchmark = get_perf_benchmark()

    if benchmark is None:
        raise HTTPException(
            status_code=503,
            detail="Performance benchmark not initialized",
        )

    result = benchmark.benchmark(inverter_id)

    if result is None:
        raise HTTPException(
            status_code=404,
            detail="No benchmark data available for this inverter",
        )

    return result.to_dict()


@router.get("/performance/{inverter_id}/history")
async def get_performance_history(
    inverter_id: str,
    days: int = Query(30, ge=1, le=365, description="Number of days"),
):
    """
    Get performance history for an inverter.

    Returns historical performance scores.
    """
    calculator = get_perf_calculator()

    if calculator is None:
        raise HTTPException(
            status_code=503,
            detail="Performance calculator not initialized",
        )

    history = calculator.get_history(inverter_id)

    # Filter by days
    if history:
        from datetime import datetime, timedelta
        cutoff = datetime.now(UTC) - timedelta(days=days)
        history = [
            h for h in history
            if h.get("timestamp", datetime.min.replace(tzinfo=UTC)) > cutoff
        ]

    return {
        "inverter_id": inverter_id,
        "history": history,
        "total": len(history),
    }


@router.get("/performance/ranking")
async def get_performance_ranking():
    """
    Get performance ranking of all inverters.

    Returns inverters sorted by performance score.
    """
    store = get_store()
    inverters = await store.get_inverters()

    calculator = get_perf_calculator()
    scores = []

    for inv in inverters:
        inv_id = inv.get("id", inv.get("inverter_id"))
        if calculator:
            score = calculator.calculate(inv_id)
            if score:
                scores.append({
                    "inverter_id": inv_id,
                    "name": inv.get("name", inv_id),
                    "overall_score": score.overall_score,
                    "performance_ratio": score.performance_ratio,
                    "grade": score.grade,
                })
        else:
            score = await store.get_performance_score(inv_id)
            if score:
                scores.append({
                    "inverter_id": inv_id,
                    "name": inv.get("name", inv_id),
                    "overall_score": score.get("overall_score", 0),
                    "performance_ratio": score.get("performance_ratio", 0),
                    "grade": score.get("grade", "N/A"),
                })

    scores.sort(key=lambda x: x.get("overall_score", 0), reverse=True)

    return {"ranking": scores, "total": len(scores)}


@router.get("/performance/fleet")
async def get_fleet_stats():
    """
    Get fleet-wide performance statistics.

    Returns mean, std, min, max scores across all inverters.
    """
    benchmark = get_perf_benchmark()

    if benchmark is None:
        return {
            "total_inverters": 0,
            "peer_groups": 0,
        }

    return benchmark.get_fleet_stats()


@router.get("/performance/fleet/{peer_group}")
async def get_peer_group_stats(peer_group: str):
    """
    Get statistics for a specific peer group.

    Returns metrics for inverters in the same model/capacity group.
    """
    benchmark = get_perf_benchmark()

    if benchmark is None:
        raise HTTPException(
            status_code=503,
            detail="Performance benchmark not initialized",
        )

    stats = benchmark.get_peer_group_stats(peer_group)

    return {"peer_group": peer_group, "stats": stats}


@router.get("/performance/stats")
async def get_performance_stats():
    """
    Get performance system statistics.

    Returns calculator status and data metrics.
    """
    calculator = get_perf_calculator()
    benchmark = get_perf_benchmark()

    return {
        "calculator": calculator.get_stats() if calculator else {},
        "benchmark": benchmark.get_stats() if benchmark else {},
    }
