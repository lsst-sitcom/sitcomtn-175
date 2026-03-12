import itertools
import numpy as np
import pandas as pd

from bokeh.io import output_notebook, show
from bokeh.models import (
    BoxAnnotation,
    BoxZoomTool,
    ColumnDataSource,
    CrosshairTool,
    CustomJSTickFormatter,
    DatetimeTickFormatter,
    FixedTicker,
    HoverTool,
    LinearAxis,
    PanTool,
    ResetTool,
    SaveTool,
    WheelZoomTool,
)
from bokeh.palettes import Category10
from bokeh.plotting import figure, gridplot

__all__ = [
    "plot_fwhm_metrics",
    "plot_ccd_z4",
    "plot_ccd_z11",
    "plot_night_timeline_combined",
]


output_notebook()

CORNER_DETECTORS = [191, 195, 199, 203]

# ── Color palettes ────────────────────────────────────────────────────────────
BAND_COLORS = {
    "u": "#9467bd", "g": "#2ca02c", "r": "#d62728",
    "i": "#ff7f0e", "z": "#1f77b4", "y": "#8b4513",
}

FWHM_COLORS = {
    "aos_fwhm": "black",
    "fwhm_zenith_500nm_median": "gray",
}

CCD_MEAN_COLORS = {
    "ccd_z4_mean": "#17becf",
    "ccd_z11_mean": "#ff7f0e",
}

DETECTOR_COLORS = {det: Category10[4][i] for i, det in enumerate(CORNER_DETECTORS)}


