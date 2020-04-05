import dash
import dash_core_components as dcc
import dash_html_components as html
from dash.dependencies import Input, Output
import flask
import pandas as pd
import plotly.express as px

from model import variables, Infection


lang = "cs"

stylesheets = ['https://codepen.io/chriddyp/pen/bWLwgP.css']

server = flask.Flask(__name__)
app = dash.Dash(__name__, external_stylesheets=stylesheets, server=server)
app.title = dict(
    en="Epidemic control calculator",
    cs="Kalkulačka epidemických opatření",
)[lang]


def get_slider(id, var):
    return html.Div([
        html.P(var.name[lang]),
        dcc.Slider(id=id, min=var.min, max=var.max, step=var.step, tooltip={"always_visible": True}, value=var.default),
    ], style={"width": "400px"})

app.layout = html.Div([
    dcc.Location(id='url', refresh=False),
    html.Div(id="invisible", style={"display": "none"}),
    html.Div([
        dcc.Link('English', href='/en'),
        html.Br(),
        dcc.Link('Česky', href='/cs'),
    ], style={"display": "none"}),
    html.Div([
        html.Div([
            html.P(dict(
                en="X axis:",
                cs="Osa X:",
            )[lang]),
            dcc.Dropdown(id="x", value="tracing_rate", options=[{"value": k, "label": v.name[lang]} for k, v in variables.items()]),
        ])
    ] + [
        get_slider(id, var) for id, var in variables.items() if var.cat == 0
    ], style={"width": "400px", "padding-right": "50px", "float": "left"}),
    html.Div([
        get_slider(id, var) for id, var in variables.items() if var.cat == 1
    ], style={"width": "400px", "padding-right": "50px", "float": "left"}),
    html.Div([
        html.Div([
            html.P(dict(
                en="Daily infection rates (will be scaled to sum up to R0):",
                cs="Relativní infekčnost po dnech (bude přepočteno na součet R0):",
            )[lang]),
            dcc.Input(id="infection_rates", value=", ".join(map(str, Infection.infection_rates)), size=40),
        ]),
        html.Div([
            html.P(dict(
                en="Daily symptom onsets (%, the rest is considered asymptomatic):",
                cs="Začátek příznaků po dnech (%, zbytek je považován za bez příznaků):",
            )[lang]),
            dcc.Input(id="symptom_rates", value=", ".join(map(str, Infection.symptoms)), size=40),
        ]),
    ] + [
        get_slider(id, var) for id, var in variables.items() if var.cat == 2
    ], style={"width": "600px", "float": "left"}),
    html.Div([dcc.Graph(id="graph_r")], style={"float": "left", "clear": "both"}),
    html.Div([dcc.Graph(id="graph_g")], style={"float": "left"}),
    
    dcc.Markdown("""
### O modelu

Tato kalkulačka je matematickým modelem, který simuluje změnu reprodukčního čísla a denního nárůstu infikovaných, v závislosti několika faktorech, které můžeme ovlivnit:
  - především hodnotou **základního reprodukčního čísla** R0, které pro potřeby této kalkulačky závisí jak na viru samotném, tak na fyzickém a sociálním prostředí (počasí, míra kontaktů, mobilita, karanténní opatření)
  - na **testování a následné izolaci potvrzených pacientů** - model je řízen proměnnými:
    - procento pacientů s příznaky, které se daří testovat
    - zpoždění ve dnech, se kterým se to daří, počítáno od nástupu příznaků
  - na **trasování kontaktů těchto pacientů a následné izolaci těchto kontaktů** - model je řízen proměnnými:
    - procento kontaktů, které se daří vystopovat
    - zpoždění ve dnech, se kterým se to daří, počítáno od testu pacienta
  - model dále umožňuje nastavit efektivitu izolace (platí pro pozitivně otestované i trasované kontakty)

&nbsp;

Model dále závisí na vlastnostech epidemie, o kterých pro COVID-19 máme jistou mlhavou představu, a které lze jen ztěží ovlivnit:
  - **míra infekčnosti pacienta**, pro jednotlivé dny od počátku nakažení
    - hodnoty jsou bez rozměru, model si je přenásobí vhodnou konstantou, aby součet dával dohromady zadané základní reprodukční číslo
  - **rozložení příchodu příznaku**, pro jednotlivé dny od počátku nakažení
    - hodnoty udávají procento pacientů, kteří pocítí příznaky daný den
  - **procento nakažených, kteří vůbec nepocítí příznaky**
    - kalkulačka toto procento vypočítá jako doplněk procent pacientů s příznaky do 100 %
  - míra, o kterou jsou tito **nakažení bez příznaků méně infekční**, než pacienti s příznaky

&nbsp;

Model a předvolené hodnoty vychází hlavně ze zdrojů:
- Ferretti et al, Quantifying SARS-CoV-2 transmission suggests epidemic control with digital contact tracing - [link](https://science.sciencemag.org/content/early/2020/03/30/science.abb6936)
- Hellewell e al, Feasibility of controlling COVID-19 outbreaks by isolation of cases and contacts - [link](https://www.sciencedirect.com/science/article/pii/S2214109X20300747)

&nbsp;

Budu rád za připomínky - github: [github.com/ProtD/covid-r](https://github.com/ProtD/covid-r), email: vrszavináčemailtečkacz
""", style={"clear": "both"}),
])

@app.callback(
    [Output('graph_r', 'figure'),
     Output('graph_g', 'figure')],
    [Input('url', 'pathname'),
     Input('x', 'value'),
     Input('infection_rates', 'value'),
     Input('symptom_rates', 'value')
    ] + [Input(id, 'value') for id in variables.keys()]
)
def get_data(url_path, x, infection_rates, symptom_rates, *values):
    if url_path is None or len(url_path) <= 1:
        lang = "cs"
    else:
        lang = url_path[1:]

    inf = Infection()
    try:
        infection_rates = [x.strip() for x in infection_rates.split(",")]
        infection_rates = [float(x) for x in infection_rates if x != ""]
        symptom_rates = [x.strip() for x in symptom_rates.split(",")]
        symptom_rates = [float(x) for x in symptom_rates if x != ""]
    except:
        return None
    for k, v in zip(variables.keys(), values):
        if k == "r0":
            inf.set_rates(v, infection_rates, symptom_rates)
        else:
            setattr(inf, k, v)
    df = inf.iterate(x)
    fig_r = px.line(
        df, x=x, y="r", range_y=(0.0, 6.0), width = 900, height=600,
        labels={"r": dict(
            en="Effective reproduction number (R)",
            cs="Efektivní reprodukční číslo (R)",
        )[lang], x: variables[x].name[lang]},
    )
    fig_r.update_traces(mode='markers+lines')
    fig_g = px.line(
        df, x=x, y="perc", range_y=(-30.0, +50.0), width = 900, height=600,
        labels={"perc": dict(
            en="Daily growth (%)",
            cs="Denní nárůst (%)",
        )[lang], x: variables[x].name[lang]},
    )
    fig_g.update_traces(mode='markers+lines')
    return fig_r, fig_g

if __name__ == '__main__':
    app.run_server(debug=False, host='0.0.0.0', port=8050)


# Run e.g. with:
# sudo iptables -t nat -A PREROUTING -p tcp --dport 80 -j REDIRECT --to-port 8050
# gunicorn app:server -b :8050 --workers 4
