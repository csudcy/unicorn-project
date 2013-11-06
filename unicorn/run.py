import unicorn, cherrypy, json, time, os, sys, signal
from optparse import OptionParser
from datetime import datetime, timedelta
import database as db
from sqlalchemy import func
from cherrypy.lib.static import serve_file
__version__ = '0.0.1'

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

class Unicorn:

	@cherrypy.expose
	def index(self):
		return serve_file(os.path.join(static_dir,'index.html'))

	@cherrypy.expose
	def aggregate(self):
		agg_logs = db.Session.query(
					db.Log.site_id, 
					db.Log.track_type,
					func.max(db.Log.datestamp)
				).group_by(db.Log.site_id, db.Log.track_type).all()
		out = [{'site_id':al.site_id, 'datestamp':al[2], 'track_type': al.track_type} for al in agg_logs]

		db.Session.close()
		return json.dumps(out)


	@cherrypy.expose
	def problems(self):
		comp = time.time() #	- 60*60	
		agg_logs = db.Session.query(
					db.Log.site_id, 
					db.Log.track_type,
					func.max(db.Log.datestamp)
				).group_by(db.Log.site_id, db.Log.track_type).all()
		results = [
				{
					'site_id':al.site_id, 
					'time_ago': str(timedelta(seconds=  int(time.time() - al[2]))), 
					'track_type': al.track_type
				} 
			for al in agg_logs if al[2]<comp
		]
		db.Session.close()

		template = """<div>%(site_id)s last updated %(track_type)s %(time_ago)s ago</div>"""

		out = ''
		for item in results:
			out += template % item

		return out

	@cherrypy.expose
	def track(self, track_type, site_id):
		le = db.Log()
		le.datestamp = time.time()
		le.track_type = track_type
		le.site_id = site_id
		db.Session.add(le)
		db.Session.commit()
		db.Session.close()
		return 'thanks'

def command_line_handler():
    usage = """Usage: %prog [options]
note: requires postgres database server that it can connect to
    """
    parser = OptionParser(usage=usage, version='Unicorn '+__version__)
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
    return options, args, parser

def main():
    # http://bugs.python.org/issue7980 - Need to load strptime from main thread
    # so that it does not complain later in the process
    datetime.strptime('2010-01-01 00:00:00.000000', '%Y-%m-%d %H:%M:%S.%f')

    options, args, parser = command_line_handler()

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



    db.set_up(
        options.db_user,
        options.db_password,
        options.db_name,
        options.db_host,
        options.db_port
    )
    if options.reset:
        print 'Resetting trailerpark database'
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
    if options.stop:
        try:
            with open(options.pid_file, 'r') as f:
                pid = int(f.read())
                print 'Stutting down service with PID %d' % pid
                os.kill(pid, signal.SIGTERM)
                os.remove(options.pid_file)
                sys.exit(1)
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
        print 'Unable to bind to address ({0}, {1}'.format(options.ip_address, cherrypy.port)
        sys.exit(1)
    cherrypy.engine.wait(cherrypy.process.wspbus.states.STARTED)
    cherrypy.engine.block()  # Wait until the app is started before proceeding





if __name__ == '__main__':
    main()
    print 'what'