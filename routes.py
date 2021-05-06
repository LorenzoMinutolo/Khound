from flask import render_template,flash, redirect,url_for,render_template_string,send_from_directory
from app import app,db
from forms import LoginForm,RegistrationForm
from flask_login import current_user, login_user
from models import User
from flask_login import login_required
from flask import request, jsonify
from werkzeug.urls import url_parse
from flask_login import logout_user
from datetime import datetime
import glob,os
import json
from flask import g
import ntpath
from pathlib import Path
import base64

@app.before_request
def before_request():
    if current_user.is_authenticated:
        current_user.last_seen = datetime.utcnow()
        db.session.commit()

@app.errorhandler(404)
def page_not_found(error):
   return render_template('404.html', title = '404'), 404

@app.route('/', methods=['GET', 'POST'])
@app.route('/index', methods=['GET', 'POST'])
@login_required
def index():
    search_string = os.path.join(app.config['PLOT_DIR'], "KHound_plot_*.png")
    try:
        plot_list = sorted(glob.glob(search_string))[-1]
        with open(plot_list, "rb") as image_file_:
            encoded_string = base64.b64encode(image_file_.read()).decode("utf-8")
        print("Loading: " + plot_list)
    except IndexError:
        encoded_string = ''
    return render_template(
        'index.html',
        title='Khound',
        main_image = encoded_string
    )


# @app.route('/explore', methods=['GET', 'POST'])
# @app.route('/explore/<path:path>', methods=['GET', 'POST'])
# @login_required
# def explore(path = ""):
#
#     if path.endswith(".h5"):
#         return single_file(path)
#
#     # Build the file tree
#     folder_struct = get_folder_struct(path)
#
#     # Compute the source selector
#     source_path, source_kind, source_perm, source_group = user_files_source()
#     source_group_list = list(set(source_group))
#     DL = {
#         'source_path':source_path,
#         'source_kind':source_kind,
#         'source_perm':source_perm,
#         'source_group':source_group,
#         }
#     DataTable_source = [dict(zip(DL,t)) for t in zip(*DL.values())] # how fun
#     return render_template(
#         'explore.html',
#         folder_struct = folder_struct,
#         source_group_set = source_group_list,
#         source_files = DataTable_source,
#         title='Explore',
#     )
#
# @app.route('/plot_serve', methods=['GET', 'POST'])
# @app.route('/plot_serve/<path:path>', methods=['GET', 'POST'])
# @login_required
# def plot_serve(path = ""):
#     current_path = os.path.join(app.config['GLOBAL_MEASURES_PATH'], path)
#     if path.endswith(".png"):
#         print('file requested: %s'%path)
#         return send_from_directory(directory=os.path.dirname(current_path), filename=os.path.basename(path))
#     elif path.endswith(".html"):
#         print('file requested: %s'%path)
#         return send_from_directory(directory=os.path.dirname(current_path), filename=os.path.basename(path))
#     else:
#         abort(404)


@app.route('/index_about')
@login_required
def index_about():
    return render_template('index_about.html', title='About')


@app.route('/index_help')
@login_required
def index_help():
    return render_template('index_help.html', title='About')


@app.route('/login', methods=['GET', 'POST'])
def login():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = LoginForm()
    if form.validate_on_submit():
        user = User.query.filter_by(username=form.username.data).first()
        if form.validate_on_submit():
            user = User.query.filter_by(username=form.username.data).first()
            if user is None or not user.check_password(form.password.data):
                flash('Invalid username or password')
                return redirect(url_for('login'))
            login_user(user, remember=form.remember_me.data)
            next_page = request.args.get('next')
            if not next_page or url_parse(next_page).netloc != '':
                next_page = url_for('index')
        return redirect(next_page)
        login_user(user, remember=form.remember_me.data)
        return redirect(url_for('index'))
    return render_template('login.html', title='Sign In', form=form)

@app.route('/logout')
def logout():
    logout_user()
    return redirect(url_for('index'))

@app.route('/register', methods=['GET', 'POST'])
def register():
    if current_user.is_authenticated:
        return redirect(url_for('index'))
    form = RegistrationForm()
    if form.validate_on_submit():
        user = User(username=form.username.data, email=form.email.data)
        user.set_password(form.password.data)
        db.session.add(user)
        db.session.commit()
        flash('Congratulations, you are now a registered user!')
        return redirect(url_for('login'))
    return render_template('register.html', title='Register', form=form)

@app.route('/user/<username>')
@login_required
def user(username):
    page = request.args.get('page', 1, type=int)
    user = User.query.filter_by(username=username).first_or_404()
    sessions = Session.query.filter_by(author = user).order_by(Session.timestamp.desc()).paginate(page, app.config["SESSIONS_PER_PAGE"], False)
    next_url = url_for('index', page=sessions.next_num) \
        if sessions.has_next else None
    prev_url = url_for('index', page=sessions.prev_num) \
        if sessions.has_prev else None
    return render_template('user.html', user=user, sessions=sessions.items,next_url=next_url, prev_url=prev_url)


@login_required
@app.route('/show_plot', methods=['GET', 'POST'])
def show_plot():
    return render_template('example_load.html')
