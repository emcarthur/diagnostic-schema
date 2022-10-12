
#! To do: fix dissapearing dashed lines
#! To do: ignore nodes without the "Name" category
#! To do: some kerning issues on pdf export, some indent issues on notes: https://forum.graphviz.org/t/unwanted-space-around-html-font-tags/460/4
#! Blurry thumbnail of youtube video until resize
#! refresh button top right
#! wont work with node that starts with a number (or sheet)
#! check url, check sheet, check formatting and add alert popups
#! left-align text if long
#! split app.py to multiple

### Input libraries nodes ###

# https://towardsdatascience.com/how-to-load-the-content-of-a-google-document-in-python-1d23fd8d8e52


import dash_interactive_graphviz
from dash import Dash, html, dcc, Input, Output, State, callback_context
from graphviz import Digraph
import textwrap
import re
import requests
import dash_bootstrap_components as dbc
import uuid
import pandas as pd
import numpy as np
import dash_dangerously_set_inner_html
import gspread
from datetime import datetime

from urllib.error import HTTPError


from dotenv import load_dotenv # Only needed to run locally
load_dotenv() # Only needed to run locally

import os
os.environ['PATH'] += os.pathsep + r'C:\Users\Evonne\Downloads\windows_10_msbuild_Release_graphviz-2.50.0-win32\Graphviz\bin' # Only needed to run locally

# https://www.youtube.com/watch?v=n2aQ6QOMJKE
# https://devcenter.heroku.com/articles/config-vars%20
# https://stackoverflow.com/questions/47446480/how-to-use-google-api-credentials-json-on-heroku
credentials = {
  "type": "service_account",
  "project_id": "diagnostic-schema",
  "private_key_id": os.environ["PRIVATE_KEY_ID"],
  "private_key": os.environ["PRIVATE_KEY"].replace('\\n', '\n'),
  "client_email": os.environ["CLIENT_EMAIL"],
  "client_id": os.environ["CLIENT_ID"],
  "auth_uri": "https://accounts.google.com/o/oauth2/auth",
  "token_uri": "https://oauth2.googleapis.com/token",
  "auth_provider_x509_cert_url": "https://www.googleapis.com/oauth2/v1/certs",
  "client_x509_cert_url": os.environ["CLIENT_X509_CERT_URL"]
}

sheets = gspread.service_account_from_dict(credentials).open_by_key("11ZsKtxpXqw5BZdEp05BiFES9l8gqbDNhsOw7lF5cXgw")
welcomesurvey = sheets.worksheet("welcomesurvey")
schemanames = sheets.worksheet("schemanames")
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

def findSheetTabNames(url_in):
    if 'http' not in url_in:
        return None # Just so the app doesn't totally quit if it can't find the sheet
    html_txt = requests.get(url_in).text
    pattern = re.compile(r'<div class="goog-inline-block docs-sheet-tab-caption">(.+?)</div>')
    tab_names = []
    for match in pattern.finditer(html_txt):
        tab_names.append(match.group(1))
    return tab_names

def findGoogleURL(url_in, sheet_name):
    if re.search("\/[d]\/([\w-]+)\/", url_in) is not None:
        regex = re.search("\/[d]\/([\w-]+)\/",url_in)
        id = regex.group(1)
    else:
        id = ""
#        alert_url = True
    sheet_name = sheet_name.replace(" ","%20")
    return f"https://docs.google.com/spreadsheets/d/{id}/gviz/tq?tqx=out:csv&sheet={sheet_name}&range=A4:I200"

# raise HTTPError(req.full_url, code, msg, hdrs, fp) urllib.error.HTTPError: HTTP Error 404: Not Found

