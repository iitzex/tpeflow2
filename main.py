import os
import time
import requests
from datetime import datetime, timedelta
import numpy as np
import pandas as pd
import matplotlib.pyplot as plt
from flask import Flask, render_template
from bokeh.embed import components
from bokeh.core.properties import value
from bokeh.io import save, show, output_file
from bokeh.plotting import figure
from bokeh.models import ColumnDataSource

TRAFFIC = []
FN = 'out.csv'
TIMEOUT = 120
app = Flask(__name__)


def T(ts):
    if ts == None:
        return '-'
    return datetime.fromtimestamp(ts).strftime("%m/%d-%H:%M")


def hour(ts):
    return datetime.fromtimestamp(ts).strftime("%H")


def day_begin_ts():
    d = datetime.now().date()
    t = datetime(d.year, d.month, d.day, 0, 0, 0, 0)
    ts = time.mktime(t.timetuple())
    return ts


def day_end_ts():
    return day_begin_ts() + 86400


def fetch(i, t):
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

    params = (
        ('code', 'TPE'),
        ('plugin[]', ''),
        ('page', i),
        ('limit', '100'),

        # beging of day
        ('plugin-setting[schedulj][mode]', t),
        ('plugin-setting[schedule][timestamp]', day_begin_ts()),
        ('plugin-setting[estimate][mode]', t),

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
        t = status(v, typ)
        tstr = T(t)

        t_begin = day_begin_ts()
        t_end = day_end_ts()
        if t and t_begin < t < t_end:
            # print((i - 1) * 100 + k, cs(v), tstr, hour(t), t)
            TRAFFIC.append([cs(v), t, tstr, hour(t), (typ[:3]).upper()])


def status(v, typ):
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
    sn = v['flight']['identification']['number']['default']
    icao = v['flight']['airline']['code']['icao']
    cs = icao + sn[2:]

    return cs


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
    df.to_csv('out.csv')


def plt_draw(df):
    count = df.groupby(['HOUR', 'TYP']).size().unstack()
    count.plot(kind='bar', stacked=True, color=['#fe9900', '#4D95F2'])
    plt.legend(loc=2)
    plt.savefig('tpeflow2.png')
    # plt.show()


def bokeh_draw():
    output_file('templates/index.html')

    df = pd.read_csv(FN)

    count = df.groupby(['HOUR', 'TYP']).size().unstack()
    hour = [i for i in range(len(count.index))]
    source = {
        'time': hour,
        'ARR': count.ARR,
        'DEP': count.DEP,
    }

    source = ColumnDataSource(source)

    typ = ['ARR', 'DEP']
    colors = ["#FFCC00", "#3366FF"]
    p = figure(
        plot_height=550,
        plot_width=800,
        title='TPEFlow',
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

    save(p)
    return p


def check():
    global FN, TIMEOUT
    t = time.time()

    mt = os.path.getmtime(FN)
    # print(t, mt, t - mt)

    return ((t - mt) > TIMEOUT)


@app.route('/')
def home():
    if check():
        execute()

    bokeh_draw()

    return render_template('index.html')


if __name__ == '__main__':
    debug = False
    if os.environ.get('PORT') is None:
        debug = True

    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, debug=debug)

