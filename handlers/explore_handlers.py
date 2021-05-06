import json
import os,glob
import time
import numpy as np
from flask_socketio import emit
from flask_login import current_user
from app import socketio, app, session
from diagnostic_text import *
# from models import add_file_selected, user_files_selected, remove_file_selected, clear_user_file_selected, add_file_source, consolidate_sources
# from models import remove_source_group, clear_user_file_source, remove_file_source, measure_path_from_name, measure_path_response, get_associated_plots, remove_path_selected
import datetime
from Khound import make_spec_file, shared_dict, shared_dict_lock, meas_lock, file_write_lock, plot_files
import multiprocessing
from multiprocessing import Process, Lock, Manager, Process


def get_latest_plot_tag():
    '''
    get the last plotted timestamp
    '''
    plot = sorted(glob.glob(os.path.join(app.config['PLOT_DIR'], "KHound_plot_*.png")))[-1]
    # print(os.path.basename(plot))
    x = os.path.basename(plot).split('.')[0].split('plot_')[1]
    return x

def plot_full_spec(args):
    '''
    Plot the last <time> periodically upon new data present in data folder.
    '''
    shared_dict = args[0]
    file_write_lock = args[1]
    socketio = args[2]
    print('Running plotter process now')
    plot_time = 60*30 # in seconds, from last file received
    while shared_dict['plot_full_spec_enable']:
        #get the file list
        search_string = os.path.join(app.config['GLOBAL_MEASURES_PATH'], "Khound_*.txt")
        # print(search_string)
        with file_write_lock:
            meas_list = sorted(glob.glob(search_string))
        # print(meas_list)
        latest_meas_tag = int(os.path.basename(meas_list[-1]).split('.')[0].split('_')[1])
        latest_plot_tag = int(get_latest_plot_tag())
        if latest_meas_tag!=latest_plot_tag:
            print(latest_meas_tag)
            print(latest_plot_tag)
            meas_list_int = [int(os.path.basename(m).split('.')[0].split('_')[1]) for m in meas_list]
            meas_list_base = [os.path.basename(m) for m in meas_list]
            file_list = []
            for m in range(len(meas_list_int)):
                if latest_meas_tag - meas_list_int[m] < plot_time:
                    file_list.append(meas_list_base[m])
            file_list = sorted(file_list)

            # with file_write_lock:
            print('plotting...')
            #processes are not PIL locked, matplotlib works way faster
            pp = Process(target = plot_files, args = [shared_dict,file_list,'matplotlib',False,app.config['GLOBAL_MEASURES_PATH'],app.config['PLOT_DIR']])
            pp.start()
            pp.join()
            print("New plot available, reloading mainpage")
            reload_page_command(socketio)
        else:
            print('Nothing to plot')
            time.sleep(1)

# plot_full_spec_process = Process(target = plot_full_spec, args = [shared_dict,file_write_lock,socketio])
shared_dict['plot_full_spec_enable'] = False
@socketio.on('init_plotter')
def init_plotter(msg, methods=['GET', 'POST']):
    print('request to start plotter received')
    # if not plot_full_spec_process.is_alive():
    if not shared_dict['plot_full_spec_enable']:
        print("starting plotter")
        plot_full_spec_process = socketio.start_background_task(target = plot_full_spec, args = [shared_dict,file_write_lock,socketio])
        shared_dict['plot_full_spec_enable'] = True
    else:
        print('plotter already initialized')


def run_full_spec(args):
    '''
    run full spec periodically
    '''
    shared_dict = args[0]
    meas_lock = args[1]
    socketio = args[2]
    print('Running full spec process now.')
    start_time = time.time()
    while shared_dict['full_spec_enable']:
        wait_time = np.abs(time.time()-start_time)
        # print(wait_time)
        if wait_time>shared_dict['full_spec_every']:
            with meas_lock:
                status_update('Starting scan loop', socketio)
                daq_thread = multiprocessing.Process(target=make_spec_file, args=(shared_dict, None,
                    shared_dict['master_clock_rate'],
                    shared_dict['start'],
                    shared_dict['end'],
                    shared_dict['gain'],
                    shared_dict['resolution'],
                    shared_dict['iterations'])
                )
                # daq_thread.daemon = True
                daq_thread.start()
                while daq_thread.is_alive():
                    with shared_dict_lock:
                        status_update(shared_dict['progress'], socketio)
                    time.sleep(0.127)
                status_update(shared_dict['progress'], socketio)
                daq_thread.join()
        else:
            with shared_dict_lock:
                shared_dict['progress'] = "Updating in %d s" % int(shared_dict['full_spec_every'] - wait_time)
            status_update(shared_dict['progress'], socketio)
            time.sleep(1)
        # else:
        #     time.sleep(1)

