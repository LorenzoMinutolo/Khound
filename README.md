GPU SDR WEB-GUI
===============

SignalHound for the ShortK0/ShortKeck lab

How to
------
pip install -r requirements.txt
sh initialize.sh
python add_user.py -u <username>
change GLOBAL_MEASURES_PATH, PLOT_DIR, MAIN_DIR in app.py according to your system configuration
change SECRET_KEY in app.py randomly
change acquisition parameters at line 189 of handlers/explore_handlers.py
change the init arg "type" at line 138 of Khound.py
change the rate at line 135 of Khound.py
