import re
from datetime import datetime
from app import app,db
from sqlalchemy.orm.exc import NoResultFound, StaleDataError, MultipleResultsFound
import os, glob
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin
from app import login
from flask_login import current_user
from diagnostic_text import *
from multiprocessing import RLock, Manager
from pathlib import Path

commit_manager = Manager()
commit_lock = commit_manager.RLock() # Recursive lock because db.session.commit() is a non-thread-safe operation

class User(UserMixin,db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(64), index=True, unique=True)
    email = db.Column(db.String(120), index=True, unique=True)
    password_hash = db.Column(db.String(128))
    last_seen = db.Column(db.DateTime, default=datetime.utcnow)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def __repr__(self):
        return '<User {}>'.format(self.username)


@login.user_loader
def load_user(id):
    return User.query.get(int(id))

# class Measure(db.Model):
#     __tablename__ = 'Measure'
#     id = db.Column(db.Integer, primary_key=True)
#     kind = db.Column(db.String(140))
#     started_time = db.Column(db.String(140))
#     relative_path = db.Column(db.String(200))
#     comment = db.Column(db.String(300))
#     timestamp = db.Column(db.DateTime, index=True, default=datetime.utcnow)
#     author = db.Column(db.Integer, db.ForeignKey('user.id'))
#     plot = db.relationship('Plot', secondary="PlotVsMeasure", back_populates='measure') #, passive_deletes=True
#
#     def get_plots(self):
#         '''
#         Get the plots in which this measure appears.
#
#         Return:
#             - The paths of the plots file in a list and the kind of the plot in an other list.
#
#         Exammple:
#         >>> path_list, kind_list = my_measure.get_plots()
#         '''
#         paths = []
#         kinds = []
#         timestamp = []
#         comment = []
#         for p in self.plot:
#             paths.append(
#                 p.relative_path
#             )
#             kinds.append(
#                 p.kind
#             )
#             timestamp.append(
#                 str(p.timestamp)
#             )
#             comment.append(
#                 p.comment
#             )
#         return paths, kinds, timestamp, comment
#
#     def __repr__(self):
#         return '<Measure {}>'.format(self.id)
#
# def filename_to_abs_path(filename):
#     '''
#     Return an error flag and eventually the complete path
#     '''
#     try:
#         x = Measure.query.filter(Measure.relative_path.like("%"+os.path.basename(filename)+"%")).one()
#         return False, os.path.join(app.config['GLOBAL_MEASURES_PATH'],x.relative_path)
#     except NoResultFound:
#         print_warning("No results found when converting file %s to relative path"%filename)
#         return True, filename
#     except MultipleResultsFound:
#         print_warning("Multiple results found when converting file %s to relative path"%filename)
#         return True, filename
#
# def get_associated_plots(path_list):
#     '''
#     Given a list of paths returns a list of dictionaries containing {err:[boolean], plots[{ path:[], kind:[]}]}.
#     Where the field err is true if a db query returns nothing (i.e. the measure is not registered in the database)
#     '''
#     ret = {
#         'err':[],
#         'plots':[]
#     }
#     for single_measure_path in path_list:
#         current_plots = {
#         }
#         try:
#             measure = Measure.query.filter(Measure.relative_path == single_measure_path).one()
#             current_plots['path'],current_plots['kind'], current_plots['timestamp'], current_plots['comment'] = measure.get_plots()
#             err = False
#         except NoResultFound:
#             current_plots['path'] = []
#             current_plots['kind'] = []
#             current_plots['timestamp'] = []
#             current_plots['comment'] = []
#             err = True
#
#         ret['plots'].append(current_plots)
#         ret['err'].append(err)
#
#     return ret