def identifyNodeLevels(df):
    df['node_level'] = 0
    df['child_num'] = 1

    for i,r in df.iloc[1:,:].iterrows():
        currentChild = r['below']
        counter = 0
        while currentChild != "Top node":
            if currentChild not in df['Name'].values:
                df.drop(i, inplace=True,axis=0)
                break
            counter+=1
            currentChild = df.loc[df['Name'] == currentChild, "below"].values[0]
        df.loc[i,"node_level"] = counter
    
    df = df[df['below'].notnull() & df['Name'].notnull()].reset_index().drop('index',axis=1) # ignore nodes without missing necessary info

    for i,r in df.iloc[1:,:].iterrows():
        df.loc[i,"child_num"] = sum(df.iloc[:i+1,:]['below'] == r['below'])
    
    return df
        
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
    # This is a mess. To clean up.
    try:
        df = pd.read_csv(url)
    except HTTPError as err:
         df = pd.read_csv('https://docs.google.com/spreadsheets/d/1i-tuYPWaG5TTAxjksTlV7aE5S1jOR69Ers6WH1_M8SQ/gviz/tq?tqx=out:csv&sheet=Error&range=A4:I200')
    if (len(df) == 0) or (len(df.columns) != 9): # if missing data
        df = pd.read_csv('https://docs.google.com/spreadsheets/d/1i-tuYPWaG5TTAxjksTlV7aE5S1jOR69Ers6WH1_M8SQ/gviz/tq?tqx=out:csv&sheet=Error&range=A4:I200')
    df.columns = ['node_num', 'below',  'Name','Description', 'Diagnostics', 'Category', 'Note','node_level','child_num']
    df = df[df['below'].notnull() & df['Name'].notnull()] # ignore nodes without missing necessary info
    if (len(df) == 0) or (len(df.columns) != 9): # if missing data 
        df = pd.read_csv('https://docs.google.com/spreadsheets/d/1i-tuYPWaG5TTAxjksTlV7aE5S1jOR69Ers6WH1_M8SQ/gviz/tq?tqx=out:csv&sheet=Error&range=A4:I200')
        df.columns = ['node_num', 'below',  'Name','Description', 'Diagnostics', 'Category', 'Note','node_level','child_num']
    df.iloc[0,1] = 'Top node' #in case this was accidentally edited
    df = identifyNodeLevels(df)
    
    max_base = max(df['node_level'])
    df['node_num'] = 10**max_base
    for i,r in df.iloc[1:,:].iterrows():
        df.loc[i,'node_num'] = r["child_num"]*10**(max_base - r['node_level']) + df.loc[df['Name'] == r['below'],"node_num"].values[0]
    df = df.sort_values(by='node_num').reset_index(drop=True)
    df['node_num'] = df['node_num'].astype(str)
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
            self.schema.node(str(node_num),label=html_str, fontname="Helvetica")

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

title_style = {"margin-top": '10px', 'margin-bottom':'8px', 'font-size':"18px", 'font-weight':'600'}
hr_style = {'width': '90%', 'margin':'auto', 'color': '#9e9e9e', 'background-color': '#9e9e9e', 'height': '1px', 'border': 'none'}

# definition_block = html.Details(
#     [
#         html.Summary('What is a diagnostic schema?',style = title_style),
#         html.P(["A diagnostic schema is a clinical reasoning tool that links diagnostic thinking to a systematic and logical organizational framework. It can provide a scaffold that allows diagnoses to be more easily remembered to ", html.Span("reduce cognitive load" ,style={"textDecoration": "underline"}),", ", html.Span("minimize anchoring bias" ,style={"textDecoration": "underline"})," towards common or recent diagnoses, " , html.Span("expand the differential" ,style={"textDecoration": "underline"}),", and " , html.Span("facilitate teaching" ,style={"textDecoration": "underline"}),"."], className="lead", style={'font-size':"13px", "margin-top": '10px'}),
#         html.P([html.Span("Motivation behind the app: " ,style={"font-weight": '560'})," I loved the idea of diagnostic schemas, but making them was a hassle. Some online chart makers were too inflexible and others were so overwhelmingly customizable and time consuming. Drawing them by hand was helpful, but I had to redo the whole thing when I wanted to reorganize one piece of the schema. I knew I could have fun making something better. Now, I can draft my thoughts easily in google sheets (and use spell check!). Then, I use this app to easily convert them to high-quality sharable schemas..and now you can too! Please reach out to me for questions, interest, or ideas. "], className="lead", style={'font-size':"13px"}),
#     ],open=True)

