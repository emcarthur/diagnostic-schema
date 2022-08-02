
#! To do: fix dissapearing dashed lines
#! To do: ignore nodes without the "Name" category
#! To do: some kerning issues on pdf export, some indent issues on notes
#! Blurry thumbnail of youtube video until resize
#! watermark
#! legend
#! legend to pdf
#! favicon
#! fix toggle box
#! refresh button top right
#! survey
#! Dr webber
#! cc info

### Input libraries nodes ###

# https://towardsdatascience.com/how-to-load-the-content-of-a-google-document-in-python-1d23fd8d8e52


import dash_interactive_graphviz
#import dash
from dash import Dash, html, dcc, Input, Output, State, callback_context
#from dash.dependencies import Input, Output, State

# import dash_html_components as html
# import dash_core_components as dcc
from graphviz import Digraph
import textwrap
import re
import dash_bootstrap_components as dbc
# from dash.dependencies import Output, Input
# from dash_extensions import Download
import uuid
# from dash_extensions.snippets import send_file
import pandas as pd
import numpy as np
import dash_dangerously_set_inner_html

import os
os.environ['PATH'] += os.pathsep + r'C:\Users\Evonne\Downloads\windows_10_msbuild_Release_graphviz-2.50.0-win32\Graphviz\bin'

### Helper functions & dictionaries to format GraphViz HTML nodes ###

html_escape_table = {
    "&": "&amp;",
    '"': "&quot;",
    "'": "&apos;",
    ">": "&gt;",
    "<": "&lt;",
    "`": "<br/>"
    }

nodeLevelToWidth = { # set default character width (nodes deeper on the tree have to be narrower)
        0:50,
        1:35,
        2:30,
        3:25,
        4:25
    }

color_table = { # colors for the different disease categories
    'Vascular':'"#FDB0B1"',
    'Infectious/Immune':'"#BDE0EF"',
    'Trauma/Mechanical':'"#E4E3E2"',
    'Metabolic/Endocrine':'"#FCC39D"',
    'Iatrogenic/Meds':'"#FCE5B0"',
    'Neoplasm':'"#C9DFB9"',
    'Social/Psych':'"#E1D3E3"',
    'Congenital/Genetic':'"#F7C8E5"',
}

