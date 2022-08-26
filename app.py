from flask_table import Table, Col, LinkCol
from flask import Flask, Markup, request, url_for, session
from flask_socketio import SocketIO, emit
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from flask_login import LoginManager
from flask_bootstrap import Bootstrap
from flask_login import current_user
from flask_session import Session
#from flask.ext.session import Session

import json
import os
import time
import numpy as np
from multiprocessing import Process, Lock, Manager, Process
from Khound import make_spec_file, shared_dict, shared_dict_lock, meas_lock



basedir = os.path.abspath(os.path.dirname(__file__))

SECRET_KEY = 'A4Zr348j/3yX R~XKH!1mN]LZX/,?RT'
class Config(object):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'reference_database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = SECRET_KEY
    DEBUG = False
    FLASK_APP = "Khound"
    GLOBAL_MEASURES_PATH = "."
    APP_ADDR = "127.0.0.1"
    SESSION_TYPE = 'filesystem'
    PORT = "5000"
    GLOBAL_MEASURES_PATH = "/home/lorenzo/Khound/data/"
    PLOT_DIR = "/home/lorenzo/Khound/plot/"
    MAIN_DIR = "/home/lorenzo/Khound/"

app = Flask(__name__)
app.config.from_object(Config)
# app.secret_key =SECRET_KEY

# app.config['SESSION_TYPE']
db = SQLAlchemy(app)
migrate = Migrate(app, db)
login = LoginManager(app)
login.login_view = 'login'
bootstrap = Bootstrap(app)
socketio = SocketIO(app)
socketio.init_app(app, cors_allowed_origins="*")

# Session(app)

# MUST be after app init
from routes import *

# This has to be imported last
from handlers import *

with shared_dict_lock:
    shared_dict['master_clock_rate'] = 200e6
    shared_dict['start'] = 10e6
    shared_dict['end'] = 1300e6
    shared_dict['gain'] = 50
    shared_dict['resolution'] = 1000
    shared_dict['iterations'] = 2000
    shared_dict['full_spec_every'] = 10*60
    shared_dict['full_spec_enable'] = True
    shared_dict['plot_full_spec_enable'] = False
    shared_dict['plot_time'] = 60*60*2





if __name__ == '__main__':
    #app.run(debug=True)
    try:
        os.chdir(app.config['PLOT_DIR'])
    except OSError:
        os.mkdir(app.config['PLOT_DIR'])
        os.chdir(app.config['PLOT_DIR'])
    os.chdir(app.config['MAIN_DIR'])

    try:
        os.chdir(app.config['GLOBAL_MEASURES_PATH'])
    except OSError:
        os.mkdir(app.config['GLOBAL_MEASURES_PATH'])
        os.chdir(app.config['GLOBAL_MEASURES_PATH'])
    os.chdir(app.config['MAIN_DIR'])

    app.add_url_rule(app.config['PLOT_DIR'], endpoint='plot',
                 view_func=app.send_static_file)

    print("Running application on addr: %s"%app.config['APP_ADDR'])
    socketio.run(app,host= app.config['APP_ADDR'], port = app.config['PORT']) #port 33 and sudo for running on local network?
