import dash
from dash import html, dcc, Input, Output
import os
import dash_interactive_graphviz
from graphviz import Digraph
os.environ['PATH'] += os.pathsep + r'C:\Users\Evonne\Downloads\windows_10_msbuild_Release_graphviz-2.50.0-win32\Graphviz\bin'

app = dash.Dash(__name__)
server = app.server

initial_dot_source = """
digraph  {
node[style="filled"]
a ->b->d
a->c->d
}
"""

app.layout = html.Div(
    [
        html.Div(
            dash_interactive_graphviz.DashInteractiveGraphviz(id="gv"),
            style=dict(flexGrow=1, position="relative",height='20%'),
        ),
        html.Div(
            [
                html.H3("Selected element"),
                html.Div(id="selected"),
                html.H3("Dot Source"),
                dcc.Textarea(
                    id="input",
                    value=initial_dot_source,
                    style=dict(flexGrow=1, position="relative"),
                ),
                html.Button("Download Image", id="btn_image"),
                dcc.Download(id="download-image"),
                html.H3("Engine"),
                dcc.Dropdown(
                    id="engine",
                    value="dot",
                    options=[
                        dict(label=engine, value=engine)
                        for engine in [
                            "dot",
                            "fdp",
                            "neato",
                            "circo",
                            "osage",
                            "patchwork",
                            "twopi",
                        ]
                    ],
                ),
            ],
            style=dict(display="flex", flexDirection="column"),
        ),
    ],
    style=dict(position="absolute", height="100%", width="100%", display="flex"),
)


@app.callback(
    [Output("gv", "dot_source"), Output("gv", "engine")],
    [Input("input", "value"), Input("engine", "value")],
)
def display_output(value, engine):
    return value, engine

@app.callback(
    Output("download-image", "data"),
    Input("btn_image", "n_clicks"),
    prevent_initial_call=True,
)
def func(n_clicks):
    s = Digraph(initial_dot_source, filename="test.gv", format="pdf")
    s.render(f"downloads/x")
    return dcc.send_file(f"downloads/x.pdf")



@app.callback(Output("selected", "children"), [Input("gv", "selected")])
def show_selected(value):
    return html.Div(value)


if __name__ == "__main__":
    app.run_server(debug=True)