full_spec_process = Process(target = run_full_spec, args = [shared_dict,meas_lock,socketio])


def status_update(message, socketio, UUID = None):
    message = str(message)
    if len(message) > 1024:
        print_warning("transmitting very long status update")
    msg = {'status':message}
    if UUID is not None:
        socketio.emit('status_update',json.dumps(msg),namespace="/"+UUID)
    else:
        socketio.emit('status_update',json.dumps(msg))
        print("------------>sending status update")

def reload_page_command(socketio, UUID = None):
    msg = {'command':'reload'}
    if UUID is not None:
        socketio.emit('command',json.dumps(msg),namespace="/"+UUID)
    else:
        socketio.emit('command',json.dumps(msg))
        print("------------>sending reload command")

@socketio.on('start_full')
def start_full(msg, methods=['GET', 'POST']):
    print("starting full from window UUID: " + msg['window_UUID'])
    window_UUID = msg['window_UUID']
    with shared_dict_lock:
        shared_dict['full_spec_enable'] = True
    # full_spec_process = Process(target = run_full_spec, args = [shared_dict,meas_lock,socketio])
    full_spec_process = socketio.start_background_task(target = run_full_spec, args = [shared_dict,meas_lock,socketio])
    # full_spec_process.start()

@socketio.on('stop_full')
def stop_full(msg, methods=['GET', 'POST']):
    print("stopping full from window UUID: " + msg['window_UUID'])
    window_UUID = msg['window_UUID']
    with shared_dict_lock:
        shared_dict['full_spec_enable'] = False
    while full_spec_process.is_alive():
        status_update("stopping full_spec_thread", socketio)
        time.sleep(0.136)
    try:
        full_spec_process.join()
    except AssertionError:
        pass
    with shared_dict_lock:
        time.sleep(0.0954)
        shared_dict['progress'] = 'full_spec thread stopped'
        status_update(shared_dict['progress'], socketio)


@socketio.on('ping')
def ping(msg, methods=['GET', 'POST']):
    print("received ping from window UUID: " + msg['window_UUID'])
    window_UUID = msg['window_UUID']
    print(window_UUID)

@socketio.on('scan_all')
def plot_all(msg, methods=['GET', 'POST']):
    print("Sending data to UUID: " + msg['window_UUID'])
    window_UUID = msg['window_UUID']
    print("Scan request received")

    master_clock_rate = 52e6
    start = 10e6
    end = 500e6
    gain = 30
    resolution = 10000
    iterations = 200
    # status_update('Starting scan loop', window_UUID)
    # daq_thread = multiprocessing.Process(target=make_spec_file, args=(shared_dict, None, master_clock_rate, start,end, gain, resolution, iterations))
    # # daq_thread.daemon = True
    # daq_thread.start()
    # while daq_thread.is_alive():
    #     with shared_dict_lock:
    #         status_update(shared_dict['progress'], window_UUID)
    #     time.sleep(0.127)
    # status_update(shared_dict['progress'], window_UUID)
    # daq_thread.join()
    print('thread joined')




# def get_small_timestamp():
#     return datetime.datetime.now().strftime("%H%M%S")

