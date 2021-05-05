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

shared_var_manager = Manager()
INFO = shared_var_manager.dict()


basedir = os.path.abspath(os.path.dirname(__file__))
GLOBAL_MEASURES_PATH = "/home/lorenzo/Desktop/GPU_SDR/scripts/data/"
SECRET_KEY = 'A4Zr348j/3yX R~XKH!1mN]LZX/,?RT'
class Config(object):
    SQLALCHEMY_DATABASE_URI = 'sqlite:///' + os.path.join(basedir, 'reference_database.db')
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    SECRET_KEY = SECRET_KEY
    DEBUG = False
    FLASK_APP = "Khound"
    GLOBAL_MEASURES_PATH = "."
    APP_ADDR = "0.0.0.0"
    SESSION_TYPE = 'filesystem'
    PORT = "5000"

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
Session(app)

# MUST be after app init
from routes import *

# This has to be imported last
from handlers import *

if __name__ == '__main__':
    #app.run(debug=True)

    # measures_handler = Process(target = finished_measures_handler, args = [measure_manager.result_queue,])
    # measures_handler.deamon = True
    # measures_handler.start()

    print("Running application on addr: %s"%app.config['APP_ADDR'])
    socketio.run(app,host= app.config['APP_ADDR'], port = app.config['PORT']) #port 33 and sudo for running on local network?
