import time,os,glob
import numpy as np
import matplotlib.pyplot as plt
import uhd
from cycler import cycler
from scipy.signal import decimate, welch, blackmanharris, resample
from scipy.fft import fft
from multiprocessing import Process
from joblib import Parallel, delayed
import multiprocessing

shared_dict_lock = multiprocessing.Lock()
os.environ["UHD_IMAGES_DIR"] = "/usr/local/share/uhd/images"
manager = multiprocessing.Manager()
shared_dict = manager.dict()
shared_dict['progress'] = 'Nothing happening'
# measurement queue
def measurement_manager():
    '''
    Function defining a thread that decide whar measurement to do and put stuff in the measurement queue.
    '''

def acquisition_thread():
    '''
    Function defining the acquisition thread. check the measurement queue and execute.
    '''

def gather_main_files():
    '''
    Returns a list of files containing the main spectrum.
    '''
def gather_followup():
    '''
    Returns a list of follow ups.
    '''

def generate_central_freqs(start=10e6,end=5.95e9,clipping = 0.1,master_clock_rate= 52e6):
    '''
    Generate an array of central frequencies.
    Arguments:
        - master_clock_rate: daq rate for the board.
        - clipping: fp between 0 and 1. represent half-band cut.
        - start: in hz
        - end: in hz
    '''
    if start>end:
        start,end = end,start
        inv_flag = True
    else:
        inv_flag = False
    base_freq = max(10e6,start) # 10MHz for B200
    freq = base_freq + (1.-clipping)*master_clock_rate/2.
    ret = []
    while freq<end:
        ret.append(freq)
        freq+=(1.-clipping*2.)*master_clock_rate
    if inv_flag:
        ret = reverse(ret)
    return ret

def get_header(filename,data_folder=None):
    '''
    get gain and central freqs.
    '''
    if data_folder is not None:
        os.chdir(data_folder)
    infile = open(filename, 'r')
    firstLine = infile.readline()
    gain = int(firstLine.split(";")[0].split(":")[1])
    freqs = [float(f) for f in firstLine.split(";")[1].split(":")[1][1:-2].split(", ")]
    reso = int(float(firstLine.split(";")[2].split(":")[1]))
    infile.close()
    if data_folder is not None:
        os.chdir('..')
    return gain, freqs, reso

def find_nearest(array, value):
    '''
    Should be a method of numpy arrays at this point.
    '''
    array = np.asarray(array)
    idx = (np.abs(array - value)).argmin()
    return array[idx]

def find_nearest_index(array, value):
    '''
    Should be a method of numpy arrays at this point.
    '''
    array = np.asarray(array)
    return (np.abs(array - value)).argmin()

def calculate_spec(samps,iterations,num_samps,clip,rate,central_freq,shared_dict):
    '''
    Spectrum calculation helper
    '''
    n_worker_fft = 6
    samps = samps.reshape((iterations,num_samps))[1:] # skip the first
    s = np.fft.fftshift(fft(samps*blackmanharris(num_samps),workers = n_worker_fft))
    spectrum = np.abs(np.mean(s, axis = 0)[int(num_samps*clip):-int(num_samps*clip)])
    freqv=np.fft.fftshift(np.fft.fftfreq(num_samps,d=1./rate))[int(num_samps*clip):-int(num_samps*clip)]+central_freq
    LO_index = find_nearest_index(freqv,central_freq)
    suppress_LO = 10
    for i in range(suppress_LO):
        spectrum[LO_index+i] = np.mean([spectrum[LO_index+suppress_LO+1],spectrum[LO_index-suppress_LO-1]])
        spectrum[LO_index-i] = np.mean([spectrum[LO_index+suppress_LO+1],spectrum[LO_index-suppress_LO-1]])
    spectrum = 20.0*np.log10(spectrum)
    freqv = freqv/1e6
    with shared_dict_lock:
        shared_dict['power'] = spectrum
        shared_dict['freq'] = freqv
    return

