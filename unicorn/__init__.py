import os, sys
__version__ = '0.0.1'

static_dir = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'static')

sys.path.append(os.path.join(os.path.dirname(os.path.abspath(__file__)), 'lib'))