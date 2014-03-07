from datetime import datetime, timedelta
from optparse import OptionParser
import json
import operator
import os
import signal
import sys
import time

CURRENT_DIRECTORY = os.path.dirname(os.path.abspath(__file__))
PARENT_DIRECTORY = os.path.split(CURRENT_DIRECTORY)[0]
LIB_PATH = os.path.join(CURRENT_DIRECTORY, 'lib')

sys.path.append(PARENT_DIRECTORY)
sys.path.append(LIB_PATH)
sys.path.append(os.path.join(LIB_PATH, 'cherrypy'))

from cherrypy.lib.static import serve_file
from sqlalchemy import func
import cherrypy
import requests

from unicorn import database as db
import unicorn

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

PRODUCER = {
    'BASE_URL': 'https://producer.artsalliancemedia.com/',
    'USER': 'adfuser',
    'PASS': '[c0ldfus10n]'
}

SITE_LOOKUP = {}
SITE_LOOKUP_NEXT_LOAD = 0
def get_site_names():
    """
    Get a lookup of cadien_id -> name from Producer
    Cached for 10 minutes
    """
    global SITE_LOOKUP, SITE_LOOKUP_NEXT_LOAD
    if SITE_LOOKUP_NEXT_LOAD < time.time():
        SITE_LOOKUP = _get_site_names()
        SITE_LOOKUP_NEXT_LOAD = time.time() + 10*60
    return SITE_LOOKUP

def _get_site_names():
    print 'LOADING SITES FROM PRODUCER!'
    def producer_get(url, params=None):
        #Get the sites from Producer
        params = params or {}

        response = requests.get(
            PRODUCER['BASE_URL']+url,
            verify = False,
            params = {
                'username': PRODUCER['USER'],
                'password': PRODUCER['PASS'],
            }
        )
        response.raise_for_status()
        result = response.json()
        #Copied from adfuser/producer/endpoint.py
        if 'messages' in result and result['messages']:
            raise Exception('Producer returned messages: {0}'.format(result['messages']))
        if 'data' not in result:
            raise Exception(
                'Expected Producer to return a result with "data" key (returned keys were {0}).'.format(
                    result.keys()
                ))
        data = result['data']
        filtered_count = data.pop('count', None)
        if len(data.keys()) != 1:
            raise Exception(
                'Expected Producer to return data with a single key (returned keys were {0}).'.format(
                    data.keys()
                ))
        return data.values()[0]

    #Get stuff from Producer
    site_maps = producer_get(
        '/circuit_core/complex_maps',
        params={
            'q': json.dumps({'source':'cadien'})
        }
    )

    #Make a lookup for the complexes
    site_lookup = {}
    for site_map in site_maps:
        site_lookup[str(site_map['external_id'])] = site_map['name']

    return site_lookup

class Unicorn(object):
    @cherrypy.expose
    def index(self):
        return serve_file(os.path.join(static_dir,'index.html'))

    @cherrypy.expose
    def aggregate(self):

        #Get the site names
        site_lookup = {}
        try:
            site_lookup = get_site_names()
        except Exception, ex:
            print 'Error retrieving complexes from Producer:'
            print ex

        #Get the latest logs
        agg_logs = db.Session.query(
            db.Log.site_id,
            db.Log.track_type,
            func.max(db.Log.datestamp)
        ).group_by(
            db.Log.site_id,
            db.Log.track_type
        ).all()

        #Construct the return structure
        now = time.time()
        out = []
        for al in agg_logs:
            seconds_ago = int(now - al[2])
            out.append({
                'site_id': al.site_id,
                'site_name': site_lookup.get(al.site_id, 'Unknown - %s' % al.site_id),
                'datestamp': al[2],
                'seconds_ago': seconds_ago,
                'time_ago': str(timedelta(seconds = seconds_ago)),
                'track_type': al.track_type
            })
        db.Session.close()

        #Sort nicely
        out.sort(key=operator.itemgetter('site_name', 'track_type', 'seconds_ago'))

        return json.dumps(out)

    @cherrypy.expose
    def track(self, track_type, site_id, data=None):
        le = db.Log(
            datestamp=time.time(),
            track_type=track_type,
            site_id=site_id,
            data=data
        )
        db.Session.add(le)
        db.Session.commit()
        db.Session.close()
        return 'thanks'


