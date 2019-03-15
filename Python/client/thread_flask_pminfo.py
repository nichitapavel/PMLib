import logging
import signal
import socket
import struct
import sys
import threading
import urllib
import urlparse
from Queue import Empty, Queue
from datetime import datetime
from optparse import OptionParser

from enum import Enum
from flask import request, Flask

logging.basicConfig(
    level=logging.INFO,
    # filename='thread-flask-pminfo.log',
    format='[%(process)d][%(name)s][%(levelname)s] %(message)s'
)


class Operation(Enum):
    AS = 'matrix A fill start'
    AF = 'matrix A fill finish'
    BS = 'matrix B fill start'
    BF = 'matrix B fill finish'
    XS = 'matrix compute start'
    XF = 'matrix compute finish'


# Create a single input and a single output queue for all threads.
marks = Queue()
app = Flask("server")


@app.route('/message')
def message():
    try:
        query = urllib.unquote(request.query_string)
        params = urlparse.parse_qs(query)
        timestamp = datetime.fromtimestamp(
            long(params.get('timestamp')[0]) / 1000.0
        )
        # timestamp = datetime.datetime.strftime(
        #     timestamp,
        #     '%Y/%m/%d - %H:%M:%S.%f'
        # )[:-2]

        msg = {
            'device': params.get('device')[0],
            'device timestamp': params.get('timestamp')[0],
            'local timestamp': timestamp,
            'operation': params.get('operation')[0]
        }
        marks.put(msg)
    except TypeError:
        logging.warnings('The http query is malformed')
    return ''


class FlaskThread(threading.Thread):
    def __init__(self, marks):
        super(FlaskThread, self).__init__()
        self.name = 'FlaskThread'
        self.marks = marks
        self.stop_request = threading.Event()
        self.logger = logging.getLogger(__name__)
        log = logging.getLogger('werkzeug')
        log.setLevel(logging.ERROR)

    def run(self):
        app.run(host='0.0.0.0')

    def join(self, timeout=None):
        self.stop_request.set()
        super(FlaskThread, self).join(timeout)


class PMInfoThread(threading.Thread):
    def __init__(self, marks):
        super(PMInfoThread, self).__init__()
        self.name = type(self).__name__
        self.marks = marks
        self.stop_request = threading.Event()
        self.logger = logging.getLogger(type(self).__name__)

    def run(self):
        dev_name = 'APCape8L'
        send_all_data(client, struct.pack("i", 9))
        msg = struct.pack("i", len(dev_name))
        msg += dev_name
        msg += struct.pack("i", 0)
        send_all_data(client, msg)
        count = 0
        last_ten_thousands = 0.0

        while not self.stop_request.isSet():
            try:
                lines = receive_data(client, "i")
                lines_array = []

                for lin in xrange(lines):
                    line_power = receive_data(client, "d")
                    lines_array.append("%.2f" % (line_power))

                wattage = 0.0
                if len(lines_array) != 0:
                    wattage = lines_array[0]
                    last_ten_thousands += float(wattage)
                    count += 1

                if count > 10000:
                    average = last_ten_thousands / count
                    if average < 2500:
                        self.logger.info('average below 2500')
                        self.logger.info('average %d with count %d', average, count)
                        self.stop_request.set()
                    else:
                        self.logger.info('average higher 2500')
                        self.logger.info('average %d with count %d', average, count)
                        last_ten_thousands = 0.0
                        count = 0

                self.logger.info(wattage)

                if not self.marks.empty():
                    mark = self.marks.get()
                    self.marks.task_done()
                    self.logger.info(
                        '[device:' + mark.get('device') +
                        '][device timestamp:' + mark.get('device timestamp') +
                        '][local timestamp:' + str(mark.get('local timestamp')) +
                        '][operation:' + mark.get('operation') +
                        ']'
                    )
            except Empty:
                continue

    def join(self, timeout=None):
        self.stop_request.set()
        super(PMInfoThread, self).join(timeout)


def handler():
    if mode == "read":
        send_all_data(client, struct.pack("i", 0))
        client.close()


def receive_data(client, datatype):
    try:
        msg = client.recv(struct.calcsize(datatype))
        if len(msg) == 0:
            client.close()
            sys.exit(1)
    except Exception:
        client.close()
        sys.exit(1)

    try:
        return struct.unpack(datatype, msg)[0]
    except struct.error as err:
        print('Error found! Here are the details:')
        # noinspection SpellCheckingInspection
        print('datatype: ' + datatype + '\t msg: ' + msg)
        print err
        client.close()
        sys.exit(1)


def send_all_data(client, msg):
    totalsent = 0
    while totalsent < len(msg):
        sent = client.send(msg[totalsent:])
        if sent == 0:
            raise RuntimeError
        totalsent = totalsent + sent


def read_device(client, dev_name, frequency):
    send_all_data(client, struct.pack("i", 9))

    msg = struct.pack("i", len(dev_name))
    msg += dev_name
    msg += struct.pack("i", frequency)
    send_all_data(client, msg)

    status = receive_data(client, "i")

    if status == -1:
        print "Device %s does not exist!" % (dev_name)

    elif status == -2:
        frequency = receive_data(client, "i")
        print "Device %s only works at least %d Hz!" % (dev_name, frequency)

    elif status == 0:
        while True:
            lines = receive_data(client, "i")
            lines_array = []

            sum_ = 0
            sample = ""
            for lin in xrange(lines):
                line_power = receive_data(client, "d")
                sum_ += line_power
                sample += "%5.2f : " % (line_power)
                lines_array.append("%.2f" % (line_power))

            print "%s - %s =  %2.2f" % (datetime.now().strftime("%H:%M:%S.%f")[:-2], sample[:-2], sum_)
        # send_all_data(client, struct.pack("i", 1) )


def main():
    # Parsear linea de comandos
    parser = OptionParser("usage: %prog -s|--server SERVER:PORT\n"
                          "       %prog -r|--read DEVNAME [-f|--freq FREQ]")
    parser.add_option("-s", "--server", action="store", type="string", dest="server")
    parser.add_option("-r", "--read", action="store", type="string", dest="device")
    parser.add_option("-f", "--freq", action="store", type="int", dest="freq", default=0)

    (options, args) = parser.parse_args()

    global client, mode
    mode = 'read'

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect((options.server.split(":")[0], int(options.server.split(":")[1])))
    signal.signal(signal.SIGINT, handler)

    pool = [PMInfoThread(marks=marks), FlaskThread(marks=marks)]
    pool[0].daemon = True

    for thread in pool:
        thread.start()


if __name__ == '__main__':
    main()