def html_escape(text,nodeLevel, scalar = 10, big=False, render=False): # function to convert input text to "HTML node"-ready text
    mod = 0
    if big: # if text is bolded
        mod = 5
    if nodeLevel > 4:
        nodeLevel = 4

    width = round((nodeLevelToWidth[nodeLevel] - mod) * scalar) # set char width of node based on the default dictionary times a scalar defined by the slider
    wraptext = "`".join(textwrap.wrap(text,width=width))
    if big and not(render):
        wraptext = '`'.join([x + ' '*(1+len(x)//8) for x in wraptext.split('`')]) # a hack to fit bold text into the node better (add a space for every 8th character)

    return "".join(html_escape_table.get(c,c) for c in wraptext)

def findGoogleURL(url_in, sheet_name):
    id = re.search("\/[d]\/(\w+)\/",url_in).group(1)
    sheet_name = sheet_name.replace(" ","%20")
    return f"https://docs.google.com/spreadsheets/d/{id}/gviz/tq?tqx=out:csv&sheet={sheet_name}&range=A4:I200"

def isolateLeafNodes(df):
    leafList = []
    i = 0
    node_level_list = list(df['node_level'].diff().values[1:]) + [-1]
    node_level_list_neg = list(np.array(node_level_list) < 0)
    while i < len(node_level_list):
      if node_level_list[i] == 1:
        try:
          if (len(node_level_list[i+1:i+node_level_list_neg[i:].index(True)]) > 0) and (sum(node_level_list[i+1:i+node_level_list_neg[i:].index(True)]) == 0): # fix so not sum==0 but if all values == 0
            _ = [leafList.append(True) for x in range(1+len(node_level_list[i+1:i+node_level_list_neg[i:].index(True)]))]
            leafList.append(False)
            i = i+node_level_list_neg[i:].index(True) + 1
          else:
            i=i+1
            leafList.append(False)
        except ValueError: # fix for the end with leaf nodes
          i=i+1
          leafList.append(False)
      else:
        i=i+1
        leafList.append(False)
    return leafList[:-1]

def processDF(url):
    df = pd.read_csv(url)
    if (len(df) == 0) or (len(df.columns) != 9):
        df = pd.DataFrame([[0],['Top node'],['ERROR: Could not find your google sheet or it was formatted incorrectly!!'],[np.nan],[np.nan], [np.nan], [np.nan], [0], [np.nan]]).T
    df.columns = ['node_num', 'below',  'Name','Description', 'Diagnostics', 'Category', 'Note','node_level','child_num']
    df = df.sort_values(by='node_num').reset_index(drop=True)
    df['node_num'] = df['node_num'].astype(str)
    df = df[df['Name'].notnull()]
    df.loc[1:,'child_node_num'] = [df.loc[df['Name'] == x,'node_num'].values[0] for x in df['below'].values[1:]]
    df.loc[1:,'leaf_node'] = isolateLeafNodes(df)
    return df
### Create & update the GraphViz ###

class GraphGenerator:
    def __init__(self, df, sheet_name, width_scalar,stack, render):
        df['node_level'] = df['node_level'].astype('int64')
        df = df.fillna(value=np.nan)
        df = df.reset_index().drop('index',axis=1)
        self.schema = Digraph(sheet_name, filename='%s.gv' % sheet_name,
            node_attr={'shape': 'none','margin': '0', 'width': '0', 'height': '0'})
        self.plotNodes(df, width_scalar, render)
        self.plotEdges(df, stack)

    def plotNodes(self, df, scalar, render):
        for i,row in df.iterrows():
            node_num = row['node_num']
            node_level = row['node_level']
            html_str = '<<TABLE BORDER="0" CELLBORDER="1" CELLSPACING="0" CELLPADDING="4">'
            try:
                color = color_table[row['Category']]
            except KeyError:
                color = '"#FFFFFF"'
            if pd.notnull(row['Description']):
                html_str +=  '<TR><TD bgcolor=%s><B>%s</B><br/><font POINT-SIZE="10">%s</font></TD></TR>' % (color,html_escape(row['Name'], node_level, scalar=scalar, big=True, render=render), html_escape(row['Description'], node_level,scalar=scalar))
            elif pd.notnull(row['Diagnostics']) or pd.notnull(row['Note']):
                html_str += '<TR><TD bgcolor=%s><B>%s</B></TD></TR>' % (color,html_escape(row['Name'], node_level, scalar=scalar,big=True, render=render))
            else:
                html_str += '<TR><TD height="35" bgcolor=%s><B>%s</B></TD></TR>' % (color,html_escape(row['Name'], node_level, scalar=scalar, big=True, render=render))

            if pd.notnull(row['Diagnostics']):
                html_str += '<TR><TD><font POINT-SIZE="10" color=" #cc0000">%s</font></TD></TR>' % html_escape(row['Diagnostics'],node_level,scalar=scalar)

            if pd.notnull(row['Note']):
                html_str += '<TR><TD align="left"><font POINT-SIZE="10">'
                for note in row['Note'].split("\n"):
                    html_str = html_str + ' &#8226; %s<br align="left"/>' % html_escape(note.strip(), node_level,scalar=scalar)
                html_str += '</font></TD></TR>'

            html_str += '</TABLE>>'
            self.schema.node(str(node_num),label=html_str, fontname="helvetica")

    def plotEdges(self, df, stack):
        if not(stack):
            for i,row in df.iterrows():
                if i != 0:
                    self.schema.edge(row['child_node_num'],row['node_num'])
        else:
            for i,row in df.iterrows():
                if i !=0:
                    if not(row['leaf_node']):
                        self.schema.edge(row['child_node_num'],row['node_num'])
                    else:
                        self.schema.edge(df.loc[i-1,'node_num'],row['node_num'], style='dashed',arrowhead='none')

###

app = Dash(__name__, external_stylesheets=[dbc.themes.BOOTSTRAP])
server = app.server

# schema = GraphGenerator("../OrganizationalChart5.txt","hypoglycemia",1,True)
# initial_dot_source = schema.s.source

title_style = {"margin-top": '12px', 'margin-bottom':'10px', 'font-size':"20px", 'font-weight':'600'}
hr_style = {'width': '90%', 'margin':'auto', 'color': '#9e9e9e', 'background-color': '#9e9e9e', 'height': '1px', 'border': 'none'}

definition_block = html.Details(
    [
        html.Summary('What is a diagnostic schema?',style = title_style),
        html.P(["A diagnostic schema is a clinical reasoning tool that links diagnostic thinking to a systematic and logical organizational framework. It can provide a scaffold that allows diagnoses to be more easily remembered to ", html.Span("reduce cognitive load" ,style={"textDecoration": "underline"}),", ", html.Span("minimize anchoring bias" ,style={"textDecoration": "underline"})," towards common or recent diagnoses, " , html.Span("expand the differential" ,style={"textDecoration": "underline"}),", and " , html.Span("facilitate teaching" ,style={"textDecoration": "underline"}),"."], className="lead", style={'font-size':"13px", "margin-top": '10px'}),
        html.P("Motivation for building this app", className="lead", style={'font-size':"16px", "margin-top": '10px',"margin-bottom": '5px',  "font-weight":'450'}),
        html.P("I loved the idea of diagnostic schemas, but making them was a hassle. Some online chart makers were too inflexible and others were so overwhelmingly customizable and time consuming. Drawing them by hand was helpful, but I had to redo the whole thing when I wanted to reorganize one piece of the schema. I knew I could have fun making something better. Now, I can draft my thoughts easily in google sheets (and use spell check!). Then, I use this app to easily convert them to high-quality sharable schemas..and now you can too! Please reach out to me for questions, interest, or ideas. ", className="lead", style={'font-size':"13px"}),
    ],open=True)

directions_block = html.Details(
    [
        html.Summary('Directions',style = title_style),
        html.Div(style={'padding':'5px'}),
        #html.Img(src = "./assets/tmp.JPG", style={'width':'100%','height':'auto'}), #! remove
        html.Div(
            [
                dash_dangerously_set_inner_html.DangerouslySetInnerHTML('''
                <iframe style ="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" src="https://www.youtube.com/embed/4XTd6RnFMR8" allowfullscreen></iframe>
                '''),
            ], style={'position':'relative','width':'100%','padding-bottom':'56.25%'}),
        html.P("Make a copy of the google sheets template and set it to public to create your own schema below.", className="lead", style={'font-size':"13px","margin-top": '5px'}),
        html.Div([dbc.Button("Template & Example Google Sheet", target='_blank', href='https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/', color="secondary")], style={'text-align':'center','display':'block'}),
        html.P("Further instructions are in the document & video. Edit the nodes, specify their connections, and then copy the URL and sheet name to the boxes below.", className="lead", style={'font-size':"13px", "margin-top": '15px'}),
    ])

try_block = html.Details(
    [
        html.Summary('Try it out',style = title_style),
        html.P("Google Sheets Link (make sure it is public):", className="lead", style={ "margin-top": '10px', 'margin-bottom':'2px','font-size':"14px", 'font-weight':'600'}),
        dbc.Input(id='url_in', value='https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/edit', type="text", debounce=False,size='sm'), 
        html.P("Google sheet tab name:", className="lead", style={'font-size':"14px", "margin-top": '10px', 'margin-bottom':'2px','font-weight':'600'}),
        dbc.Row(
            [
                dbc.Col(dbc.Input(id='sheet_name', value='Example-Hypoglycemia', type="text", debounce=False,size='sm'), width=8),
                dbc.Col(html.Div(dbc.Button("Refresh", id="refresh", color="primary",size='sm'), style={'text-align':'center','display':'block'}),width=4),
            ]),
        dbc.DropdownMenu(
            [
                dbc.DropdownMenuItem("Hypoglycemia", style={'font-size':'12px'}),
                dbc.DropdownMenuItem("Chest Pain",style={'font-size':'12px'})
            ],size='sm',label="Or check out some examples:",style={ "margin-top": '15px', 'margin-bottom':'10px'},color='secondary'), 
    ])

adjust_block = html.Details(
    [
        html.Summary('Adjust & download',style = title_style),
        html.P("You can zoom and reposition the graph with your mouse in the right-panel. Click the black box in the upper right to reset the zoom.", className="lead", style={'font-size':"13px", "margin-top": '15px'}),
        dbc.Row(
            [
                dbc.Col(html.H5("Adjust width/height:", style={'font-size':"14px"}),md=5),
                dbc.Col(dcc.Slider(id='slider', min=-3, max=3, step=0.05, value=0, marks={-3: 'Taller', 3: 'Wider'}),md=7),
            ]),
        dbc.Row(
            [
                html.H5("Stack leaf nodes (narrower & less branching):", style={'font-size':"14px"}),
                html.Div(dcc.Checklist(id='stack', options=[{'label': '', 'value': 'stack'}], value=['stack']),style={'padding-left':'15px'}),
            ],style={'padding-left':'15px','padding-right':'15px'}),
        html.P("When you are happy with your schema graph, download it and share it!", className="lead", style={'font-size':"13px", "margin-top": '15px'}),
        html.Div(
            [
                dbc.Button("Download PDF schema", id="pdf_download", color="danger", style={'margin':'2px', 'margin-bottom':'10px'}), 
                dcc.Download(id="download")
            ], style={'text-align':'center','display':'block'}),
    ])

credits_block = html.Details(
    [
        html.Summary('Credits, resources & code',style = title_style),
        dcc.Markdown('''
            I created this app using many powerful, flexible, and open-source tools in python:

            - [Graphviz](https://graphviz.org/) (open source graph visualization software)
            - [PyPI Graphviz](https://graphviz.readthedocs.io/en/stable/index.html) (python Graphviz interface)
            - [Plotly Dash](https://plotly.com/dash/) (framework for building reactive web applications)
            - [Dash Graphviz](https://pypi.org/project/dash-interactive-graphviz/) (interactive Graphviz viewer for Dash)
            - [Dash Bootstrap](https://dash-bootstrap-components.opensource.faculty.ai/) (library of Bootstrap components for Dash)
            - [Inkscape](https://inkscape.org/) (open source vector graphics editor)

            I was inspired by many thoughtful diagnosticians, discussions, and texts:

            - [Clinical problem solvers](https://clinicalproblemsolving.com/) (diagnostic reasoning podcast, blog, website, app, and more)
            - [HumanDx](https://www.humandx.org/) (medical problem solving app, great practice for clinical thinking)
            - [The Calgary Guide](https://calgaryguide.ucalgary.ca/) (flow-charts for understanding disease pathophysiology)
            - Many medical journals including NEJM, JAMA, and [JGIM](https://www.sgim.org/web-only/clinical-reasoning-exercises/diagnostic-schema)
            - [Vanderbilt SOM](https://medschool.vanderbilt.edu/) & MSTP mentors & peers

            All my code is publically available at [my GitHub](https://github.com/emcarthur). Please email me at my `firstname[dot]lastname[at]gmail[dot]com` with questions or interest!
            ''', className="lead", style={'font-size':"13px", "margin-top": '15px'})
    ])

app.title = 'Diagnostic Schema Maker'
app.layout = dbc.Container(
    [
        html.H2("Medical diagnostic schema graph generator"),
        html.P("Evonne McArthur, Vanderbilt MD/PhD Student", className="lead", style={'font-size':"18px"}),
        html.Hr(style= {'color': '#9e9e9e', 'background-color': '#9e9e9e', 'height': '1px',}),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Row(
                            [
                                definition_block,
                                html.Hr(style=hr_style),
                                directions_block, 
                                html.Hr(style=hr_style),
                                try_block,
                                html.Hr(style=hr_style),
                                adjust_block,
                                html.Hr(style=hr_style),
                                credits_block,
                            ],style={"background-color": "#ededed"}
                        )
                        
                    ],md=4),
                dbc.Col(
                    [
                     #   html.Div(html.Img(src="./assets/legend2.png",alt="Legend", width="65%",), style={'text-align':'center','display':'block','margin-bottom':'10px'}),
                        html.Div(
                            [
                                dcc.Store(id='df_memory', storage_type='local'),
                                dash_interactive_graphviz.DashInteractiveGraphviz(id="gv")
                            ],style={"position":"relative", "height":"80vh", 'display':'flex','vertical-align':'top'}), #"width":"99%",'min-height':'300px','max-height':'1000px', ,'display':'flex' #'height':'100%','vertical-align': 'top','max-height':'500px', # relative vs absolute
                    ],md=8),

            ])
    ], style = {"margin-top": '15px'}
)