directions_block = html.Details(
    [
        html.Summary('Directions',style = title_style),
        html.P(["A diagnostic schema is a clinical reasoning tool that links diagnostic thinking to a systematic and logical organizational framework to ", html.Span("reduce cognitive load" ,style={"font-style": "italic"}),", ", html.Span("minimize anchoring bias" ,style={"font-style": "italic"})," towards common or recent diagnoses, " , html.Span("expand the differential" ,style={"font-style": "italic"}),", and " , html.Span("facilitate teaching" ,style={"font-style": "italic"}),"."], className="lead", style={'font-size':"13px", "margin-top": '10px'}),
        html.P(["The best way to learn why and how to use Schematify is to watch it in action:"], className="lead", style={'font-size':"13px", "margin-top": '10px'}),
        html.Div(
            [
                dash_dangerously_set_inner_html.DangerouslySetInnerHTML('''
                <iframe style ="position:absolute;top:0;left:0;width:100%;height:100%;border:0;" src="https://www.youtube.com/embed/u-gjhf2LF4I" allowfullscreen></iframe>
                '''),
            ], style={'position':'relative','width':'100%','padding-bottom':'56.25%'}),
        html.P("Make a copy of the google sheets template, set it to public, and follow the directions to create your own schema below.", className="lead", style={'font-size':"13px","margin-top": '5px'}),
        html.Div([dbc.Button("Template & Example Google Sheet", target='_blank', href='https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/', color="secondary")], style={'text-align':'center','display':'block'}, className='mb-3'),
        # html.P("Further instructions are in the document & video. Edit the nodes, specify their connections, and then copy the URL and sheet name to the boxes below.", className="lead", style={'font-size':"13px", "margin-top": '15px'}),
    ])

try_block = html.Details(
    [
        html.Summary('Create your schema',style = title_style),
        html.P("Google Sheets Link (make sure it is public):", className="lead", style={ "margin-top": '10px', 'margin-bottom':'2px','font-size':"14px", 'font-weight':'600'}),
        dbc.Input(id='url_in', value='https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/edit', type="text", debounce=False), 
        html.P("Google sheet tab name:", className="lead", style={'font-size':"14px", "margin-top": '10px', 'margin-bottom':'2px','font-weight':'600'}),
        dbc.Row(
            [
                dbc.Col(dcc.Dropdown(id="sheet_name", clearable=False), width=8),
                dbc.Col(html.Div(dbc.Button("Refresh", id="refresh", color="primary",), style={'text-align':'center','display':'block'}),width=4),
            ]),
        dbc.DropdownMenu(
            [
                dbc.DropdownMenuItem("Hypoglycemia", style={'font-size':'12px'}, id='hypoglycemiaExample'),
                dbc.DropdownMenuItem("Chest Pain (Toy example)",style={'font-size':'12px'}, id='chestpainExample'),
                dbc.DropdownMenuItem("Rhabdomyolysis (Genetics)",style={'font-size':'12px'}, id='rhabdoExample')
            ],size='sm',label="Or check out some examples:",style={ "margin-top": '15px', 'margin-bottom':'10px'},color='secondary'), 

        # dbc.Alert(
        #     "URL not recognized! Make sure it is publicly shared.",
        #     id="alert-url",
        #     dismissable=True,
        #     is_open=False,
        #     color="danger",
        #     className="mt-3"
        # ),
        # dbc.Alert(
        #     "Sheet name not recognized! (URL is recognized).",
        #     id="alert-name",
        #     dismissable=True,
        #     is_open=False,
        #     color="danger",
        #     className="mt-3"
        # ),
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
                dbc.Col(html.H5("Stack leaf nodes (narrower & less branching):", style={'font-size':"14px"}),md=10),
                dbc.Col(html.Div(dcc.Checklist(id='stack', options=[{'label': '', 'value': 'stack'}], value=['stack'])),md=2),
            ]),
        html.P("When you are happy with your schema graph, download it and share it!", className="lead", style={'font-size':"13px", "margin-top": '15px'}),
        html.Div(
            [
                dbc.Button("Download PDF schema", id="pdf_download", color="danger", style={'margin':'2px', 'margin-bottom':'10px'}), 
                dcc.Download(id="download")
            ], style={'text-align':'center','display':'block'}),
    ])

