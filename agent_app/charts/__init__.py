"""Chart-payload extraction for the analysis / anomaly-detection /
prediction sub-agents.

Each sub-agent walks its langchain message stream via
:func:`agents.base_agent.extract_tool_calls` to produce a flat
``tool_calls`` list (one record per invocation, with the parsed tool
``result`` already attached). The extractors in this package consume
that list and turn the **last** chartable tool result into a
frontend-ready chart payload.

Public surface
--------------
- :func:`extract_analysis_chart` — correlation / histogram / decomposition /
  control / changepoint / acf.
- :func:`extract_anomaly_chart` — anomaly-score scatter for
  ``detect_with_model`` / ``detect_ts_anomalies``.
- :func:`extract_prediction_chart` — quantile-band forecast chart for
  ``forecast_time_series`` / ``forecast_multi_models``.
- :func:`extract_evaluation_chart` — backtest chart for
  ``backtest_forecast`` / ``compare_forecast_models_backtest``;
  overlays the holdout actuals on top of the forecast so the user can
  eyeball the error directly.
"""

from .analysis_charts import extract_analysis_chart
from .anomaly_charts import extract_anomaly_chart
from .evaluation_charts import extract_evaluation_chart
from .prediction_charts import extract_prediction_chart

__all__ = [
    "extract_analysis_chart",
    "extract_anomaly_chart",
    "extract_prediction_chart",
    "extract_evaluation_chart",
]