@app.callback(
    [Output("df_memory", "data"),
    Output("stack", "value"),
    Output("slider","value")],
    [Input('url_in', "value"),
    Input('sheet_name', "value"),
    Input('refresh', 'n_clicks')],
    [State('stack','value'),
    State('slider','value')]
)
def update_df(url_in, sheet_name, refresh, stack, width_scalar):
    df = processDF(findGoogleURL(url_in, sheet_name))
    if not(callback_context.triggered[0]['prop_id'].split('.')[0] == 'refresh'):
        if np.nansum(df['leaf_node']) > 5:
            stack = ['stack']
        else:
            stack = []
        width_scalar = 0
    return df.to_dict(), stack, width_scalar

@app.callback(
    Output("gv", "dot_source"),
    [Input('df_memory', "data"),
    Input('slider', 'value'),
    Input('stack', 'value')],
    State('sheet_name','value')
)
def display_output(df, width_scalar,stack, sheet_name):
    df = pd.DataFrame.from_dict(df)
    chart = GraphGenerator(df,sheet_name,2**width_scalar,stack, render=False)
    return chart.schema.source

@app.callback(
    Output("download", "data"),
     [Input("pdf_download", "n_clicks"),
     State('df_memory', "data"),
     State('sheet_name','value'),
     State('slider', 'value'),
     State('stack', 'value')],
     prevent_initial_call=True,
)
def func(n_clicks, df, sheet_name, width_scalar, stack):
    df = pd.DataFrame.from_dict(df)
    filename = f"{sheet_name}_{uuid.uuid1()}"
    #url_in = "https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/edit#gid=0"
    #sheet_name = "Hypoglycemia"
    chart = GraphGenerator(df,sheet_name,2**width_scalar,stack, render=True)
    chart.schema.render(f"downloads/{filename}")
    return dcc.send_file(f"downloads/{filename}.pdf")


if __name__ == '__main__':
    app.run_server(debug=False)