def _setup_figure_and_data(df: pd.DataFrame):
    """
    Setup and prepare data and base figure with common elements.
    
    Returns:
        Tuple of (processed DataFrame, ColumnDataSource, bokeh figure)
    """
    df = df.reset_index().copy()
    df["obs_start"] = pd.to_datetime(df["obs_start"])
    df["obs_start_ms"] = df["obs_start"].astype(np.int64) // 1_000_000
    source = ColumnDataSource(df)

    wheel_zoom = WheelZoomTool()

    p = figure(
        width=1300, height=550,
        x_axis_type="datetime",
        title="Observatory Performance",
        tools=[
            PanTool(),
            BoxZoomTool(),
            BoxZoomTool(dimensions="width"),
            wheel_zoom,
            ResetTool(),
            SaveTool(),
        ],
        active_scroll=wheel_zoom,
    )
    p.xaxis.axis_label = "Time (UTC)"
    p.yaxis.axis_label = "Value"
    p.xaxis.formatter = DatetimeTickFormatter(minutes="%H:%M", hours="%H:%M")

    # ── Top axis: visit seq numbers ───────────────────────────────────────────
    step = max(1, len(df) // 18)
    tick_df = df.iloc[::step]
    js_labels = {
        int(ms): str(int(v))[-3:]
        for ms, v in zip(tick_df["obs_start_ms"], tick_df["visit"])
    }
    p.add_layout(
        LinearAxis(
            ticker=FixedTicker(ticks=tick_df["obs_start_ms"].tolist()),
            formatter=CustomJSTickFormatter(code=f"""
                const labels = {js_labels};
                return labels[tick] !== undefined ? labels[tick] : '';
            """),
            axis_label="Visit (seq #)",
        ),
        "above",
    )

    # ── Filter bands ──────────────────────────────────────────────────────────
    for band, group in itertools.groupby(
        zip(df["obs_start_ms"], df["band"]), key=lambda x: x[1]
    ):
        run = [ms for ms, _ in group]
        p.add_layout(BoxAnnotation(
            left=run[0], right=run[-1],
            fill_color=BAND_COLORS.get(band, "#aaaaaa"),
            fill_alpha=0.13, line_color=None,
        ))

    return df, source, p


def plot_fwhm_metrics(df: pd.DataFrame):
    """
    Plot FWHM metrics (aos_fwhm, fwhm_zenith_500nm_median, ccd_z4_mean, ccd_z11_mean).
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing observation data with columns:
        obs_start, band, aos_fwhm, fwhm_zenith_500nm_median, ccd_z4_mean, ccd_z11_mean
    
    Returns
    -------
    bokeh.plotting.Figure
        Bokeh figure with FWHM metrics plotted
    """
    df, source, p = _setup_figure_and_data(df)

    line_renderers = []

    for col, color in FWHM_COLORS.items():
        r = p.line(
            x="obs_start_ms", y=col, source=source,
            line_color=color, line_width=1.8, line_alpha=0.5,
            muted_alpha=0.05, legend_label=col,
        )
        p.scatter(
            x="obs_start_ms", y=col, source=source,
            marker="circle", size=4, color=color,
            muted_alpha=0.05, legend_label=col,
        )
        line_renderers.append(r)

    # ── Additional CCD Z4 and Z11 mean lines ──────────────────────────────────
    for col, color in CCD_MEAN_COLORS.items():
        r = p.line(
            x="obs_start_ms", y=col, source=source,
            line_color=color, line_width=1.8, line_alpha=0.5,
            muted_alpha=0.05, legend_label=col,
        )
        p.scatter(
            x="obs_start_ms", y=col, source=source,
            marker="circle", size=4, color=color,
            muted_alpha=0.05, legend_label=col,
        )
        line_renderers.append(r)

    # ── Hover ─────────────────────────────────────────────────────────────────
    p.add_tools(HoverTool(
        renderers=line_renderers,
        mode="mouse",
        tooltips=[
            ("Visit", "@visit"),
            ("Time", "@obs_start"),
            ("Band", "@band"),
            ("AOS FWHM", "@aos_fwhm{0.000}"),
            ("FWHM zenith 500nm", "@fwhm_zenith_500nm_median{0.000}"),
            ("CCD Z4 Mean", "@ccd_z4_mean{0.000}"),
            ("CCD Z11 Mean", "@ccd_z11_mean{0.000}"),
        ],
    ))

    # ── Legend ────────────────────────────────────────────────────────────────
    if p.legend:
        legend = p.legend[0]
        p.add_layout(legend, 'right')
        legend.location = "top_right"
        legend.click_policy = "mute"
        legend.label_text_font_size = "10px"
        legend.spacing = 2
        legend.background_fill_alpha = 0.8

    return p


def plot_ccd_z4(df: pd.DataFrame, corner_detectors: list = CORNER_DETECTORS):
    """
    Plot CCD Z4 term data for corner detectors.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing observation data with columns: obs_start, band, ccd_z4_d*
    corner_detectors : list, optional
        List of detector IDs to plot. Default is [191, 195, 199, 203]
    
    Returns
    -------
    bokeh.plotting.Figure
        Bokeh figure with CCD Z4 data plotted
    """
    df, source, p = _setup_figure_and_data(df)

    # Recompute detector colors if different corner_detectors are provided
    detector_colors = (
        {det: Category10[4][i] for i, det in enumerate(corner_detectors)}
        if corner_detectors != CORNER_DETECTORS else DETECTOR_COLORS
    )
    line_renderers = []

    for det in corner_detectors:
        color = detector_colors[det]
        col = f"ccd_z4_d{det}"
        r = p.line(
            x="obs_start_ms", y=col, source=source,
            line_color=color, line_width=1.5, line_dash="solid", line_alpha=0.5,
            muted_alpha=0.05, legend_label=col,
        )
        p.scatter(
            x="obs_start_ms", y=col, source=source,
            marker="circle", size=4, color=color,
            muted_alpha=0.05, legend_label=col,
        )
        line_renderers.append(r)

    # ── Hover ─────────────────────────────────────────────────────────────────
    p.add_tools(HoverTool(
        renderers=line_renderers,
        mode="mouse",
        tooltips=[
            ("Visit", "@visit"),
            ("Time", "@obs_start"),
            ("Band", "@band"),
        ],
    ))

    # ── Legend ────────────────────────────────────────────────────────────────
    if p.legend:
        legend = p.legend[0]
        p.add_layout(legend, 'right')
        legend.location = "top_right"
        legend.click_policy = "mute"
        legend.label_text_font_size = "10px"
        legend.spacing = 2
        legend.background_fill_alpha = 0.8

    return p


def plot_ccd_z11(df: pd.DataFrame, corner_detectors: list = CORNER_DETECTORS):
    """
    Plot CCD Z11 term data for corner detectors.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing observation data with columns: obs_start, band, ccd_z11_d*
    corner_detectors : list, optional
        List of detector IDs to plot. Default is [191, 195, 199, 203]
    
    Returns
    -------
    bokeh.plotting.Figure
        Bokeh figure with CCD Z11 data plotted
    """
    df, source, p = _setup_figure_and_data(df)

    # Recompute detector colors if different corner_detectors are provided
    detector_colors = (
        {det: Category10[4][i] for i, det in enumerate(corner_detectors)}
        if corner_detectors != CORNER_DETECTORS else DETECTOR_COLORS
    )
    line_renderers = []

    for det in corner_detectors:
        color = detector_colors[det]
        col = f"ccd_z11_d{det}"
        r = p.line(
            x="obs_start_ms", y=col, source=source,
            line_color=color, line_width=1.5, line_dash="solid", line_alpha=0.5,
            muted_alpha=0.05, legend_label=col,
        )
        p.scatter(
            x="obs_start_ms", y=col, source=source,
            marker="triangle", size=4, color=color,
            muted_alpha=0.05, legend_label=col,
        )
        line_renderers.append(r)

    # ── Hover ─────────────────────────────────────────────────────────────────
    p.add_tools(HoverTool(
        renderers=line_renderers,
        mode="mouse",
        tooltips=[
            ("Visit", "@visit"),
            ("Time", "@obs_start"),
            ("Band", "@band"),
        ],
    ))

    # ── Legend ────────────────────────────────────────────────────────────────
    if p.legend:
        legend = p.legend[0]
        p.add_layout(legend, 'right')
        legend.location = "top_right"
        legend.click_policy = "mute"
        legend.label_text_font_size = "10px"
        legend.spacing = 2
        legend.background_fill_alpha = 0.8

    return p


def plot_night_timeline_combined(df: pd.DataFrame, corner_detectors: list = CORNER_DETECTORS):
    """
    Create a combined plot with three subplots stacked vertically:
    top - FWHM metrics, middle - CCD Z4, bottom - CCD Z11.
    
    The three plots share an x-axis range, so zooming in one zooms all three.
    A vertical crosshair cursor is synchronized across all plots.
    
    Parameters
    ----------
    df : pd.DataFrame
        DataFrame containing observation data
    corner_detectors : list, optional
        List of detector IDs to plot. Default is [191, 195, 199, 203]
    
    Returns
    -------
    bokeh.layouts.Column
        A gridplot layout with the three vertically stacked plots
    """
    # Create individual plots with reduced height
    p_fwhm = plot_fwhm_metrics(df)
    p_z4 = plot_ccd_z4(df, corner_detectors)
    p_z11 = plot_ccd_z11(df, corner_detectors)
    
    # Reduce individual plot heights
    p_fwhm.height = 300
    p_z4.height = 300
    p_z11.height = 300
    
    # Link x-axis ranges so zooming in one plot affects the others
    p_z4.x_range = p_fwhm.x_range
    p_z11.x_range = p_fwhm.x_range
    
    # Add crosshair tool to each plot for synchronized vertical cursor
    p_fwhm.add_tools(CrosshairTool(dimensions="height"))
    p_z4.add_tools(CrosshairTool(dimensions="height"))
    p_z11.add_tools(CrosshairTool(dimensions="height"))
    
    # Create grid layout with the three plots stacked vertically
    grid = gridplot(
        [[p_fwhm], [p_z4], [p_z11]],
        toolbar_location="right",
        merge_tools=True,
    )
    
    return grid