# @socketio.on('explore_clear_selection')
# def clear_all_selected_files(msg):
#     '''
#     Clear the selectef file list.
#     '''
#     msg_clear_warning = "Clearing all temporary files of user %s"%current_user
#     clear_user_file_selected()
#     print_warning(msg_clear_warning)
#
# @socketio.on('remove_from_selection')
# def remove_from_selection(msg):
#     '''
#     Remove file from selected list
#     '''
#     old_list = user_files_selected()
#     filepath = measure_path_from_name(msg['file'])
#     if filepath in old_list:
#
#         ret = remove_file_selected(filepath)
#         old_list = user_files_selected()
#         socketio.emit('update_selection',json.dumps({'files':old_list,'err':int(ret)}))
#     else:
#         print_warning('cannot remove %s from selected list, not found'%filepath)
#
# @socketio.on('add_to_selection')
# def add_to_selection(msg):
#     '''
#     Add file from selected list
#     '''
#     filepath = measure_path_from_name(msg['file'])
#     ret = add_file_selected(filepath)
#     old_list = user_files_selected()
#     socketio.emit('update_selection',json.dumps({'files':old_list,'err':int(ret)}))
#
# @socketio.on('request_selection')
# def send_selection_update(msg):
#     socketio.emit('update_selection',json.dumps({'files':user_files_selected(),'err':int(1)}))
#
#
# @socketio.on('request_selection_file_list')
# def send_selection_update_file_list(msg):
#     folders_req = msg['folders']
#     dbs = []
#     plot = []
#     files = []
#     sizes = []
#     kinds = []
#     parent= []
#     for folder in folders_req:
#         dbs_, plot_, files_, sizes_, kinds_, parent_ = measure_path_response(folder,msg['recursive'])
#         parent += parent_
#         dbs+=dbs_
#         plot+=plot_
#         files+=files_
#         sizes+=sizes_
#         kinds+=kinds_
#     ret = list(zip(dbs, plot, files, sizes, kinds, parent))
#     socketio.emit('update_selection_file_list',json.dumps({'items':ret}))
#
# @socketio.on('request_selection_plot_list')
# def send_selection_update_file_list(msg):
#     file_req = msg['file']
#     path = measure_path_from_name(file_req)
#     plots = get_associated_plots([path])['plots'][0]
#     ret = []
#     for i in range(len(plots['path'])):
#         ret.append([
#             plots['path'][i],
#             plots['kind'][i],
#             plots['timestamp'][i],
#             plots['comment'][i],
#         ])
#     # print(ret)
#
#     socketio.emit('update_selection_plot_list',json.dumps({'items':ret}))
#
#
#
# @socketio.on('add_to_selection_from_folder')
# def select_from_folder(msg):
#     '''
#     Select all the files in a folder.
#     '''
#     #relative_path = os.path.join(msg['path'], msg['folder'])
#     relative_path = msg['folder']
#     ret = True
#     for root, dirs, files in os.walk(os.path.join(app.config["GLOBAL_MEASURES_PATH"],relative_path), topdown=False):
#         for name in files:
#             if name.endswith('.h5'):
#                 ret = ret and add_file_selected(measure_path_from_name(name))
#     socketio.emit('update_selection',json.dumps({'files':user_files_selected(),'err':int(ret)}))
#
# @socketio.on('remove_selection_from_folder')
# def remove_select_from_folder(msg):
#     ret = remove_path_selected(msg['folder'])
#     socketio.emit('update_selection',json.dumps({'files':user_files_selected(),'err':int(ret)}))
#
#
# @socketio.on('analysis_modal_config')
# def define_possible_analysis(msg):
#     file_list = user_files_selected()
#     config = Analysis_Config(file_list) # TODO: move it to user space.
#     config.check_file_list() # Determine which analysis on which file
#     session['analysis_config'] = config
#     socketio.emit('analyze_config_modal',json.dumps(config.config))
#
#
# @socketio.on('explore_add_source')
# def add_source_file(msg):
#     print("Adding %s to file source (permanent? %s) for user %s"%(msg['file'], msg['permanent'], current_user.username))
#     if msg['group'] == '':
#         gr = None
#     else:
#         gr = msg['group']
#     try:
#         file_path = measure_path_from_name(msg['file'])
#         add_file_source(file_path, msg['permanent'], gr)
#         result = 1
#     except ValueError:
#         print_warning("Database error, cannot add file %s to source"%msg['file'])
#         result = 0
#     socketio.emit('explore_add_source_done',json.dumps({'file':str(msg['file']),'result':result}))
#
# @socketio.on('explore_remove_source')
# def remove_source(msg):
#     try:
#         group = msg['group']
#         print('Removing source group %s'%group)
#         remove_source_group(group)
#     except KeyError:
#         measure = msg['file']
#         print('Removing source file %s'%measure)
#         remove_file_source(measure)
#
# @socketio.on('consolidate_source_files')
# def consolidate_source_files(msg):
#     deleted_items = consolidate_sources()
#     socketio.emit('consolidate_source_files',json.dumps(deleted_items))
#
# @socketio.on('remove_temporary_source_files')
# def remove_temporary_source_files(msg):
#     clear_user_file_source()
#     socketio.emit('remove_temporary_source_files',json.dumps({}))
#
# @socketio.on('init_test_run')
# def init_test_run_handler(msg):
#     clean_tmp_folder()
#     name = ""
#     for file in msg['files']:
#         arguments = {}
#         arguments['file'] = file
#         arguments['parameters'] = msg['params']
#         name = "Fit_init_test_%s_%s"%(file,get_small_timestamp())
#         job_manager.submit_job(init_dry_run, arguments = arguments, name = name, depends = None)
#     if name != "":
#         socketio.emit('init_test_run',json.dumps({'last':name}))
#
# @socketio.on('run_analysis')
# def run_analysis(msg):
#     clear_all_selected_files({})
#     print('updating configuration variable...')
#     config = session.get('analysis_config')
#     config.update_configuration(msg['params'])
#     session['analysis_config'] = config
#     print(config.pprint())
#     print("building job queue...")
#     config.build_job_queue()
#     print("sorting job queue...")
#     config.sort_job_queue()
#     print("submitting jobs...")
#     config.enqueue_jobs()
