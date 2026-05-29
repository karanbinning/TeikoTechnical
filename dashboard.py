import os

import dash
import dash_bootstrap_components as dbc
import plotly.express as px
import plotly.graph_objects as go
from dash import Input, Output, dash_table, dcc, html
from plotly.subplots import make_subplots

from analysis import get_baseline_subset, get_frequency_table, get_responder_stats
from load_data import DB_PATH, load_data

POPULATIONS = ["b_cell", "cd8_t_cell", "cd4_t_cell", "nk_cell", "monocyte"]
RESPONDER_COLOR = "#2ecc71"
NON_RESPONDER_COLOR = "#e74c3c"
CHART_COLORS = px.colors.qualitative.Set2

if not os.path.exists(DB_PATH):
    load_data()

freq_df = get_frequency_table()
plot_df, stats_df = get_responder_stats()
samples_per_project, response_counts, sex_counts = get_baseline_subset()

sample_options = [{"label": "All samples", "value": "all"}] + [
    {"label": s, "value": s} for s in sorted(freq_df["sample"].unique())
]

app = dash.Dash(
    __name__,
    external_stylesheets=[dbc.themes.FLATLY],
    title="Loblaw Bio — Miraclib Clinical Trial Dashboard",
    suppress_callback_exceptions=True,
)
app.layout = dbc.Container(
    [
        html.H1("Loblaw Bio — Miraclib Clinical Trial Dashboard", className="my-4 text-center"),
        dbc.Tabs(
            [
                dbc.Tab(label="Data Overview", tab_id="tab-overview"),
                dbc.Tab(label="Responder vs Non-Responder Analysis", tab_id="tab-responder"),
                dbc.Tab(label="Baseline Subset Summary", tab_id="tab-baseline"),
            ],
            id="tabs",
            active_tab="tab-overview",
        ),
        html.Div(id="tab-content", className="mt-4"),
    ],
    fluid=True,
)


def stacked_bar(df):
    """Return a stacked percentage bar chart by sample."""
    fig = px.bar(
        df, x="sample", y="percentage", color="population",
        title="Cell Population Percentage by Sample",
        labels={"percentage": "Percentage (%)", "sample": "Sample"},
        color_discrete_sequence=CHART_COLORS,
    )
    fig.update_layout(barmode="stack", yaxis=dict(range=[0, 100], title="Percentage (%)"))
    return fig


def overview_layout():
    """Return the Data Overview tab."""
    return html.Div([
        html.Label("Filter by sample:", className="fw-bold"),
        dcc.Dropdown(id="sample-filter", options=sample_options, value="all", clearable=False, className="mb-3"),
        dash_table.DataTable(
            id="freq-table",
            columns=[{"name": c, "id": c} for c in freq_df.columns],
            data=freq_df.to_dict("records"),
            page_size=20, sort_action="native", style_table={"overflowX": "auto"},
        ),
        dcc.Graph(id="stacked-bar-chart", figure=stacked_bar(freq_df), className="mt-4"),
    ])


def responder_layout():
    """Return the Responder vs Non-Responder tab."""
    fig = make_subplots(rows=1, cols=5, subplot_titles=POPULATIONS, horizontal_spacing=0.06)
    for i, population in enumerate(POPULATIONS, start=1):
        pop_data = plot_df[plot_df["population"] == population]
        for response, color in [("yes", RESPONDER_COLOR), ("no", NON_RESPONDER_COLOR)]:
            subset = pop_data[pop_data["response"] == response]
            fig.add_trace(
                go.Box(y=subset["percentage"], x=[response] * len(subset), name=response,
                       marker_color=color, showlegend=(i == 1)),
                row=1, col=i,
            )
    fig.update_layout(height=450, boxmode="group", legend_title_text="Response")
    for i in range(1, 6):
        fig.update_yaxes(title_text="Percentage", range=[0, 100], row=1, col=i)
        fig.update_xaxes(title_text="Response", row=1, col=i)

    return html.Div([
        dcc.Graph(figure=fig),
        dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in stats_df.columns],
            data=stats_df.to_dict("records"),
            style_table={"overflowX": "auto"},
            style_data_conditional=[{"if": {"filter_query": "{significant} = True"}, "backgroundColor": "#fff3cd"}],
        ),
    ])


def summary_col(title, df, x_col, y_col):
    """Return one baseline summary column with table and bar chart."""
    fig = px.bar(df, x=x_col, y=y_col, title=title, color=x_col, color_discrete_sequence=CHART_COLORS)
    fig.update_layout(showlegend=False)
    return dbc.Col([
        html.H5(title, className="text-center"),
        dash_table.DataTable(
            columns=[{"name": c, "id": c} for c in df.columns],
            data=df.to_dict("records"), style_table={"overflowX": "auto"},
        ),
        dcc.Graph(figure=fig),
    ], md=4)


def baseline_layout():
    """Return the Baseline Subset Summary tab."""
    return html.Div([dbc.Row([
        summary_col("Samples per Project", samples_per_project, "project", "sample_count"),
        summary_col("Responder / Non-Responder", response_counts, "response", "subject_count"),
        summary_col("Sex Distribution", sex_counts, "sex", "subject_count"),
    ], className="g-3")])


@app.callback(Output("tab-content", "children"), Input("tabs", "active_tab"))
def render_tab(active_tab):
    """Return the layout for the active tab."""
    if active_tab == "tab-responder":
        return responder_layout()
    if active_tab == "tab-baseline":
        return baseline_layout()
    return overview_layout()


@app.callback(
    Output("freq-table", "data"),
    Output("freq-table", "columns"),
    Output("stacked-bar-chart", "figure"),
    Input("sample-filter", "value"),
)
def update_overview(sample_filter):
    """Update overview table and chart for the selected sample filter."""
    df = freq_df if sample_filter == "all" else freq_df[freq_df["sample"] == sample_filter]
    return df.to_dict("records"), [{"name": c, "id": c} for c in df.columns], stacked_bar(df)


if __name__ == "__main__":
    app.run(debug=True, host="127.0.0.1", port=8050)
