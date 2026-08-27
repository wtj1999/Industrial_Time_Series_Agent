"""Resolve structured business applications into orchestrator queries."""

from typing import Any, Callable, Dict

from .battery_installation_forecast import build_query as build_battery_query
from .new_energy_vehicle_sales import build_query as build_vehicle_sales_query
from .coating_areal_density_analysis import build_query as build_coating_query
from .coating_areal_density_anomaly_detection import build_query as build_coating_anomaly_query
from .cell_capacity_root_cause import build_query as build_cell_capacity_root_cause_query
from .cell_production_forecast import build_query as build_cell_production_forecast_query
from .pack_production_forecast import build_query as build_pack_production_forecast_query
from .factory_energy_forecast import build_query as build_factory_energy_forecast_query


ApplicationBuilder = Callable[[Dict[str, Any]], str]

_APPLICATION_BUILDERS: Dict[str, ApplicationBuilder] = {
    "battery-installation-forecast": build_battery_query,
    "new-energy-vehicle-sales": build_vehicle_sales_query,
    "coating-areal-density-analysis": build_coating_query,
    "coating-areal-density-anomaly-detection": build_coating_anomaly_query,
    "cell-capacity-root-cause": build_cell_capacity_root_cause_query,
    "cell-production-forecast": build_cell_production_forecast_query,
    "pack-production-forecast": build_pack_production_forecast_query,
    "factory-energy-forecast": build_factory_energy_forecast_query,
}


def build_application_query(application_id: str, params: Dict[str, Any]) -> str:
    """Validate application parameters and compile a user task query."""
    builder = _APPLICATION_BUILDERS.get(application_id)
    if builder is None:
        raise ValueError(f"Unknown agent application: {application_id}")
    return builder(params)
