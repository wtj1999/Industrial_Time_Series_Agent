"""Resolve structured business applications into orchestrator queries."""

from typing import Any, Callable, Dict

from .battery_installation_forecast import build_query as build_battery_query
from .new_energy_vehicle_sales import build_query as build_vehicle_sales_query
from .coating_areal_density_analysis import build_query as build_coating_query
from .coating_areal_density_anomaly_detection import build_query as build_coating_anomaly_query


ApplicationBuilder = Callable[[Dict[str, Any]], str]

_APPLICATION_BUILDERS: Dict[str, ApplicationBuilder] = {
    "battery-installation-forecast": build_battery_query,
    "new-energy-vehicle-sales": build_vehicle_sales_query,
    "coating-areal-density-analysis": build_coating_query,
    "coating-areal-density-anomaly-detection": build_coating_anomaly_query,
}


def build_application_query(application_id: str, params: Dict[str, Any]) -> str:
    """Validate application parameters and compile a user task query."""
    builder = _APPLICATION_BUILDERS.get(application_id)
    if builder is None:
        raise ValueError(f"Unknown agent application: {application_id}")
    return builder(params)
