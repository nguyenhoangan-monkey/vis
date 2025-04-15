import subprocess
import sys
import argparse
import matplotlib.pyplot as plt
from matplotlib.pyplot import figure
import numpy as np
import csv
import re
import time
from datetime import datetime
from datetime import timedelta
import locale

# ALL DATA IS EXPECTED TO BE IN A CSV FORMAT
# DO NOT MODIFY THE FOLLOWING: 
ANNEX_UPS = 6.857 # constant for the Annex UPS load prior to February 16th
ANNEX_A03 = 0.794 # for PDU A0-3 prior to March 13th
FSA_LOAD = 0.523  
SIEMENS_LOAD = 1.524
ANNEX_NONUPS = FSA_LOAD + SIEMENS_LOAD
SCGP_LOAD = 1.248 
SAMPLE_USE = """
REQUIREMENTS: Make sure to load the anaconda/ module prior to running this script.
SAMPLE COMMAND: python vis.py -g 'Com Center Main Room' -d 20 -s 01/05/2024 -p 50 -a
    This command will generate a graph of the average power data for the Computing Center's main room from Jan 5th to 25th with 50 data points
    """
GROUPNAMES = ['PDU-A10-1', 'PDU-A10-2', 'PDU-A10-3', 'PDU-A4-1', 'PDU-A4-2', 'PDU-A5-1', 'PDU-A5-2', 'PDU-A5-3', 'PDU-A5-4', 'PDU-A5-5', 'PDU-A6-1', 'PDU-A6-2', 'PDU-A6-3', 'PDU-A7-1', 'PDU-A7-2', 'PDU-A7-3', 'PDU-A8-1', 'PDU-A8-2', 'PDU-A8-3', 'PDU-A8-4', 'PDU-B1-1', 'PDU-B1-2', 'PDU-B1-3', 'PDU-B2-1', 'PDU-B2-2', 'PDU-B3-1', 'PDU-B3-2', 'PDU-B3-3', 'PDU-B3-4', 'PDU-B4-1', 'PDU-B4-2', 'PDU-D1-1', 'PDU-D1-2', 'PDU-D1-3', 'PDU-D1-4', 'PDU-D2-1', 'PDU-D2-2', 'PDU-D2-3', 'PDU-D2-4', 'PDU-D3-1', 'PDU-D3-2', 'PDU-D3-3', 'PDU-D3-4', 'PDU-D4-1', 'PDU-D4-2', 'PDU-D4-3', 'PDU-D4-4', 'PDU-D5-1', 'PDU-D5-2', 'PDU-D5-3', 'UPS-PDU1', 'UPS-PDU2', 'SW-EPS1', 'SW-EPS2', 'SW-EPS3', 'PDU-A0-1', 'PDU-A0-2', 'PDU-A0-3', 'PDU-C4-1', 'PDU-C4-2', 'Com Center Main Room', 'Com Center A-Aisle', 'Com Center B-Aisle', 'SeaWulf Main Room on UPS', 'SeaWulf Main Room on Non-UPS', 'SeaWulf Annex on UPS', 'SeaWulf Annex on Non-UPS', 'Com Center Annex Total', 'IACS Total', 'IACS Main Panel', 'IACS RP2 Panel']

def valid_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%m/%d/%Y")
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a valid date: {s!r}")

# START OF ARG PARSING ===================================================================================================
# USAGE: -g GROUP -d DAYS -p POINTS [-s START] [-e END] [-a] [-m]
parser = argparse.ArgumentParser(description="Parses and visualizes SNMP power data.")
parser.add_argument('-g', '--group', dest='group', choices=GROUPNAMES, help="group of PDUs (e.g. ARACK, MAINROOM, IACS, etc.)")
parser.add_argument('-d', '--days', dest='numDays',  type=float, help="the number of days to look at data for, counted from the date provided with -s or backwards from today if -s is not provided")
parser.add_argument('-s', '--start', dest='startDate', type=valid_date, help="the date to start collecting data from in MM/DD/YYYY format")
parser.add_argument('-e', '--end', dest='endDate', type=valid_date, help="the date to stop collecting data from in MM/DD/YYYY format")
parser.add_argument('-p', '--points', dest='numPoints', type=int, help="number of points to plot")
parser.add_argument('-a', '--average', dest='avg', action='store_true', help="chart only average load")
parser.add_argument('-m', '--max', dest='max', action='store_true', help="chart only maximum load")
parser.add_argument('--clean', dest='plotClean', action='store_true', help="plot graph without values over every point")

