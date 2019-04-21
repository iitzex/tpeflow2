import calendar
import os
import time
from datetime import datetime, timezone

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import pytz
import requests
from bokeh.core.properties import value
from bokeh.embed import components
from bokeh.io import output_file, save
from bokeh.models import ColumnDataSource
from bokeh.plotting import figure
from flask import Flask, render_template, Markup

TRAFFIC = []
OUT = 'out.csv'
INDEX = 'templates/index.html'
TIMEOUT = 300
t_begin = 0
t_end = 0
tw = pytz.timezone('Asia/Taipei')
app = Flask(__name__)


def T(ts):
    if ts == None:
        return '-'
    d = datetime.fromtimestamp(ts, tz=tw)
    return d.strftime("%m/%d-%H:%M")


def H(ts):
    d = datetime.fromtimestamp(ts, tz=tw)
    return d.strftime("%H")


def day_begin_ts():
    d = datetime.now(tw)
    ts = time.time() - d.hour * 3600 - d.minute * 60 - d.second
    print(d, ts)
    return ts


def day_end_ts():
    return day_begin_ts() + 86400


def fetch(i, typ):
    headers = {
        'Host': 'api.flightradar24.com',
        'User-Agent':
        'Mozilla/5.0 (Macintosh; Intel Mac OS X 10.13; rv:60.0) Gecko/20100101 Firefox/60.0',
        'Accept': 'application/json',
        'Accept-Language': 'zh-TW,zh;q=0.8,en-US;q=0.5,en;q=0.3',
        'Referer': 'https://www.flightradar24.com/airport/tpe/arrivals',
        'origin': 'https://www.flightradar24.com',
        'DNT': '1',
        'Connection': 'keep-alive',
    }

    global t_begin
    global t_end
    t_begin = day_begin_ts()
    t_end = day_end_ts()

    params = (
        ('code', 'TPE'),
        ('plugin[]', ''),
        ('page', i),
        ('limit', '100'),

        # beging of day
        ('plugin-setting[schedulj][mode]', typ),
        ('plugin-setting[schedule][timestamp]', t_begin),
        ('plugin-setting[estimate][mode]', typ),

        # now
        # ('plugin-setting[estimate][timestamp]', day_begin_ts()),
    )

    res = requests.get(
        'https://api.flightradar24.com/common/v1/airport.json',
        headers=headers,
        params=params)

    # with open('tp.json', 'w') as f:
    #     f.write(res.text)

    return res.json()


def page(i, typ):
    global TRAFFIC
    j = fetch(i, typ)
    data = j['result']['response']['airport']['pluginData']['schedule'][typ][
        'data']
    for k, v in enumerate(data):
        t = event(v, typ)

        global t_begin
        global t_end
        if t and t_begin < t < t_end:
            TRAFFIC.append([cs(v), t, T(t), H(t), (typ[:3]).upper()])


def event(v, typ):
    status = v['flight']['status']['generic']['status']['text']

    scheduled_t = v['flight']['time']['scheduled'][typ[:-1]]
    scheduled_t = scheduled_t
    event_t = v['flight']['status']['generic']['eventTime']['utc']

    if status == 'unknown':
        return None
    elif status == 'scheduled':
        return scheduled_t
    else:
        return event_t


def cs(v):
    try:
        sn = v['flight']['identification']['number']['default']
        icao = v['flight']['airline']['code']['icao']
        cs = icao + sn[2:]
        return cs
    except TypeError as e:
        print(sn)
        return sn


def execute():
    for i in range(1, 6):
        page(i, 'departures')
    for i in range(1, 6):
        page(i, 'arrivals')

    # print(TRAFFIC)
    # with open('tp.csv', 'w') as f:
    #     for i in TRAFFIC:
    #         f.write(f'{str(i)}\n')

    df = pd.DataFrame(
        np.array(TRAFFIC), columns=['CS', 'TS', 'DATE', 'HOUR', 'TYP'])
    df.to_csv(OUT)

    return df


def plt_draw(df):
    count = df.groupby(['HOUR', 'TYP']).size().unstack()
    count.plot(kind='bar', stacked=True, color=['#fe9900', '#4D95F2'])
    plt.legend(loc=2)
    plt.savefig('tpeflow2.png')
    # plt.show()


def bokeh_draw():
    global INDEX
    df = pd.read_csv(OUT)
    output_file('main.html', title='TPEflow')
    count = df.groupby(['HOUR', 'TYP']).size().unstack()
    hour = [i for i in range(len(count.index))]
    source = {
        'time': hour,
        'ARR': count.ARR,
        'DEP': count.DEP,
    }

    source = ColumnDataSource(source)

    typ = [
        'ARR',
        'DEP',
    ]
    colors = ["#fdae6b", "#3182bd"]
    mt = os.path.getmtime(OUT)
    print(mt)
    p = figure(
        plot_height=550,
        plot_width=800,
        y_range=(0, 55),
        title='TPEFlow ' + T(mt),
        tools="hover",
        tooltips="($index)$name: @$name",
        toolbar_location=None)
    p.vbar_stack(
        typ,
        x='time',
        width=0.4,
        color=colors,
        source=source,
        legend=[value(x) for x in typ])

    p.y_range.start = 0
    p.x_range.start = -0.5
    # p.xgrid.grid_line_color = None
    # p.axis.minor_tick_line_color = None
    # p.outline_line_color = None
    p.legend.location = "top_left"
    p.legend.orientation = "horizontal"

    save(p, filename='main.html', title='TPEFlow')
    script, div = components(p)
    return script, div


def check():
    d = 'templates/'
    if not os.path.exists(d):
        os.makedirs(d)

    global OUT, TIMEOUT
    t = time.time()

    if os.path.isfile(OUT):
        mt = os.path.getmtime(OUT)
        print(t, mt, t - mt)

        if (t - mt) < TIMEOUT:
            return False

        os.remove(OUT)

    return True


@app.route('/out.json')
def summary():
    df = pd.read_csv(OUT)
    return df.to_json(orient='records')


@app.route('/')
def home():
    if check():
        global TRAFFIC
        TRAFFIC = []
        execute()

    script, div = bokeh_draw()

    html = render_template(
        'index.html', script=Markup(script), div=Markup(div))
    return html


if __name__ == '__main__':
    debug = False
    if os.environ.get('PORT') is None:
        debug = True

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug)