def make_spec_file(shared_dict, usrp, master_clock_rate = 52e6, start = 30e6, end = 5.95e9, gain = 50, resolution = 100000, iterations = 2000, write_dir = "data"):
    '''
    Acquire data from the B200, fft them and dump to disk.
    Arguments:
        - shared_dict: multithreading shared object
        - usrp: usrp object.
        - master_clock_rate: master clock rate used to initialize the board in Hz.
        - start: start of the scan in Hz
        - end: end of the scan in Hz
        - gain: rx gain in dB.
        - resolution: resolution in Hz
        - iterations: how many spectrum to process, see next arguments
     Return filename.
    '''
    try:
        os.chdir(write_dir)
    except OSError:
        os.mkdir(write_dir)
        os.chdir(write_dir)
    filename = 'Khound_%d.txt' % int(time.time())
    rate = int(master_clock_rate)
    channels = [int(0)]
    gain = int(gain)
    init_args = "master_clock_rate=%.3f, type=b200" % master_clock_rate
    usrp = uhd.usrp.MultiUSRP(init_args)
    num_samps = int(rate/float(resolution))
    print("Resolution: %.3fHz"%(resolution))
    complete_spec = []
    complete_freq = []
    clip = 0.1
    iterations = int(np.abs(iterations+1)) # one is wasted by capacitors
    span_freq = generate_central_freqs(start=start,end=end,clipping = clip,master_clock_rate= master_clock_rate)
    progress = 1.
    for central_freq in span_freq:
        with shared_dict_lock:
            shared_dict['progress'] = 'percent: %.1f\tScanning freq %.1fMHz '% (progress/len(span_freq), central_freq/1e6)
        if central_freq!= span_freq[0]:
            if analysis_thread.is_alive():
                print("waiting analysis...", end='')
            while analysis_thread.is_alive():
                with shared_dict_lock:
                    shared_dict['progress'] = 'percent: %.1f\tWaiting for analysis %.1fMHz '% (progress/len(span_freq), central_freq/1e6)
                print(".", end='')
                time.sleep(0.1)
            print("")
            with shared_dict_lock:
                complete_spec.append(np.array(shared_dict['power']))
                complete_freq.append(np.array(shared_dict['freq']))

        print("Acquiring data at %.2f MHz" % (central_freq/1e6))
        err = True
        while err:
            samps = usrp.recv_num_samps(num_samps*iterations, central_freq, rate, channels, gain)[0]
            if len(samps) == num_samps*iterations:
                err = False
            else:
                print("DAQ Error on %s, re-acquiring..." % filename)
        analysis_thread = multiprocessing.Process(target=calculate_spec, args=(np.array(samps)*1.,iterations,num_samps,clip,rate,central_freq*1.,shared_dict))
        analysis_thread.start()

        if central_freq== span_freq[-1]:
            if analysis_thread.is_alive():
                print("waiting analysis...", end='')
            while analysis_thread.is_alive():
                with shared_dict_lock:
                    shared_dict['progress'] = 'percent: %.1f\tWaiting for analysis %.1fMHz '% (progress/len(span_freq), central_freq/1e6)
                print(".", end='')
                time.sleep(0.1)
            print("")
            with shared_dict_lock:
                complete_spec.append(np.array(shared_dict['power']))
                complete_freq.append(np.array(shared_dict['freq']))

        progress+=1

    analysis_thread.join()
    complete_spec = np.concatenate(complete_spec)
    complete_freq = np.concatenate(complete_freq)

    with shared_dict_lock:
        shared_dict['progress'] = 'Spectral scan complete, writing %s on disk' % filename

    print("Writing %s on disk..." % filename)
    # print(np.c_[complete_freq,complete_spec].shape)
    np.savetxt(filename, np.c_[complete_freq,complete_spec], header = "gain:%d;central_freqs:%s;resolution:%f" % (gain,str(span_freq),resolution))
    print("Spectrum saved")
    with shared_dict_lock:
        shared_dict['progress'] = 'Operations complete. %s is on disk.' % filename
    return filename

def make_followup_scan(shared_dict, usrp, master_clock_rate = 52e6, duration=1, gain = 50, resolution = 100, decimation = 10):
    '''
    Similar to make spec but saves a waterfall spec to file on a single tuning.
    '''


def filename2time(filename):
    '''
    Convert a filename string into a time string. works for lists.
    '''
    if isinstance(filename, str):
        return time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(os.path.splitext(os.path.basename(filename))[0].split('_')[1])))
    elif isinstance(filename, list):
        return [time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(int(os.path.splitext(os.path.basename(f))[0].split('_')[1]))) for f in filename]
    else:
        raise ValueError('Input must be string or list')

def load_single_file(filename):
    '''
    Load data from a single file.
    '''
    print("Loading file %s..." % filename)
    freq,power = np.loadtxt(filename, unpack = True, skiprows = 1)
    return freq,power#,std

def multi_load(suffix, file_list = None, start = 0, end = np.inf):
    '''
    TO DO
    Loads data from different files and return a waterfall plot array and a list of timestamps.
    '''
    if file_list is None:
        file_list = glob.glob("%s*.txt" % suffix)
    res = Parallel(n_jobs=8, backend='multiprocessing')(delayed(load_single_file)(f) for f in file_list)
    freq_axis = []
    power_axis = []
    # std_axis = []
    for single_spec in res:
        freq_axis.append(single_spec[0])
        power_axis.append(single_spec[1])
        # std_axis.append(single_spec[2])
    return freq_axis,power_axis#,std_axis


def subtract_background(spec, spacing = 100):
    '''
    does not sound right
    '''
    back_partial = resample(spec, spacing, t=None, axis=0, window=None)
    back_full =  resample(back_partial, len(spec), t=None, axis=0, window=None) -1.
    return back_full,spec - back_full