if len(sys.argv) == 1: # no arguments provided, print help message
    print(SAMPLE_USE)
    parser.print_help(sys.stderr)
    sys.exit(1)
if sys.argv[1] == '-h' or sys.argv[1] == '--help':
    print(SAMPLE_USE)

args = parser.parse_args()
upsOnly = entOnly = hpcOnly = nonmetered = False
headerData = ''
if args.group == None: 
    val = int(input("""Group name not specified. Please enter a value: 
    1 for Computing Center Main Room 
    2 for Computing Center Annex
    3 for other
        : """))
    if val == 3:
        group = input(f"""Please type in one of the following options:\n{GROUPNAMES}
        : """)
        while group not in GROUPNAMES:
            group = input(f"""Invalid name. Please type in one of the following options:\n{GROUPNAMES}
        : """)
        args.group = group
    elif val == 2:
        annex = int(input("""Please enter a value: 
    1 for Computing Center Annex Total
    2 for SeaWulf Annex on UPS
    3 for SeaWulf Annex on Non-UPS
        : """))
        if annex == 1: 
            args.group = "Com Center Annex Total"
        if annex == 2:
            args.group = "SeaWulf Annex on UPS"
        if annex == 3: 
            args.group = "SeaWulf Annex on Non-UPS"
    else:  
        args.group = "Com Center Main Room"
if args.group == "Com Center Main Room":
    headerData = "Total"
    val = int(input("""Please enter a value: 
    1 for Computing Center Main Room total
    2 for Computing Center Main Room UPS logs-only
    3 for Computing Center Main Room Enterprise Aisle-only
    4 for Computing Center Main Room HPC data-only
    5 for Computing Center Main Room nonmetered equipment
        : """))
    if val == 2:
        headerData = "UPS"
        upsOnly = True
    if val == 3: 
        headerData = "ENT"
        entOnly = True
    if val == 4:
        headerData = "HPC"
        hpcOnly = True
    if val == 5:
        headerData = "Nonmetered"
        nonmetered = True
# save = input("Would you like to save this figure? [y/n] ").lower()

if args.numDays != None and args.numDays < 0.08:
        parser.error("numDays cannot be smaller than 0.08 of a day")
print("Group: {}\nStart Date: {}\nDays: {}\nAverage? {}\nMax? {}\nNumber of Points? {}".format(args.group, args.startDate, args.numDays, args.avg, args.max, args.numPoints))

if(args.startDate == None):
    endDate = datetime.now()
    startDate = endDate - timedelta(days=float(args.numDays))
else:
    startDate = args.startDate
    if args.endDate != None:
        endDate = args.endDate
    else:
        endDate = startDate + timedelta(days=float(args.numDays))
print("Start time:", startDate, "End time:", endDate)
numDays = (endDate.date() - startDate.date()).days

# END OF ARG PARSING =====================================================================================================
# START OF READING DATA ==================================================================================================
# input data. for more information see ./power_diagram.jpg
hpc_data = {} # Seawulf data. Location: in the center
ent_data = {} # Enterprise equipments power data. Location: mainroom, UPS
ups_data = {} # UPS power data

# global variables for data generated by calculations. not provided by csv.
averages = {} # average for the power data requested by the user over the certain period
maxes = {} # max of the power data requested by the user over the certain period
disclaimers = [] # problems outside of our control

