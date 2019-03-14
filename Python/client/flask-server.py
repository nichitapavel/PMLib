import datetime

from enum import Enum
from flask import Flask, request
import urllib
import urlparse

app = Flask("server")


class Operation(Enum):
    AS = 'matrix A fill start'
    AF = 'matrix A fill finish'
    BS = 'matrix B fill start'
    BF = 'matrix B fill finish'
    XS = 'matrix compute start'
    XF = 'matrix compute finish'


@app.route('/message')
def message():
    try:
        query = urllib.unquote(request.query_string)
        map = urlparse.parse_qs(query)
        timestamp = datetime.datetime.fromtimestamp(
            long(map.get('timestamp')[0]) / 1000.0
        )
        timestamp = datetime.datetime.strftime(
            timestamp,
            '%Y/%m/%d - %H:%M:%S.%f'
        )[:-2]
        print(
            'Incoming message from:\n' +
            '[device]: ' + map.get('device')[0] + '\t' +
            '[device timestamp]: ' + str(timestamp) + '\t' +
            '[operation]: ' + Operation[
                map.get('operation')[0]
            ].value
        )
    except TypeError:
        print ('The http query is malformed')
    return ''


if '__main__' == __name__:
    app.run(host='0.0.0.0')
