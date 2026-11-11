"""
modules/report_target.py
------------------------
Determines the Recommended Target (SAC Stories, Excel add-on, or SAC Analyzer)
for SAP BusinessObjects reports migrating to SAP Analytics Cloud (SAC).

Rules:
1. SAC Stories:
   - Reports with visualizations and more than one chart (or charts present).
   - Also recommended for Dashboards and Crystal Reports with visualizations.
2. Excel add-on:
   - Reports with more calculated columns / variables (> 5 variables) and no visualizations.
3. SAC Analyzer:
   - Reports with dimensions and tables, no visualizations, and minimal calculations (variables <= 5).
"""


def get_recommended_target(report: dict) -> str:
    """
    Classifies a report into its recommended SAP Analytics Cloud target:
      - 'SAC Stories'
      - 'Excel add-on'
      - 'SAC Analyzer'
    """
    if not isinstance(report, dict):
        return "SAC Analyzer"

    kind = str(report.get("kind") or "").lower()
    if "dashboard" in kind:
        return "SAC Stories"
    if "crystal" in kind:
        return "SAC Stories"

    # 1. Calculate visualization / chart counts and table counts
    vis = report.get("visualizations") or report.get("Visualizations") or {}
    total_charts = 0
    total_tables = 0

    if isinstance(vis, dict):
        for tab_counts in vis.values():
            if isinstance(tab_counts, dict):
                total_charts += int(tab_counts.get("visualizations", 0) or 0)
                total_tables += int(tab_counts.get("tables", 0) or 0)

    # 2. Count calculated variables / columns
    variables = report.get("variables") or report.get("Variables") or {}
    if isinstance(variables, dict):
        var_count = len(variables)
    elif isinstance(variables, list):
        var_count = len(variables)
    else:
        var_count = 0

    # 3. Count dimensions
    dimensions = report.get("dimensions") or report.get("Dimensions") or []
    dims_count = len(dimensions) if isinstance(dimensions, list) else 0

    # Rule 1: Use SAC Stories to replicate reports with visualizations and more than one chart
    # (or any charts/visualizations present)
    if total_charts > 1 or total_charts >= 1:
        return "SAC Stories"

    # Rule 2: Use the Excel add-on for reports with more calculated columns (variables > 5)
    if var_count > 5:
        return "Excel add-on"

    # Rule 3: Use SAC Analyzer for reports with dimensions and tables, no visualizations,
    # and minimal calculations (calculated variables <= 5)
    if total_charts == 0 and (total_tables > 0 or dims_count > 0) and var_count <= 5:
        return "SAC Analyzer"

    # Default / Fallback
    return "SAC Analyzer"