def calc_annex_helper():
    # can use to generate average before March 14th, but not max
    print("\nCalculating annex data")
    command = f"""ls -lt ../*-*-*csv | awk '{{print $9}}' | sed -n '/2024-03-28/, /2024-03-17/p' | tac"""
    result = subprocess.run(command, shell=True, executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True)
    files = result.stdout.splitlines()
    print(files)

    filedata = {} # temp file for csv.DictReader()
    group = 'PDU-A0-3'
    for file in files: # reading through every file
        matches = re.split(r'^(\d{4})-(\d{2})-(\d{2})\.csv$', file)[1:4] # making sure file name matches expected format
        if matches:
            with open(file, 'r') as f:
                reader = csv.DictReader(f) # reads every row in the csv into dict
                for row in reader:
                    if not filedata: # if dictionary is empty, initiate values
                        filedata['Date'] = [int(row['Date'])]
                        filedata[group] = [float(row[group])]
                    else: 
                        filedata['Date'].append(int(row['Date']))
                        filedata[group].append(float(row[group]))
    average = round(sum(filedata[group]) / len(filedata[group]), 3)
    # maximum = round(max(filedata[group]), 3)
    return average

def parse_HPC(): 
    """Parses the files from the relevant time period generated by HPC polling. The following are modified:
        hpc_data -> {Date: [timestamps], 'args.group': [values] ...}
    HPC is a dictionary with an array for timestamps, and array(s) for the relevant polling data.
    This includes Computing Center Annex UPS and Non-UPS, if necessary. 
    """
    # bash code to filter through CSV files within time range specified
    print("\nPARSING HPC DATA... (default, must be parsed for all options)")
    command = f"""ls -lt ../*-*-*csv | awk '{{print $9}}' | sed -n '/{endDate.date()}/, /{startDate.date()}/p' | tac"""
    result = subprocess.run(command, shell=True, executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True)
    files = result.stdout.splitlines()
    print(files)

    # array to append data extracted from the CSV
    hpc_data['Date'] = []
    hpc_data[args.group] = []
    hpc_data['SeaWulf Main Room on UPS'] = []
    hpc_data['SeaWulf Main Room on Non-UPS'] = []
    hpc_data['SeaWulf Annex on UPS'] = []

    for file in files: # reading through every file
        matches = re.split(r'^../(\d{4})-(\d{2})-(\d{2})\.csv$', file)[1:4] # making sure file name matches expected format
        if matches:
            with open(file, 'r') as f:
                reader = csv.DictReader(f) # reads every row in the csv into dict
                for row in reader:
                    if (datetime.timestamp(startDate) <= int(row['Date']) and datetime.timestamp(endDate) >= int(row['Date'])): # timestamp in range
                        hpc_data['Date'].append(int(row['Date'])) # append values
                        if args.group not in row:
                            hpc_data[args.group].append(float(0))
                        if (args.group == 'Com Center Main Room'): #FOR COMPUTING CENTER MAIN ROOM CAlCUlATIONS, RECORD
                            hpc_data['SeaWulf Main Room on UPS'].append(float(row['SeaWulf Main Room on UPS']))
                            hpc_data['SeaWulf Main Room on Non-UPS'].append(float(row['SeaWulf Main Room on Non-UPS']))
                            hpc_data[args.group].append(float(row['SeaWulf Main Room on UPS']) + float(row['SeaWulf Main Room on Non-UPS']))
                            if (not hpcOnly and not upsOnly and not entOnly): # ANNEX DATA REQUIRED FOR NONMETERED CALCULATIONS
                                if (file >= '2024-02-16.csv'): # ANNEX DATA EXISTS
                                    hpc_data['SeaWulf Annex on UPS'].append(float(row['SeaWulf Annex on UPS']))
                                else:
                                    hpc_data['SeaWulf Annex on UPS'].append(float(0))
                        else: 
                            hpc_data[args.group].append(float(row[args.group]))