def plot_files(shared_dict, file_list, backend = 'matplotlib', auto_show = False, data_folder = 'data', plot_folder = 'plot'):
    '''
    Plot a bunch of files in a waterfall plot. Sort the input alphabetically.
    '''

    if len(file_list)==0:
        raise ValueError("Empty file list passed to plotting function")

    waterfall = []
    # waterfall_std = []
    waterfall_back = []
    print("Loading all available files...")
    ii = 0
    s = 200
    os.chdir(data_folder)
    file_list = sorted(file_list)
    freq,powers = multi_load(suffix = None, file_list = file_list, start = 0, end = np.inf)
    filename  = "KHound_plot_"+(file_list[-1].split('_')[1]).split('.')[0]+".png"
    os.chdir("..")
    additional_clip = 1
    freq = freq[0][additional_clip:-additional_clip]
    for power in powers:
        #print("(%d/%d) %s"%(ii,len(file_list),f))
        #freq,power = np.loadtxt(f, unpack = True, skiprows = 1) #std
        # back,std = subtract_background(std, spacing = s)
        back,power = subtract_background(power, spacing = s)
        # plt.plot(freq,back[additional_clip:-additional_clip])
        # plt.plot(freq)
        # plt.show()
        # exit()
        waterfall_back.append(back[additional_clip:-additional_clip])
        waterfall.append(power[additional_clip:-additional_clip])
        # waterfall_std.append(std)
        ii+=1
    average = np.mean(waterfall,axis = 0)
    # average_std = np.mean(waterfall_std,axis = 0)
    # average_std = average_std/np.max(average_std)
    average_back = np.mean(waterfall_back,axis = 0)
    gain, central_freqs, resolution = get_header(file_list[0], data_folder = data_folder)
    if backend == 'matplotlib':
        plt.rcParams.update({'font.size': 6})
        print("Plotting using matplotlib backend...")
        cmap=plt.cm.jet
        c = cycler('color', cmap(np.linspace(0,1,len(waterfall))) )
        plt.rcParams["axes.prop_cycle"] = c
        fig = plt.figure(figsize=(6,6), dpi=200)
        ax1 = fig.add_subplot(211)
        ax2 = fig.add_subplot(212)
        min_labels = int(max([1,np.floor(len(file_list)/5.)]))
        y_ax = filename2time(sorted(file_list))[::min_labels]
        ax1.imshow(waterfall, aspect='auto', interpolation='none', extent = [min(freq),max(freq),0,len(y_ax)])
        ax1.set_yticks(range(len(y_ax)))
        ax1.set_yticklabels(y_ax)
        ax2.scatter(np.array(central_freqs)/1e6,average[[list(freq).index(min(list(freq), key=lambda x:abs(x-cf/1e6))) for cf in central_freqs]] ,color='r', marker='x',s=2, label = 'LO freqs', zorder=3)
        for pp in waterfall:
            ax2.plot(freq,pp,alpha = 1./len(waterfall),linewidth=0.2, zorder=0)
        ax2.plot(freq,average,color='k',linewidth=0.2, zorder=1, label = 'average-bg')


        if True:
            ax3=ax2.twinx()
            ax3.plot(freq,average_back,color='b',linewidth=0.2, zorder=1, label = 'background')
            # for pp in waterfall_back:
            #     ax3.plot(freq,pp,alpha = 1./len(average_back),linewidth=0.2, zorder=0)
            ax3.set_ylabel("Baseline, resampling %d" % s,color="blue")
            ax3.tick_params(axis='y', labelcolor='b')
            ax3.spines["right"].set_edgecolor('b')

        ax2.legend()
        ax2.set_xlim([min(freq),max(freq)])
        ax2.set_ylim([np.min(waterfall),np.max(waterfall)])
        ax1.set_title('Waterfall plot')
        ax2.set_title('Average')
        ax2.set_xlabel('Frequency [MHz]')
        ax1.set_ylabel('DAQ #')
        ax2.set_ylabel('Power [10*log10(fft)**2]')
        plt.suptitle('Khound data acquisition test. Resolution %.1fkHz' % (resolution/1e3))
        # plt.tight_layout()
        with shared_dict_lock:
            shared_dict['progress'] = 'Plotting complete. %s is on disk.' % filename
        try:
            os.chdir(plot_folder)
        except OSError:
            os.mkdir(plot_folder)
            os.chdir(plot_folder)
        fig.savefig(filename)
        os.chdir('..')
        # plt.plot(complete_freq,complete_spec)
        if auto_show:
            plt.show()
    elif backend == 'plotly':
        print("plotting using plotly backend...")
    else:
        raise ValueError("Plotting backend not recognized. Only matplotlib and plotly allowed.")
    print("Plotting done.")
    return filename

if __name__ == "__main__":
    print("Starting KHound...")
    master_clock_rate = 52e6
    init_args = "master_clock_rate=%.3f, type=b200" % master_clock_rate
    # usrp = uhd.usrp.MultiUSRP(init_args)
    # for i in range(100):
    #     make_spec_file(shared_dict, usrp, master_clock_rate = master_clock_rate,start = 10e6,end = 6e9, gain = 30, resolution = 10000, iterations = 200)
    os.chdir('data')
    file_list = glob.glob("Khound_*.txt")
    os.chdir('..')
    plot_files(shared_dict, file_list, backend = 'matplotlib', auto_show = True)
    # multi_load("Khound_", start = 0, end = np.inf)


    print("Done!")
