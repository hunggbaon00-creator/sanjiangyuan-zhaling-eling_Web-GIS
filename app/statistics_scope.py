"""Resolve the formal statistics table for the active map scope."""

from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class StatisticsScope:
    """Statistics and labels shared by all dashboard components."""

    data: pd.DataFrame
    label: str
    area_column: str
    selected_subbasin_id: str | None

    @property
    def is_overall(self) -> bool:
        return self.selected_subbasin_id is None


def resolve_statistics_scope(
    overall_data: pd.DataFrame,
    subbasin_data: pd.DataFrame,
    selected_subbasin_id: str | None,
) -> StatisticsScope:
    """Return one seven-year dataset for the selected dashboard scope."""
    expected_years = sorted(overall_data["year"].unique().tolist())
    if len(overall_data) != 7 or len(expected_years) != 7:
        raise ValueError("总体研究区的年度统计应包含7个唯一年份。")

    if selected_subbasin_id is None:
        scope_data = overall_data.copy()
        label = "总体研究区"
        area_column = "roi_area_km2"
    else:
        scope_data = subbasin_data.loc[
            subbasin_data["subbasin_id"] == selected_subbasin_id
        ].copy()
        if scope_data.empty:
            raise ValueError(f"没有找到分区统计：{selected_subbasin_id}")
        names = scope_data["subbasin_name"].dropna().unique().tolist()
        if len(names) != 1:
            raise ValueError(f"分区名称不唯一：{selected_subbasin_id}")
        label = f"{selected_subbasin_id} · {names[0]}"
        area_column = "subbasin_area_km2"

    scope_years = sorted(scope_data["year"].unique().tolist())
    if len(scope_data) != 7 or scope_years != expected_years:
        raise ValueError(f"{label}的年度统计应包含7个唯一年份。")
    return StatisticsScope(
        data=scope_data.sort_values("year").reset_index(drop=True),
        label=label,
        area_column=area_column,
        selected_subbasin_id=selected_subbasin_id,
    )