def command_line_handler():
    usage = """Usage: %prog [options]
note: requires postgres database server that it can connect to
    """
    parser = OptionParser(usage=usage, version='Unicorn '+unicorn.__version__)
    parser.add_option('-d', '--daemon',
                        dest='daemon',
                        default=False,
                        action='store_true',
                        help='Daemonize when set')
    parser.add_option('-s', '--stop',
                        dest='stop',
                        default=False,
                        action='store_true',
                        help='Stop damon running unicorn')
    parser.add_option('-r', '--reset',
                        dest='reset',
                        default=False,
                        action='store_true',
                        help='Specify to reset the database')
    parser.add_option('-p', '--port',
                        dest='port',
                        default=5000,
                        type='int',
                        action='store',
                        help='Port that the cherrypy webserver runs on, default 5000')
    parser.add_option('-i', '--ip_address',
                        dest='ip_address',
                        type='string',
                        default='0.0.0.0',
                        action='store',
                        help='IP address to server cherrypy from, default 0.0.0.0')
    parser.add_option('-u', '--db_user',
                        dest='db_user',
                        type='string',
                        default='postgres',
                        action='store',
                        help='Database user to connect to postgres with, default postgres')
    parser.add_option('-w', '--db_password',
                        dest='db_password',
                        type='string',
                        default='postgres',
                        action='store',
                        help='Database password for the db user specified, default postgres')
    parser.add_option('-n', '--db_name',
                        dest='db_name',
                        type='string',
                        default='unicorn',
                        action='store',
                        help='Name of the database used by Unicorn, default unicorn')
    parser.add_option('-o', '--db_host',
                        dest='db_host',
                        type='string',
                        default='127.0.0.1',
                        action='store',
                        help='IP address that the database is being served from, default 127.0.0.1')
    parser.add_option('-t', '--db_port',
                        dest='db_port',
                        type='string',
                        default='5432',
                        action='store',
                        help='Port that the database is running from, default 5432')
    parser.add_option('-q', '--pid_file',
                        dest='pid_file',
                        default='/var/run/unicorn.pid',
                        action='store',
                        help='Location of pid file when daemonizing, default /var/run/unicorn.pid')
    options, args = parser.parse_args()
    return options, args


def main():
    # http://bugs.python.org/issue7980 - Need to load strptime from main thread
    # so that it does not complain later in the process
    datetime.strptime('2010-01-01 00:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')

    options, args = command_line_handler()

    ################################################
    #       Sort out CherryPy
    ################################################

    #Make AutoReloader exit not restart
    cherrypy.engine._restart = cherrypy.engine.restart
    cherrypy.engine.restart = cherrypy.engine.exit

    cherrypy.tree.mount(Unicorn(), '/', {
        '/static': {
            'tools.staticdir.on': True,
            'tools.staticdir.dir': static_dir,
            'tools.response_headers.on': True,
            'tools.response_headers.headers': [
                ('Cache-Control', 'max-age=3600, must-revalidate'),
                ('Proxy-Connection', 'close')
            ]
        }
    })

    cherrypy.server.socket_host = options.ip_address
    cherrypy.server.socket_port = options.port

    ################################################
    #       Database setup
    ################################################

    db.set_up(
        options.db_user,
        options.db_password,
        options.db_name,
        options.db_host,
        options.db_port
    )
    if options.reset:
        print 'Resetting unicorn database'
        db.tear_down(
            options.db_user,
            options.db_password,
            options.db_name,
            options.db_host,
            options.db_port
        )
    db.create_tables(
        options.db_user,
        options.db_password,
        options.db_name,
        options.db_host,
        options.db_port
    )

    ################################################
    #       Process management
    ################################################

    if options.stop:
        try:
            with open(options.pid_file, 'r') as f:
                pid = int(f.read())
                print 'Stutting down service with PID %d' % pid
                os.kill(pid, signal.SIGTERM)
                os.remove(options.pid_file)
        except IOError:
            print 'No PID file found, aborting shutdown.'
        sys.exit(1)

    if options.daemon:
        from cherrypy.process.plugins import Daemonizer, PIDFile
        if os.path.exists(options.pid_file):
            print 'Cannot start process - PID file already exists: %s' % options.pid_file
            sys.exit(1)

        # Daemonise the process
        Daemonizer(cherrypy.engine).subscribe()
        # -- Manage the pid: this will create the pid file on start-up and delete on shutdown
        PIDFile(cherrypy.engine, options.pid_file).subscribe()

    if hasattr(cherrypy.engine, 'signal_handler'):
        cherrypy.engine.signal_handler.subscribe()
    if hasattr(cherrypy.engine, 'console_control_handler'):
        cherrypy.engine.console_control_handler.subscribe()
    try:
        cherrypy.engine.start()
    except IOError:
        print 'Unable to bind to address {0}:{1}'.format(options.ip_address, cherrypy.port)
        sys.exit(1)
    cherrypy.engine.wait(cherrypy.process.wspbus.states.STARTED)
    cherrypy.engine.block()  # Wait until the app is started before proceeding


if __name__ == '__main__':
    main()