def parse_ENT():
    """Parses the files from the relevant time period from Enterprise logs. The following are modified:
        ent_data -> {Date: [timestamps], 'args.group': [values]}
    ent_data is a dictionary with an array for timestamps, and array for relevant data.
    """
    
    print("\nPARSING ENT DATA...")
    read = True
    # bash code to filter through ENT files
    command = f"""ls -ltr ../ENT* | awk '{{print $9}}'"""
    result = subprocess.run(command, shell=True, executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True)
    files = result.stdout.splitlines()
    print(files)
    
    with open (files[-1], 'r') as lastFile: # finding the last recorded date for ENT files
        lastEntry = lastFile.readlines()[-1]
        if(re.search(r'\d{1,2}/\d{1,2}/\d{2,4}.+EST', lastEntry) == None):
            date = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}.+EDT', lastEntry).group(0)
        else:
            date = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}.+EST', lastEntry).group(0)
        try: # for formats like 1/04/24
            last = int(time.mktime(datetime.strptime(date, "%m/%d/%y %I:%M:%S %p %Z").timetuple()))
        except: # for formats like 1/04/2024
            last = int(time.mktime(datetime.strptime(date, "%m/%d/%Y %I:%M:%S %p %Z").timetuple()))
        if last < datetime.timestamp(startDate): # if the last recorded date is before the requested time period
            read = False  # do not read ENT files
        if last < datetime.timestamp(endDate):
            disclaimers.append("Missing Enterprise aisle equipment data for the time period.")

    # array to append data extracted from the CSV, specifically the timestamp
    ent_data['Date'] = []
    ent_data[args.group] = [] # arguments parsed from the reader
    if read:
        latestTime = None # latest time in each ENT file, for checking overlaps
        for file in files:
            with open(file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    try: 
                        timestamp = int(time.mktime(datetime.strptime(row['Time'], "%m/%d/%y %I:%M:%S %p %Z").timetuple()))
                    except: 
                        timestamp = int(time.mktime(datetime.strptime(row['Time'], "%m/%d/%Y %I:%M:%S %p %Z").timetuple()))
                    if latestTime != None and latestTime > timestamp or timestamp < startDate.timestamp() or timestamp > endDate.timestamp():
                        continue
                    try: 
                        power = 208.0 * float(row['Value']) / 1000.0
                    except: 
                        power = 0
                    ent_data['Date'].append(timestamp)
                    ent_data[args.group].append(power)
                latestTime = timestamp

def parse_UPS():
    """Parses the files from the relevant time period from UPS logs. The following are modified:
        ups_data -> {Date: [timestamps], 'args.group': [values]}
    ups_data is a dictionary with an array for timestamps, and array for relevant data.
    """
    ups_data['Date'] = []
    ups_data['UPS_AVG'] = []
    # ups_data['UPS_MAX'] = []
    
    print("\nPARSING UPS DATA...")
    read = True
    # bash code to filter through UPS files
    command = f"""ls -ltr ../UPS* | awk '{{print $9}}'"""
    result = subprocess.run(command, shell=True, executable="/bin/bash",
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                universal_newlines=True)
    files = result.stdout.splitlines()
    print(files)
    
    with open (files[-1], 'r') as lastFile: # finding the last recorded date for UPS files
        lastEntry = lastFile.readlines()[-1]
        date = re.search(r'\d{1,2}/\d{1,2}/\d{2,4}', lastEntry).group(0)
        reTime = re.search(r'\d{1,2}:\d{1,2}', lastEntry).group(0)
        date += " " + reTime
        try:
            last = int(time.mktime(datetime.strptime(date, "%m/%d/%y %H:%M").timetuple()))
        except: # for formats like 1/04/2024
            last = int(time.mktime(datetime.strptime(date, "%m/%d/%Y %H:%M").timetuple()))
        if last < datetime.timestamp(startDate): # if the last recorded date is before the requested time period
            read = False  # do not read ups files
        if last < datetime.timestamp(endDate):
            disclaimers.append("Missing UPS trendlog for the time period.")

    if read:
        latestTime = None # latest time in each UPS file, for checking overlaps
        for file in files:
            with open(file, 'r') as f:
                reader = csv.DictReader(f)
                for row in reader:
                    timestring = row['Date'] + " " + row['Time']
                    try: 
                        timestamp = int(time.mktime(datetime.strptime(timestring, "%m/%d/%y %H:%M").timetuple()))
                    except: 
                        timestamp = int(time.mktime(datetime.strptime(timestring, "%m/%d/%Y %H:%M").timetuple()))
                    if latestTime != None and latestTime > timestamp or timestamp < startDate.timestamp() or timestamp > endDate.timestamp():
                        continue
                    ups_data['Date'].append(timestamp)
                    ups_data['UPS_AVG'].append(int(row['Watts Out (avg)']) / 1000.0)
                latestTime = timestamp

# CLEANING DATA + ALIGNING TIMESTAMPS ==========================================================================
# if args.group == 'Com Center Main Room':
    # assert hpc_data and ent_data and ups_data
def clean_data(dataset):
    for key in dataset: # loop to remove outliers
        if key != 'Date' and len(dataset[key]) != 0:
            std = np.std(dataset[key])
            mean = np.mean(dataset[key])
            dataset[key] = [0 if abs(val - mean) > (std) else val for val in dataset[key]]
            for i, val in enumerate(dataset[key]):
                if val == 0:
                    next = i
                    while next != (len(dataset[key]) - 1) and dataset[key][next] == 0: 
                        next += 1 # finding next valid data point
                    if i == 0: dataset[key][i] = dataset[key][next] # edge case for first point
                    elif i == len(dataset[key]) - 1: dataset[key][i] = dataset[key][i - 1] # edge case for last point
                    else: dataset[key][i] = (dataset[key][i - 1] + dataset[key][next]) / 2
    return

def align_timestamps(dataset1, dataset2):
    """ Given two dictionaries, aligns the timestamps of the shorter dictionary to the longer one
    Input: two dictionaries dataset1 and dataset2, for the timestamps you want to align
    Output: modifies in-place the timestamps and corresponding data
    """
    # if the timestamps are the same length, simply reassign
    if len(dataset2['Date']) == len(dataset1['Date']): # does NOT account for mismatching timestamps within data; approximates
        dataset1['Date'] = dataset2['Date']
        return

    if len(dataset2['Date']) - len(dataset1['Date']) < 0:
        # switch if ds1 is longer than ds2
        temp = dataset1
        dataset1 = dataset2
        dataset2 = temp
    timestamps1 = np.array(dataset1['Date'], dtype=int)
    timestamps2 = np.array(dataset2['Date'], dtype=int)

    # otherwise perform elementwise comparison of timestamps
    std_diff = np.std(timestamps2[:len(timestamps1)] - timestamps1) # determines if ds1 is earlier/later than ds2 on average
    diff_tolerance = abs(std_diff)
    print("avg diff:", std_diff)
    print("diff tol", diff_tolerance)
    # ^ positive value: ts2 is later than ts1
    # print(timestamps1)
    # print(timestamps2)

    for i, elem2 in enumerate(timestamps2): # enumerate returns tuples of (index, value)
        try: 
            elem1 = timestamps1[i]
        except:
            timestamps1.append(elem2)
            elem1 = timestamps1[i]
        if elem2 - elem1 > (std_diff + diff_tolerance): # indicates that there might've been a skip in time
            # first case: elem2 is much later than elem1, indicating a skip in ts2
            # realistically, as timestamps2 should be the longer array, the first case should not occur
            # print(elem1, ":", elem2)
            print("ERROR: skip in timestamp detected within the CSV files, cannot perform timestamp alignment between two datasets provided")
        elif elem1 - elem2 > (std_diff + diff_tolerance):
            print(elem1, ":", elem2)
            # second case: elem1 is much later than elem2, indicating a skip in ts1
            # append to shorter array, ts1 
            timestamps1 = list(np.insert(timestamps1, i, elem2))
            # update data for values
            for key in dataset1:
                if key != 'Date':
                    if i == 0:
                        dataset1[key].insert(i, dataset1[key][i + 1])
                    elif i == len(timestamps1) - 1:
                        dataset1[key].insert(i, dataset1[key][i - 1])
                    else:
                        dataset1[key].insert(i, dataset1[key][i - 1] + dataset1[key][i + 1] / 2)
            print("len 1: ", len(timestamps1), "len 2: ", len(timestamps2))
        else:
            # print("reassigning")
            timestamps1[i] = elem2
    
    # print([ts1 for ts1, ts2 in zip(timestamps1, dataset2['Date']) if ts1 != ts2][::50])
    # print(timestamps2 == dataset2['Date'])
    dataset1['Date'] = timestamps1
    # print([ts1 for ts1, ts2 in zip(dataset1['Date'], dataset2['Date']) if ts1 != ts2][::50])
    assert(len(timestamps1) == len(timestamps2)) # length check
    assert(timestamps1[int(len(timestamps1) / 2)] == timestamps2[int(len(timestamps2) / 2)]) # midpoint check
    # assert() # checking for deviation
    return

def align():
    if ups_data:
        align_timestamps(hpc_data, ups_data)

    if ent_data:
        align_timestamps(hpc_data, ent_data)

    if ups_data and hpc_data:
        assert(hpc_data['Date'] == ups_data['Date'])
    if ent_data and hpc_data:
        assert(hpc_data['Date'] == ent_data['Date'])
    print(np.average(np.diff(hpc_data['Date'])))

# CALCULATING MAX/AVERAGES =============================================
def calculate(interval):
    if not args.avg and not args.max: # if neither's specified, turn both on for default behavior
        args.avg = True
        args.max = True

    if args.group == 'Com Center Main Room': # MAIN ROOM CALCULATIONS
        for x in range(0, int(args.numPoints)): 
            if args.avg: 
                if ups_data:
                    upsAvg = round(sum(ups_data['UPS_AVG'][x*interval : (x+1)*interval]) / interval, 2)
                if ent_data:
                    entAvg = round(sum(ent_data['Com Center Main Room'][x*interval : (x+1)*interval]) / interval, 2)
                swUPSAvg = round(sum(hpc_data['SeaWulf Main Room on UPS'][x*interval : (x+1)*interval]) / interval, 2)
                swNonUPSAvg = round(sum(hpc_data['SeaWulf Main Room on Non-UPS'][x*interval : (x+1)*interval]) / interval, 2)
                if not (hpcOnly or entOnly or upsOnly):
                    swAnnexUPSAvg = round(sum(hpc_data['SeaWulf Annex on UPS'][x*interval : (x+1)*interval]) / interval, 2)

                if upsOnly: # display only UPS data
                    average = upsAvg
                elif entOnly: # display only Enterprise Equipment data
                    average = entAvg
                elif hpcOnly: # display only SeaWulf data
                    average = swUPSAvg + swNonUPSAvg
                else: # OBTAINING ANNEX DATA
                    if (hpc_data['Date'][x*interval] >= 1710302406): # if data's past March 13th
                        swAnnexUPSAvg = swAnnexUPSAvg + SCGP_LOAD
                    elif hpc_data['Date'][x*interval] >= 1708059906: # if data's past February 16th
                        swAnnexUPSAvg = swAnnexUPSAvg + SCGP_LOAD + ANNEX_A03
                    else:
                        swAnnexUPSAvg = ANNEX_UPS # relying on precomputed values, might not be accurate
                    if nonmetered: # for nonmetered equipment
                        average = upsAvg - entAvg - swUPSAvg - swAnnexUPSAvg
                    else:  # for regular main room total
                        average = swNonUPSAvg + upsAvg - swAnnexUPSAvg
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date] = round(average, 2)
            if args.max: 
                if ups_data:
                    upsMax = round(max(ups_data['UPS_AVG'][x*interval : (x+1)*interval]), 2)
                if ent_data:
                    entMax = round(max(ent_data['Com Center Main Room'][x*interval : (x+1)*interval]), 2)
                swUPSMax = round(max(hpc_data['SeaWulf Main Room on UPS'][x*interval : (x+1)*interval]), 2)
                swNonUPSMax = round(max(hpc_data['SeaWulf Main Room on Non-UPS'][x*interval : (x+1)*interval]), 2)
                if not (hpcOnly or entOnly or upsOnly):
                    swAnnexUPSMax = round(max(hpc_data['SeaWulf Annex on UPS'][x*interval : (x+1)*interval]), 2)

                if upsOnly: # display only UPS data
                    maximum = upsMax
                elif entOnly: # display only Enterprise Equipment data
                    maximum = entMax
                elif hpcOnly: # display only SeaWulf data
                    maximum = swUPSMax + swNonUPSMax
                else:
                    # OBTAINING ANNEX DATA
                    if (hpc_data['Date'][x*interval] >= 1710302406): # if data's past March 13th
                        swAnnexUPSMax = swAnnexUPSMax + SCGP_LOAD
                    elif hpc_data['Date'][x*interval] >= 1708059906: # if data's past February 16th
                        swAnnexUPSMax = swAnnexUPSMax + SCGP_LOAD + ANNEX_A03
                    else:
                        swAnnexUPSMax = ANNEX_UPS
                    if nonmetered: # for nonmetered equipment
                        maximum = upsMax - entMax - swUPSMax - swAnnexUPSMax
                    else:  # for regular main room total
                        maximum = swNonUPSMax + upsMax - swAnnexUPSMax

                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date]  = round(maximum, 2)
    elif args.group == 'Com Center Annex Total':
        for x in range(0, int(args.numPoints)): 
            if args.avg: 
                if (hpc_data['Date'][x*interval] >= 1710302406): # if data's past March 13th
                    annex_load = (sum(hpc_data[args.group][x*interval : (x+1)*interval]) / interval) + ANNEX_NONUPS + SCGP_LOAD
                elif (hpc_data['Date'][x*interval] >= 1708059906): # if data's past February 16th
                    annex_load = (sum(hpc_data[args.group][x*interval : (x+1)*interval]) / interval) + ANNEX_A03 + ANNEX_NONUPS + SCGP_LOAD
                else:
                    annex_load = ANNEX_UPS
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date] = round(annex_load, 2)
            if args.max: # for the -m flag and default behaviosr
                # print("MAX:" , max(hpc_data[args.group][x*interval : (x+1)*interval]))
                if(hpc_data['Date'][x*interval] >= 1710302406):  # if data's past March 13th
                    annex_load = max(hpc_data[args.group][x*interval : (x+1)*interval]) + SCGP_LOAD
                elif(hpc_data['Date'][x*interval] >= 1708059906):  # if data's past February 16th
                    annex_load = max(hpc_data[args.group][x*interval : (x+1)*interval]) + SCGP_LOAD + ANNEX_A03
                else: 
                    annex_load = ANNEX_UPS
                # print("MAX CALCULATED:" , annex_load)
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date]  = round(annex_load, 2)
    elif args.group == 'SeaWulf Annex on UPS':
        for x in range(0, int(args.numPoints)): 
            if args.avg: 
                if (hpc_data['Date'][x*interval] >= 1710302406): # if data's past March 13th
                    annex_load = (sum(hpc_data[args.group][x*interval : (x+1)*interval]) / interval)
                elif (hpc_data['Date'][x*interval] >= 1708059906):
                    annex_load = (sum(hpc_data[args.group][x*interval : (x+1)*interval]) / interval) + ANNEX_A03
                else:
                    annex_load = ANNEX_UPS
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date] = round(annex_load, 2)
            if args.max: # for the -m flag and default behaviosr
                if (hpc_data['Date'][x*interval] >= 1710302406): # if data's past March 13th
                    annex_load = (max(hpc_data[args.group][x*interval : (x+1)*interval]))
                elif (hpc_data['Date'][x*interval] >= 1708059906):
                    annex_load = (max(hpc_data[args.group][x*interval : (x+1)*interval])) + ANNEX_A03
                else: 
                    annex_load = ANNEX_UPS
                # print("MAX CALCULATED:" , annex_load)
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date]  = round(annex_load, 2)
    else: # for non main room
        for x in range(0, int(args.numPoints)):
            if args.avg: # for the -a flag and default behavior
                average = round(sum(hpc_data[args.group][x*interval : (x+1)*interval]) / interval, 2)
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date]  = average
            if args.max: # for the -m flag and default behavior
                maxim = round(max(hpc_data[args.group][x*interval : (x+1)*interval]), 2)
                datetime_obj = datetime.fromtimestamp(round(sum(hpc_data['Date'][x*interval : (x+1)*interval]) / interval))
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date]  = maxim

    totAvg = '--' # calculating cumulative values
    totMax = '--'
    if averages:
        totAvg = round(sum(averages.values()) / len(averages), 3)
    if maxes:
        totMax = round(max(maxes.values()), 3)
    stats = f'Cumulative Average: {totAvg} kW   Cumulative Max: {totMax} kW'
    period = f'Data from {startDate} to {endDate}'

    print("\nSETTING UP FIGURE...")
    fig, ax = plt.subplots()
    fig.set_size_inches(19.2, 14.4)

    if averages:
        dates, avgs = list(averages.keys()), list(averages.values())
        plt.plot(np.arange(len(dates)), avgs, label='average')
        if not args.plotClean:
            for i, val in enumerate(avgs):
                plt.text(i, val, str(val), fontsize=8)
        # print(dates, avgs)
    if maxes: 
        dates, maxs = list(maxes.keys()), list(maxes.values())
        plt.plot(np.arange(len(dates)), maxs, label='maximum')
        if not args.plotClean:
            for i, val in enumerate(maxs):
                plt.text(i, val, str(val), fontsize=8)
        # print(dates, maxs)

    plt.xticks(np.arange(len(dates)), dates, fontsize=9)
    plt.annotate(stats,
                xy=(0.5, 0.9), xycoords='figure fraction', ha='center')
    plt.annotate(period,
                xy=(0.5, 0.92), xycoords='figure fraction', ha='center')
    for i, disclaimer in enumerate(disclaimers): 
        plt.annotate(disclaimer,
                xy=(0.5, 0.85 - 0.01 * i), xycoords='figure fraction', ha='center', fontsize=8, color='red')

    ax.set_title(f'Power Data for {args.group} {headerData}', y=1.07)
    ax.set_xlabel('Time')
    ax.set_ylabel('Power usage (kW)')
    # ax.set_ylim(min(filedata[args.group]) - totMax * 0.05, totMax + totMax * 0.1)

    ticks = ax.xaxis.get_ticklabels();

    if(numDays < 5 and int(args.numPoints) < 26): #labels 13 ticks
        for label in ax.xaxis.get_ticklabels()[1::2]:
            label.set_visible(False)

    elif(numDays < 5):
        interval = int(args.numPoints)//12 + (int(args.numPoints) % 12 > 0)
        for i in range(0,len(ticks)):
            if(i%interval != 0):
                ticks[i].set_visible(False)

    else: #only labels different days if plotting more than 5 days
        ticks[0].set_text(ticks[0].get_text()[0:5])
        if(numDays > 21):
            interval = (numDays // 12) + (numDays % 12 > 0)
        else:
            interval = 1
        x = 1
        for i in range(1,len(ticks)):
            if(ticks[i].get_text()[0:5] == ticks[i-1].get_text()[0:5]):
                ticks[i].set_visible(False)
            else:
                if(x % interval != 0):
                    ticks[i].set_visible(False)
                else: 
                    ticks[i].set_text(ticks[i].get_text()[0:5])
                x = x+1

    plt.xticks(np.arange(len(dates)), ticks)

    plt.legend()
    # plt.show()
    plt.savefig('out.png')

def main():
    locale.setlocale(locale.LC_ALL, 'en_US')

    parse_HPC()
    print("HPC DATA PARSED:", list(hpc_data.keys()))
    if (len(hpc_data[args.group]) < int(args.numPoints)):
        print("Cannot have more points than there are data")
        exit()
    interval = int(len(hpc_data[args.group]) / int(args.numPoints)) # determines data point per entry
    print("HPC LENGTH:", len(hpc_data[args.group]))

    if args.group == 'Com Center Main Room' and not hpcOnly and not upsOnly: # INCLUDE ENTERPRISE EQUIPMENT DATA
        parse_ENT()
        for key in ent_data:
            print(key, ent_data[key][:1])
        print("ENT LENGTH:", len(ent_data[args.group]))

    if args.group == 'Com Center Main Room' and not hpcOnly and not entOnly: 
        parse_UPS()
        for key in ups_data:
            print(key, ups_data[key][:1])
        print("UPS LENGTH:", len(ups_data['UPS_AVG']))

    clean_data(hpc_data)
    if ups_data: clean_data(ups_data)
    if ent_data: clean_data(ent_data)

    align()
    calculate(interval)
    return

main()