legend_block = html.Details(
    [
        html.Summary('Legend',style = title_style),
        html.P("Colors correspond to categories of disease pathophysiology:", className="lead", style={'font-size':"13px", "margin-top": '15px'}),
        html.Div(html.Img(src="./assets/legend.png",alt="Legend",width='75%'), style={'text-align':'center','display':'block','margin-bottom':'10px'}),
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

            - [Clinical problem solvers](https://clinicalproblemsolving.com/) (diagnostic reasoning podcast, website, and more)
            - [HumanDx](https://www.humandx.org/) (medical problem solving app)
            - [The Calgary Guide](https://calgaryguide.ucalgary.ca/) (flow-charts for understanding disease pathophysiology)
            - [Frameworks for Internal Medicine](https://shop.lww.com/Frameworks-for-Internal-Medicine/p/9781496359308) by Andre Mansoor
            - Many medical journals including NEJM, JAMA, and [JGIM](https://www.sgim.org/web-only/clinical-reasoning-exercises/diagnostic-schema)
            
            Special thanks to: 
            - [Chase J. Webber, DO](https://medicine.vumc.org/person/chase-j-webber-do)
            - [Vanderbilt SOM](https://medschool.vanderbilt.edu/), MSTP mentors, & peers

            All my code is publically available at [my GitHub](https://github.com/emcarthur/diagnostic-schema). Please email me at my `firstname[dot]lastname[at]gmail[dot]com` with questions or interest!
            ''', className="lead", style={'font-size':"13px", "margin-top": '15px'})
    ])

state_to_abbrev = { "Alabama": "AL", "Alaska": "AK", "Arizona": "AZ", "Arkansas": "AR", "California": "CA", "Colorado": "CO", "Connecticut": "CT", "Delaware": "DE", "Florida": "FL", "Georgia": "GA", "Hawaii": "HI", "Idaho": "ID", "Illinois": "IL", "Indiana": "IN", "Iowa": "IA", "Kansas": "KS", "Kentucky": "KY", "Louisiana": "LA", "Maine": "ME", "Maryland": "MD", "Massachusetts": "MA", "Michigan": "MI", "Minnesota": "MN", "Mississippi": "MS", "Missouri": "MO", "Montana": "MT", "Nebraska": "NE", "Nevada": "NV", "New Hampshire": "NH", "New Jersey": "NJ", "New Mexico": "NM", "New York": "NY", "North Carolina": "NC", "North Dakota": "ND", "Ohio": "OH", "Oklahoma": "OK", "Oregon": "OR", "Pennsylvania": "PA", "Rhode Island": "RI", "South Carolina": "SC", "South Dakota": "SD", "Tennessee": "TN", "Texas": "TX", "Utah": "UT", "Vermont": "VT", "Virginia": "VA", "Washington": "WA", "West Virginia": "WV", "Wisconsin": "WI", "Wyoming": "WY", "District of Columbia": "DC", "American Samoa": "AS", "Guam": "GU", "Northern Mariana Islands": "MP", "Puerto Rico": "PR", "United States Minor Outlying Islands": "UM", "U.S. Virgin Islands": "VI", "Canada":"Canada", "Mexico":"Mexico", "Outside North America":"ONA" }
roles = ["Attending physician","Fellow/Resident","Advanced practice provider (NP/PA)","Other professional provider","Medical student","Other professional student","Undergraduate student","Other - researcher","Other - educator", "Other - programmer","Other"]
specialty = ["Internal medicine generalist", "Internal medicine subspecialist", "Pediatric generalist", "Pediatric specialist", "Med/Peds","Family medicine","Emergency medicine", "Surgical specialty","Other","NA"]
survey = html.Div(
    [
        html.P("Please help us identify our user base for research and improvement purposes. Thanks!"),
        dbc.InputGroup(
            [
                dbc.Select(
                    options=[ {"label": x, "value": x} for x in roles], placeholder="Closest clinical role", id='role'
                ),
            ],
            className="mb-3",
        ),
        dbc.InputGroup(
            [
                dbc.Select(
                    options=[ {"label": x, "value": x} for x in specialty], placeholder="Closest clinical specialty", id='specialty'
                ),
            ],
            className="mb-3",
        ),
        dbc.InputGroup(
            [
                dbc.Select(
                    options=[{"label":x, "value":y} for x,y in state_to_abbrev.items()], placeholder="Geographic location", id='location'
                ),
            ],
            className="mb-3",
        ),
        dbc.InputGroup(
            [
                dbc.InputGroupText("Optional feedback or thoughts?"),
                dbc.Textarea(id='feedback'),
            ],
        ),

    ]
)

modal = html.Div(
    [
        dbc.Modal(
            [
                dbc.ModalHeader(
                    dbc.ModalTitle("Welcome user survey"), close_button=False
                ),
                dbc.ModalBody(
                    survey
                ),
                dbc.ModalFooter(
                    [
                        dbc.Button("I've completed this survey before. Skip to app!", id="completed-dismiss", color='secondary'),
                        dbc.Button("Submit", id="submit-dismiss")
                    ]
                )

            ],
            id="modal-dismiss",
            keyboard=False,
            backdrop="static",
            is_open=True,
            centered=True,
        ),
    ],
)


app.title = 'Diagnostic Schema Maker'
app.layout = dbc.Container(
    [
        html.H2("Schematify: Medical diagnostic schema generator"),
        html.P("Evonne McArthur, Vanderbilt MD/PhD Student", className="lead", style={'font-size':"18px"}),
        modal,
        html.Hr(style= {'color': '#9e9e9e', 'background-color': '#9e9e9e', 'height': '1px',}),
        dbc.Row(
            [
                dbc.Col(
                    [
                        dbc.Row(
                            [
                                # definition_block,
                                # html.Hr(style=hr_style),
                                directions_block, 
                                html.Hr(style=hr_style),
                                try_block,
                                html.Hr(style=hr_style),
                                adjust_block,
                                html.Hr(style=hr_style),
                                legend_block,
                                html.Hr(style=hr_style),                                
                                credits_block,
                            ],style={"background-color": "#ededed"}
                        ),
                    ],md=4),
                dbc.Col(
                    [
                     #   html.Div(html.Img(src="./assets/legend2.png",alt="Legend", width="65%",), style={'text-align':'center','display':'block','margin-bottom':'10px'}),
                        html.Div("Reset zoom:",style={'text-align':'right', 'font-size':"13px", 'margin-bottom':'-6px','color':'#000000'}),
                        html.Div(
                            [
                                dcc.Store(id='df_memory', storage_type='local'),
                                dash_interactive_graphviz.DashInteractiveGraphviz(id="gv")
                            ],style={"position":"relative", "height":"80vh", 'display':'flex','vertical-align':'top'}), #"width":"99%",'min-height':'300px','max-height':'1000px', ,'display':'flex' #'height':'100%','vertical-align': 'top','max-height':'500px', # relative vs absolute
                            html.Hr(style= {'color': '#9e9e9e', 'background-color': '#9e9e9e', 'height': '1px','margin':'0px'}),

                    ],md=8),

            ]),
        dbc.Row(
            [
                html.Div("© 2022 Copyright - Evonne McArthur",style={'text-align':'right', 'font-size':"13px", "margin-top": '10px','color':'#666666'})

            ]
        )
    ], style = {"margin-top": '15px'}
)

# https://stackoverflow.com/a/72754236
from PyPDF2 import PdfFileReader, PdfFileWriter
from PyPDF2 import PageObject
landscape_footer = PdfFileReader(open('./assets/landscape_footer.pdf', 'rb')).getPage(0)
portrait_footer = PdfFileReader(open('./assets/portrait_footer.pdf', 'rb')).getPage(0)
landscape_footer_width = landscape_footer.mediaBox.getWidth(); landscape_footer_height = landscape_footer.mediaBox.getHeight()
portrait_footer_width = portrait_footer.mediaBox.getWidth(); portrait_footer_height = portrait_footer.mediaBox.getHeight()
def add_footer(schema_pdf):
    schema = PdfFileReader(open(schema_pdf + '.pdf', 'rb')).getPage(0)
    schema_width = schema.mediaBox.getWidth(); schema_height = schema.mediaBox.getHeight()

    if schema_width/schema_height > 1.2:
    # Landscape
    # 504 height x 792 width
        merged_schema = PageObject.createBlankPage(None, 792, 612)
        scalar = min(504/schema_height, 792/schema_width)
        center_translate_height = int((504-(scalar*schema_height))/2)
        center_translate_width = int((792-(scalar*schema_width))/2)
        merged_schema.mergeScaledTranslatedPage(schema,scalar,0+center_translate_width,108+center_translate_height)
        merged_schema.mergeScaledTranslatedPage(landscape_footer,1,0,0)
    else:
    # Portrait
    # 684 height x 612 width
        merged_schema = PageObject.createBlankPage(None, 612, 792)
        scalar = min(684/schema_height, 612/schema_width)
        center_translate_height =  int((684-(scalar*schema_height))/2)
        center_translate_width = int((612-(scalar*schema_width))/2)
        merged_schema.mergeScaledTranslatedPage(schema,scalar,0+center_translate_width,108+center_translate_height)
        merged_schema.mergeScaledTranslatedPage(portrait_footer,1,0,0)

    writer = PdfFileWriter()
    writer.addPage(merged_schema)

    with open(schema_pdf + '.schema.pdf', 'wb') as f:
        writer.write(f)

@app.callback(
    Output("modal-dismiss", "is_open"),
    [Input("submit-dismiss", "n_clicks"),
     Input("completed-dismiss", "n_clicks"),],
    [State("modal-dismiss", "is_open"),
     State("role","value"),
     State("specialty","value"),
     State("location","value"),
     State("feedback","value")],
)
def toggle_modal(n_close, n_complete, is_open, role, specialty, location, feedback):
    if n_close:
        welcomesurvey.append_row([0,role, specialty, location, feedback, datetime.now().strftime("%Y/%m/%d %H:%M:%S")])
        return not is_open
    elif n_complete:
        welcomesurvey.append_row([1, role, specialty, location, feedback, datetime.now().strftime("%Y/%m/%d %H:%M:%S")])
        return not is_open
    return is_open

# @app.callback(
#     [Output("url_in", "value"),
#     Output("sheet_name", "value")],
#     [Input('hypoglycemiaExample', 'n_clicks'),
#     Input('chestpainExample','n_clicks'),
#     Input('rhabdoExample','n_clicks')],
#     prevent_initial_call=True,
# )
# def show_examples(hypoglycemiaExample, chestpainExample, rhabdoExample):
#     url_in = 'https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/edit'
#     if callback_context.triggered[0]['prop_id'].split('.')[0] == 'hypoglycemiaExample':
#         sheet_name = "Example-Hypoglycemia"
#         return url_in, sheet_name
#     elif callback_context.triggered[0]['prop_id'].split('.')[0] == 'chestpainExample':
#         sheet_name = 'ToyExample-ChestPain'
#         return url_in, sheet_name

#     url_in = 'https://docs.google.com/spreadsheets/d/1i-tuYPWaG5TTAxjksTlV7aE5S1jOR69Ers6WH1_M8SQ/edit'
#     if callback_context.triggered[0]['prop_id'].split('.')[0] == 'rhabdoExample':
#         sheet_name = 'Rhabdo (Genetics)'
    
#     return url_in, sheet_name

@app.callback(
    [Output("sheet_name","options"),
    Output("sheet_name","value"),],
    [Input('url_in','value'),],
    [State('sheet_name','value'),],
)
def updateSheetTabOptions(url_in, sheet_name):
    tab_names = findSheetTabNames(url_in)
    if sheet_name in tab_names:
        default_tab = sheet_name
    else:
        default_tab = tab_names[0] # will default to first tab
    options = [{"label": x, "value": x} for x in tab_names]
    return options, default_tab

@app.callback(
    [Output("df_memory", "data"),
    Output("stack", "value"),
    Output("slider","value"),],
    # Output("alert-url",'is_open'),
    # Output("alert-name",'is_open')],
    [Input('sheet_name', "value"),
    Input('refresh', 'n_clicks'),
    Input('hypoglycemiaExample', 'n_clicks'),
    Input('chestpainExample','n_clicks'),
    Input('rhabdoExample','n_clicks')],
    [State('url_in', "value"),
    State('stack','value'),
    State('slider','value'),]
    # State("alert-url",'is_open'),
    # State("alert-name",'is_open')]
)
def update_df(sheet_name, refresh, hypoglycemiaExample, chestpainExample, rhabdoExample, url_in, stack, width_scalar): #, alert_url_open, alert_name_open):
    if callback_context.triggered[0]['prop_id'].split('.')[0] == 'hypoglycemiaExample':
        sheet_name = "Example-Hypoglycemia"
        url_in = 'https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/edit'
    elif callback_context.triggered[0]['prop_id'].split('.')[0] == 'chestpainExample':
        sheet_name = 'ToyExample-ChestPain'
        url_in = 'https://docs.google.com/spreadsheets/d/1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc/edit'
    elif callback_context.triggered[0]['prop_id'].split('.')[0] == 'rhabdoExample':
        sheet_name = 'Rhabdo (Genetics)'
        url_in = 'https://docs.google.com/spreadsheets/d/1i-tuYPWaG5TTAxjksTlV7aE5S1jOR69Ers6WH1_M8SQ/edit'
    
    url = findGoogleURL(url_in, sheet_name) #, alert_url, alert_name

    df = processDF(url)
    if not(callback_context.triggered[0]['prop_id'].split('.')[0] == 'refresh'):
        if np.nansum(df['leaf_node']) > 5:
            stack = ['stack']
        else:
            stack = []
        width_scalar = 0
    else:
        if ("1yZAG8AUSNQ7pYZ0hjcZaO87pbCgF7YQkwTbGc3ct9Bc" not in url_in) and ("1i-tuYPWaG5TTAxjksTlV7aE5S1jOR69Ers6WH1_M8SQ" not in url_in):
            schemanames.append_row([sheet_name, datetime.now().strftime("%d/%m/%Y %H:%M:%S")])
    if ("" in url_in) and sheet_name == ("Rhabdo (Genetics)"):
        stack = []
    return df.to_dict(), stack, width_scalar#, #, #

# @app.callback(
#     Output("alert-fade", "is_open"),
#     [Input("alert-toggle-fade", "n_clicks")],
#     [State("alert-fade", "is_open")],
# )
# def toggle_alert(n, is_open):
#     if n:
#         return not is_open
#     return is_open

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
    filename = f"Schematify_{uuid.uuid1()}"
    chart = GraphGenerator(df,sheet_name,2**width_scalar,stack, render=True)
    chart.schema.render(f"downloads/{filename}")
    _  = add_footer(f"downloads/{filename}")
    return dcc.send_file(f"downloads/{filename}.schema.pdf")


if __name__ == '__main__':
    app.run_server(debug=False)
