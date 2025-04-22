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
ANNEX_UPS = 6.857  # constant for the Annex UPS load prior to February 16th
ANNEX_A03 = 0.794  # for PDU A0-3 prior to March 13th
FSA_LOAD = 0.523
SIEMENS_LOAD = 1.524
ANNEX_NONUPS = FSA_LOAD + SIEMENS_LOAD
SCGP_LOAD = 1.248
SAMPLE_USE = """
REQUIREMENTS: Make sure to load the anaconda/ module prior to running this script.
SAMPLE COMMAND: python vis.py -g 'Com Center Main Room' -d 20 -s 01/05/2024 -p 50 -a
    This command will generate a graph of the average power data for the Computing Center's main room from Jan 5th to 25th with 50 data points
    """

GROUPNAMES = (
    ["PDU-A10-1", "PDU-A10-2", "PDU-A10-3"]
    + ["PDU-A4-1", "PDU-A4-2"]
    + ["PDU-A5-1", "PDU-A5-2", "PDU-A5-3", "PDU-A5-4", "PDU-A5-5"]
    + ["PDU-A6-1", "PDU-A6-2", "PDU-A6-3"]
    + ["PDU-A7-1", "PDU-A7-2", "PDU-A7-3"]
    + ["PDU-A8-1", "PDU-A8-2", "PDU-A8-3", "PDU-A8-4"]
    + ["PDU-B1-1", "PDU-B1-2", "PDU-B1-3"]
    + ["PDU-B2-1", "PDU-B2-2"]
    + ["PDU-B3-1", "PDU-B3-2", "PDU-B3-3", "PDU-B3-4"]
    + ["PDU-B4-1", "PDU-B4-2"]
    + ["PDU-D1-1", "PDU-D1-2", "PDU-D1-3", "PDU-D1-4"]
    + ["PDU-D2-1", "PDU-D2-2", "PDU-D2-3", "PDU-D2-4"]
    + ["PDU-D3-1", "PDU-D3-2", "PDU-D3-3", "PDU-D3-4"]
    + ["PDU-D4-1", "PDU-D4-2", "PDU-D4-3", "PDU-D4-4"]
    + ["PDU-D5-1", "PDU-D5-2", "PDU-D5-3"]
    + ["UPS-PDU1", "UPS-PDU2"]
    + ["SW-EPS1", "SW-EPS2", "SW-EPS3"]
    + ["PDU-A0-1", "PDU-A0-2", "PDU-A0-3"]
    + ["PDU-C4-1", "PDU-C4-2"]
    + ["Com Center Main Room", "Com Center A-Aisle", "Com Center B-Aisle"]
    + ["SeaWulf Main Room on UPS", "SeaWulf Main Room on Non-UPS"]
    + ["SeaWulf Annex on UPS", "SeaWulf Annex on Non-UPS"]
    + ["Com Center Annex Total"]
    + ["IACS Total", "IACS Main Panel", "IACS RP2 Panel"]
)


def valid_date(s: str) -> datetime:
    try:
        return datetime.strptime(s, "%m/%d/%Y")
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a valid date: {s!r}")


# START OF ARG PARSING ===================================================================================================
# USAGE: -g GROUP -d DAYS -p POINTS [-s START] [-e END] [-a] [-m]
parser = argparse.ArgumentParser(description="Parses and visualizes SNMP power data.")
parser.add_argument(
    "-g",
    "--group",
    dest="group",
    choices=GROUPNAMES,
    help="group of PDUs (e.g. ARACK, MAINROOM, IACS, etc.)",
)
parser.add_argument(
    "-d",
    "--days",
    dest="numDays",
    type=float,
    help="the number of days to look at data for, counted from the date provided with -s or backwards from today if -s is not provided",
)
parser.add_argument(
    "-s",
    "--start",
    dest="startDate",
    type=valid_date,
    help="the date to start collecting data from in MM/DD/YYYY format",
)
parser.add_argument(
    "-e",
    "--end",
    dest="endDate",
    type=valid_date,
    help="the date to stop collecting data from in MM/DD/YYYY format",
)
parser.add_argument(
    "-p", "--points", dest="numPoints", type=int, help="number of points to plot"
)
parser.add_argument(
    "-a", "--average", dest="avg", action="store_true", help="chart only average load"
)
parser.add_argument(
    "-m", "--max", dest="max", action="store_true", help="chart only maximum load"
)
parser.add_argument(
    "--clean",
    dest="plotClean",
    action="store_true",
    help="plot graph without values over every point",
)

if len(sys.argv) == 1:  # no arguments provided, print help message
    print(SAMPLE_USE)
    parser.print_help(sys.stderr)
    sys.exit(1)
if sys.argv[1] == "-h" or sys.argv[1] == "--help":
    print(SAMPLE_USE)

args = parser.parse_args()
upsOnly = entOnly = hpcOnly = nonmetered = False
headerData = ""
if args.group is None:
    group_prompt = (
        "Group name not specified. Please enter a value:\n"
        "    1 for Computing Center Main Room\n"
        "    2 for Computing Center Annex\n"
        "    3 for other\n: "
    )
    val = int(input(group_prompt))

    if val == 3:
        group_options_prompt = (
            f"Please type in one of the following options:\n{GROUPNAMES}\n: "
        )
        group = input(group_options_prompt)

        while group not in GROUPNAMES:
            invalid_group_prompt = f"Invalid name. Please type in one of the following options:\n{GROUPNAMES}\n: "
            group = input(invalid_group_prompt)

        args.group = group

    elif val == 2:
        annex_prompt = """
        Options
            1 for Computing Center Annex Total
            2 for SeaWulf Annex on UPS
            3 for SeaWulf Annex on Non-UPS
        Please enter a value: """

        annex = int(input(annex_prompt))

        if annex == 1:
            args.group = "Com Center Annex Total"
        elif annex == 2:
            args.group = "SeaWulf Annex on UPS"
        elif annex == 3:
            args.group = "SeaWulf Annex on Non-UPS"

    else:
        args.group = "Com Center Main Room"

if args.group == "Com Center Main Room":
    headerData = "Total"

    main_room_prompt = """
    Options
        1 for Computing Center Main Room total
        2 for Computing Center Main Room UPS logs-only
        3 for Computing Center Main Room Enterprise Aisle-only
        4 for Computing Center Main Room HPC data-only
        5 for Computing Center Main Room nonmetered equipment
    Please enter a value: """
    val = int(input(main_room_prompt))

    if val == 2:
        headerData = "UPS"
        upsOnly = True
    elif val == 3:
        headerData = "ENT"
        entOnly = True
    elif val == 4:
        headerData = "HPC"
        hpcOnly = True
    elif val == 5:
        headerData = "Nonmetered"
        nonmetered = True

# save = input("Would you like to save this figure? [y/n] ").lower()

if args.numDays != None and args.numDays < 0.08:
    parser.error("numDays cannot be smaller than 0.08 of a day")
print(
    f"""
    Group: {args.group}
    Start Date: {args.startDate}
    Days: {args.numDays}
    Average? {args.avg}
    Max? {args.max}
    Number of Points: {args.numPoints}
"""
)

if args.startDate == None:
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
hpc_data = {}  # Seawulf data. Location: in the center
ent_data = {}  # Enterprise equipments power data. Location: mainroom, UPS
ups_data = {}  # UPS power data

# global variables for data generated by calculations. not provided by csv.
averages = {}  # average for the power data requested by the user
maxes = {}  # max of the power data requested by the user over the certain period
disclaimers = []  # problems outside of our control


def calc_annex_helper():  # might not actually be used?
    # can use to generate average before March 14th, but not max
    print("\nCalculating annex data")
    command = f"""ls -lt ../*-*-*csv | awk '{{print $9}}' | sed -n '/2024-03-28/, /2024-03-17/p' | tac"""
    result = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    files = result.stdout.splitlines()
    print(files)

    filedata = {}  # temp file for csv.DictReader()
    group = "PDU-A0-3"

    FILENAME_REGEX_YMD = r"^(\d{4})-(\d{2})-(\d{2})\.csv$"
    for file in files:  # reading through every file
        # making sure file name matches expected format
        matches = re.split(FILENAME_REGEX_YMD, file)[1:4]
        if matches:
            with open(file, "r") as f:
                reader = csv.DictReader(f)  # reads every row in the csv into dict
                for row in reader:
                    if not filedata:  # if dictionary is empty, initiate values
                        filedata["Date"] = [int(row["Date"])]
                        filedata[group] = [float(row[group])]
                    else:
                        filedata["Date"].append(int(row["Date"]))
                        filedata[group].append(float(row[group]))

    average = round(sum(filedata[group]) / len(filedata[group]), 3)
    # maximum = round(max(filedata[group]), 3)
    return average

# Parses the files from the relevant time period generated by HPC polling. The following are modified:
#     hpc_data -> {Date: [timestamps], 'args.group': [values] ...}
# HPC is a dictionary with an array for timestamps, and array(s) for the relevant polling data.
# This includes Computing Center Annex UPS and Non-UPS, if necessary.
# DATA HAS DAYLIGHT SAVING TIME SHIFT
def parse_HPC():
    # bash code to filter through CSV files within time range specified
    print("\nPARSING HPC DATA... (default, must be parsed for all options)")
    command = f"""ls -lt ../*-*-*csv | awk '{{print $9}}' | sed -n '/{endDate.date()}/, /{startDate.date()}/p' | tac"""
    result = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    files = result.stdout.splitlines()
    print(files)

    # array to append data extracted from the CSV
    hpc_data["Date"] = []
    hpc_data[args.group] = []
    hpc_data["SeaWulf Main Room on UPS"] = []
    hpc_data["SeaWulf Main Room on Non-UPS"] = []
    hpc_data["SeaWulf Annex on UPS"] = []

    FILENAME_REGEX_REL_YMD = r"^../(\d{4})-(\d{2})-(\d{2})\.csv$"
    for file in files:  # reading through every file
        match = re.split(FILENAME_REGEX_REL_YMD, file)[1:4]
        if not match:
            continue  # making sure file name matches expected format

        with open(file, "r") as f:
            reader = csv.DictReader(f)  # reads every row in the csv into dict
            for row in reader:
                start_in_range = datetime.timestamp(startDate) <= int(row["Date"])
                end_in_range = datetime.timestamp(endDate) >= int(row["Date"])
                if not start_in_range or not end_in_range:
                    continue

                hpc_data["Date"].append(int(row["Date"]))  # append values
                if args.group not in row:
                    hpc_data[args.group].append(float(0))

                # FOR COMPUTING CENTER MAIN ROOM CAlCUlATIONS, RECORD
                if args.group == "Com Center Main Room":
                    HEADER_STR = "SeaWulf Main Room on UPS"
                    hpc_data[HEADER_STR].append(float(row[HEADER_STR]))
                    HEADER_STR = "SeaWulf Main Room on Non-UPS"
                    hpc_data[HEADER_STR].append(float(row[HEADER_STR]))

                    hpc_data[args.group].append(
                        float(row["SeaWulf Main Room on UPS"])
                        + float(row["SeaWulf Main Room on Non-UPS"])
                    )

                    # ANNEX DATA REQUIRED FOR NONMETERED CALCULATIONS
                    annex_needed = not hpcOnly and not upsOnly and not entOnly
                    if annex_needed:
                        HEADER_STR = "SeaWulf Annex on UPS"
                        if file >= "2024-02-16.csv":  # ANNEX DATA EXISTS
                            hpc_data[HEADER_STR].append(float(row[HEADER_STR]))
                        else:
                            hpc_data[HEADER_STR].append(float(0))
                else:
                    hpc_data[args.group].append(float(row[args.group]))

# Parses the files from the relevant time period from Enterprise logs. The following are modified:
#     ent_data -> {Date: [timestamps], 'args.group': [values]}
# ent_data is a dictionary with an array for timestamps, and array for relevant data.
# DATA HAS DAYLIGHT SAVING TIME SHIFT
def parse_ENT():
    print("\nPARSING ENT DATA...")
    read = True
    # bash code to filter through ENT files
    command = f"""ls -ltr ../ENT* | awk '{{print $9}}'"""
    result = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    files = result.stdout.splitlines()
    print(files)

    DATE_REGEX_EST = r"\d{1,2}/\d{1,2}/\d{2,4}.+EST"
    DATE_REGEX_EDT = r"\d{1,2}/\d{1,2}/\d{2,4}.+EDT"
    DT_FORMAT_AMPM_SHORT = "%m/%d/%y %I:%M:%S %p %Z"
    DT_FORMAT_AMPM_LONG = "%m/%d/%Y %I:%M:%S %p %Z"

    with open(
        files[-1], "r"
    ) as lastFile:  # finding the last recorded date for ENT files
        lastEntry = lastFile.readlines()[-1]
        if re.search(DATE_REGEX_EST, lastEntry) == None:
            date = re.search(DATE_REGEX_EDT, lastEntry).group(0)
        else:
            date = re.search(DATE_REGEX_EST, lastEntry).group(0)
        try:  # parsing timestamp from string for for formats like 1/04/24
            last = int(
                time.mktime(datetime.strptime(date, DT_FORMAT_AMPM_SHORT).timetuple())
            )
        except: # parsing timestamp for formats like 1/04/2024
            last = int(
                time.mktime(datetime.strptime(date, DT_FORMAT_AMPM_LONG).timetuple())
            )
        if last < datetime.timestamp(
            startDate
        ):  # if the last recorded date is before the requested time period
            read = False  # do not read ENT files
        if last < datetime.timestamp(endDate):
            disclaimers.append(
                "Missing Enterprise aisle equipment data for the time period."
            )

    # array to append data extracted from the CSV, specifically the timestamp
    ent_data["Date"] = []
    ent_data[args.group] = []  # arguments parsed from the reader
    if not read:
        return

    latestTime = None  # latest time in each ENT file, for checking overlaps
    for file in files:
        with open(file, "r") as f:
            reader = csv.DictReader(f)
            for row in reader:
                try:
                    dt = datetime.strptime(row["Time"], DT_FORMAT_AMPM_SHORT)
                except Exception:
                    dt = datetime.strptime(row["Time"], DT_FORMAT_AMPM_LONG)
                timestamp = int(time.mktime(dt.timetuple()))

                if (
                    latestTime != None
                    and latestTime > timestamp
                    or timestamp < startDate.timestamp()
                    or timestamp > endDate.timestamp()
                ):
                    continue
                try:
                    VOLTAGE_ENT = 208.0
                    # convert amps to watts
                    power = VOLTAGE_ENT * float(row["Value"]) / 1000.0
                except:
                    power = 0

                ent_data["Date"].append(timestamp)
                ent_data[args.group].append(power)
            latestTime = timestamp

# Parses the files from the relevant time period from UPS logs. The following are modified:
#     ups_data -> {Date: [timestamps], 'args.group': [values]}
# ups_data is a dictionary with an array for timestamps, and array for relevant data.
# DATA DOES DAYLIGHT SAVING TIME SHIFT however firat does fix it in some of its data
def parse_UPS():
    ups_data["Date"] = []
    ups_data["UPS_AVG"] = []
    # ups_data['UPS_MAX'] = []

    print("\nPARSING UPS DATA...")
    read = True
    # bash code to filter through UPS files
    command = f"""ls -ltr ../UPS* | awk '{{print $9}}'"""
    result = subprocess.run(
        command,
        shell=True,
        executable="/bin/bash",
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        universal_newlines=True,
    )
    files = result.stdout.splitlines()
    print(files)

    with open(
        files[-1], "r"
    ) as lastFile:  # finding the last recorded date for UPS files
        lastEntry = lastFile.readlines()[-1]
        date = re.search(r"\d{1,2}/\d{1,2}/\d{2,4}", lastEntry).group(0)
        reTime = re.search(r"\d{1,2}:\d{1,2}", lastEntry).group(0)
        date += " " + reTime
        try: # parsing timestamp from string with date, either as 01/04/24 or 01/04/2024
            last = int(
                time.mktime(datetime.strptime(date, "%m/%d/%y %H:%M").timetuple())
            )
        except:
            last = int(
                time.mktime(datetime.strptime(date, "%m/%d/%Y %H:%M").timetuple())
            )
        if last < datetime.timestamp(
            startDate
        ):  # if the last recorded date is before the requested time period
            read = False  # do not read ups files
        if last < datetime.timestamp(endDate):
            disclaimers.append("Missing UPS trendlog for the time period.")

    if read:
        latestTime = None  # latest time in each UPS file, for checking overlaps
        for file in files:
            with open(file, "r") as f:
                reader = csv.DictReader(f)
                for row in reader:
                    timestring = row["Date"] + " " + row["Time"]
                    try:
                        timestamp = int(
                            time.mktime(
                                datetime.strptime(
                                    timestring, "%m/%d/%y %H:%M"
                                ).timetuple()
                            )
                        )
                    except:
                        timestamp = int(
                            time.mktime(
                                datetime.strptime(
                                    timestring, "%m/%d/%Y %H:%M"
                                ).timetuple()
                            )
                        )
                    if (
                        latestTime != None
                        and latestTime > timestamp
                        or timestamp < startDate.timestamp()
                        or timestamp > endDate.timestamp()
                    ):
                        continue
                    ups_data["Date"].append(timestamp)
                    ups_data["UPS_AVG"].append(int(row["Watts Out (avg)"]) / 1000.0)
                latestTime = timestamp


# CLEANING DATA + ALIGNING TIMESTAMPS ==========================================================================
# if args.group == 'Com Center Main Room':
# assert hpc_data and ent_data and ups_data
def clean_data(dataset):
    for key in dataset:  # loop to remove outliers
        if key == "Date" or len(dataset[key]) == 0:
            continue

        std = np.std(dataset[key])
        mean = np.mean(dataset[key])
        dataset[key] = [0 if abs(val - mean) > (std) else val for val in dataset[key]]
        for i, val in enumerate(dataset[key]):
            if val != 0:
                continue

            next = i
            while next != (len(dataset[key]) - 1) and dataset[key][next] == 0:
                next += 1  # finding next valid data point
            if i == 0:
                dataset[key][i] = dataset[key][next]  # edge case for first point
            elif i == len(dataset[key]) - 1:
                dataset[key][i] = dataset[key][i - 1]  # edge case for last point
            else:
                dataset[key][i] = (dataset[key][i - 1] + dataset[key][next]) / 2
    return


def align_timestamps(dataset1, dataset2):
    """Given two dictionaries, aligns the timestamps of the shorter dictionary to the longer one
    Input: two dictionaries dataset1 and dataset2, for the timestamps you want to align
    Output: modifies in-place the timestamps and corresponding data
    """
    # if the timestamps are the same length, simply reassign
    # does NOT account for mismatching timestamps within data; approximates
    if len(dataset2["Date"]) == len(dataset1["Date"]):
        dataset1["Date"] = dataset2["Date"]
        return

    if len(dataset2["Date"]) - len(dataset1["Date"]) < 0:
        # switch if ds1 is longer than ds2
        temp = dataset1
        dataset1 = dataset2
        dataset2 = temp

    timestamps1 = np.array(dataset1["Date"], dtype=int)
    timestamps2 = np.array(dataset2["Date"], dtype=int)

    # otherwise perform elementwise comparison of timestamps
    # determines if ds1 is earlier/later than ds2 on average
    std_diff = np.std(timestamps2[: len(timestamps1)] - timestamps1)
    diff_tolerance = abs(std_diff)

    print("avg diff:", std_diff)
    print("diff tol", diff_tolerance)
    # ^ positive value: ts2 is later than ts1
    # print(timestamps1)
    # print(timestamps2)

    for i, elem2 in enumerate(timestamps2):
        try:
            elem1 = timestamps1[i]
        except:
            timestamps1.append(elem2)
            elem1 = timestamps1[i]

        # indicates that there might've been a skip in time
        # first case: elem2 is much later than elem1, indicating a skip in ts2
        # realistically, as timestamps2 should be the longer array, the first case should not occur
        # print(elem1, ":", elem2)
        if elem2 - elem1 > (std_diff + diff_tolerance):
            print(
                "ERROR: skip in timestamp detected within the CSV files,"
                + " cannot perform timestamp alignment between two datasets provided"
            )
        elif elem1 - elem2 > (std_diff + diff_tolerance):
            print(elem1, ":", elem2)
            # second case: elem1 is much later than elem2, indicating a skip in ts1
            # append to shorter array, ts1
            timestamps1 = list(np.insert(timestamps1, i, elem2))
            # update data for values
            for key in dataset1:
                if key != "Date":
                    if i == 0:
                        dataset1[key].insert(i, dataset1[key][i + 1])
                    elif i == len(timestamps1) - 1:
                        dataset1[key].insert(i, dataset1[key][i - 1])
                    else:
                        dataset1[key].insert(
                            i, dataset1[key][i - 1] + dataset1[key][i + 1] / 2
                        )
            print("len 1: ", len(timestamps1), "len 2: ", len(timestamps2))
        else:
            # print("reassigning")
            timestamps1[i] = elem2

    # print([ts1 for ts1, ts2 in zip(timestamps1, dataset2['Date']) if ts1 != ts2][::50])
    # print(timestamps2 == dataset2['Date'])
    dataset1["Date"] = timestamps1
    # print([ts1 for ts1, ts2 in zip(dataset1['Date'], dataset2['Date']) if ts1 != ts2][::50])
    assert len(timestamps1) == len(timestamps2)  # length check
    assert (
        timestamps1[int(len(timestamps1) / 2)] == timestamps2[int(len(timestamps2) / 2)]
    )  # midpoint check
    # assert() # checking for deviation
    return


def align():
    if ups_data:
        align_timestamps(hpc_data, ups_data)

    if ent_data:
        align_timestamps(hpc_data, ent_data)

    if ups_data and hpc_data:
        assert hpc_data["Date"] == ups_data["Date"]
    if ent_data and hpc_data:
        assert hpc_data["Date"] == ent_data["Date"]
    print(np.average(np.diff(hpc_data["Date"])))


# CALCULATING MAX/AVERAGES =============================================
def calculate(interval):
    def is_after_16_feb_2024(timestamp):
        return timestamp >= 1708059906  # Fri Feb 16 2024 00:05:06 GMT-0500

    def is_after_13_mar_2024(timestamp):
        return timestamp >= 1710302406  # Wed Mar 13 2024 00:00:06 GMT-0400

    # if neither's specified, turn both on for default behavior
    if not args.avg and not args.max:
        args.avg = True
        args.max = True

    if args.group == "Com Center Main Room":  # MAIN ROOM CALCULATIONS
        # helper function for averaging
        for x in range(0, int(args.numPoints)):
            start = x * interval
            end = (x + 1) * interval

            if args.avg:

                def calculate_avg(data, key):
                    return round(sum(data[key][start:end]) / interval, 2)

                if ups_data:
                    upsAvg = calculate_avg(ups_data, "UPS_AVG")
                if ent_data:
                    entAvg = calculate_avg(ent_data, "Com Center Main Room")

                swUPSAvg = calculate_avg(hpc_data, "SeaWulf Main Room on UPS")
                swNonUPSAvg = calculate_avg(hpc_data, "SeaWulf Main Room on Non-UPS")

                if not hpcOnly and not entOnly and not upsOnly:
                    swAnnexUPSAvg = calculate_avg(hpc_data, "SeaWulf Annex on UPS")

                if upsOnly:  # display only UPS data
                    average = upsAvg
                elif entOnly:  # display only Enterprise Equipment data
                    average = entAvg
                elif hpcOnly:  # display only SeaWulf data
                    average = swUPSAvg + swNonUPSAvg
                else:  # OBTAINING ANNEX DATA
                    if is_after_13_mar_2024(hpc_data["Date"][start]):
                        swAnnexUPSAvg = swAnnexUPSAvg + SCGP_LOAD
                    elif is_after_16_feb_2024(hpc_data["Date"][start]):
                        swAnnexUPSAvg = swAnnexUPSAvg + SCGP_LOAD + ANNEX_A03
                    else:
                        # relying on precomputed values, might not be accurate
                        swAnnexUPSAvg = ANNEX_UPS
                    if nonmetered:
                        # for nonmetered equipment
                        average = upsAvg - entAvg - swUPSAvg - swAnnexUPSAvg
                    else:
                        # for regular main room total
                        average = swNonUPSAvg + upsAvg - swAnnexUPSAvg
                datetime_obj = datetime.fromtimestamp(
                    round(sum(hpc_data["Date"][start:end]) / interval)
                )
                OUTPUT_DATE_FORMAT = "%m/%d-%H:%M"
                date = datetime_obj.strftime(OUTPUT_DATE_FORMAT)
                averages[date] = round(average, 2)

            if args.max:

                def calculate_max(data, key):
                    return round(max(data[key][start:end]), 2)

                if ups_data:
                    upsMax = calculate_max(ups_data, "UPS_AVG")
                if ent_data:
                    entMax = calculate_max(ent_data, "Com Center Main Room")

                swUPSMax = calculate_max(hpc_data, "SeaWulf Main Room on UPS")
                swNonUPSMax = calculate_max(hpc_data, "SeaWulf Main Room on Non-UPS")

                if not (hpcOnly or entOnly or upsOnly):
                    swAnnexUPSMax = calculate_max(ups_data, "SeaWulf Annex on UPS")

                if upsOnly:  # display only UPS data
                    maximum = upsMax
                elif entOnly:  # display only Enterprise Equipment data
                    maximum = entMax
                elif hpcOnly:  # display only SeaWulf data
                    maximum = swUPSMax + swNonUPSMax
                else:
                    # OBTAINING ANNEX DATA
                    if is_after_13_mar_2024(hpc_data["Date"][start]):
                        swAnnexUPSMax = swAnnexUPSMax + SCGP_LOAD
                    elif is_after_16_feb_2024(hpc_data["Date"][start]):
                        swAnnexUPSMax = swAnnexUPSMax + SCGP_LOAD + ANNEX_A03
                    else:
                        swAnnexUPSMax = ANNEX_UPS
                    if nonmetered:  # for nonmetered equipment
                        maximum = upsMax - entMax - swUPSMax - swAnnexUPSMax
                    else:  # for regular main room total
                        maximum = swNonUPSMax + upsMax - swAnnexUPSMax

                datetime_obj = datetime.fromtimestamp(
                    round(sum(hpc_data["Date"][start:end]) / interval)
                )
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date] = round(maximum, 2)

    elif args.group == "Com Center Annex Total":
        for x in range(0, int(args.numPoints)):
            if args.avg:

                def calculate_avg_int(data, key):
                    return round(sum(data[key][start:end]) / interval)

                com_center_load = sum(hpc_data[args.group][start:end]) / interval
                if is_after_13_mar_2024(hpc_data["Date"][x * interval]):
                    annex_load = com_center_load + ANNEX_NONUPS + SCGP_LOAD
                elif is_after_16_feb_2024(hpc_data["Date"][x * interval]):
                    annex_load = com_center_load + ANNEX_A03 + ANNEX_NONUPS + SCGP_LOAD
                else:
                    annex_load = ANNEX_UPS

                timestamp = calculate_avg_int(hpc_data, "Date")
                datetime_obj = datetime.fromtimestamp(timestamp)
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date] = round(annex_load, 2)

            if args.max:  # for the -m flag and default behaviosr
                # print("MAX:" , max(hpc_data[args.group][x*interval : (x+1)*interval]))

                if is_after_13_mar_2024(hpc_data["Date"][x * interval]):
                    annex_load = max(hpc_data[args.group][start:end]) + SCGP_LOAD
                elif is_after_16_feb_2024(hpc_data["Date"][x * interval]):
                    annex_load = (
                        max(hpc_data[args.group][start:end]) + SCGP_LOAD + ANNEX_A03
                    )
                else:
                    annex_load = ANNEX_UPS
                # print("MAX CALCULATED:" , annex_load)
                datetime_obj = datetime.fromtimestamp(
                    round(sum(hpc_data["Date"][start:end]) / interval)
                )
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date] = round(annex_load, 2)
    elif args.group == "SeaWulf Annex on UPS":
        for x in range(0, int(args.numPoints)):
            if args.avg:
                if is_after_13_mar_2024(hpc_data["Date"][x * interval]):
                    annex_load = (
                        sum(hpc_data[args.group][x * interval : (x + 1) * interval])
                        / interval
                    )
                elif is_after_16_feb_2024(hpc_data["Date"][x * interval]):
                    annex_load = (
                        sum(hpc_data[args.group][x * interval : (x + 1) * interval])
                        / interval
                    ) + ANNEX_A03
                else:
                    annex_load = ANNEX_UPS
                datetime_obj = datetime.fromtimestamp(
                    round(
                        sum(hpc_data["Date"][x * interval : (x + 1) * interval])
                        / interval
                    )
                )
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date] = round(annex_load, 2)
            if args.max:  # for the -m flag and default behaviosr
                if is_after_13_mar_2024(hpc_data["Date"][x * interval]):
                    annex_load = max(
                        hpc_data[args.group][x * interval : (x + 1) * interval]
                    )
                elif is_after_16_feb_2024(hpc_data["Date"][x * interval]):
                    annex_load = (
                        max(hpc_data[args.group][x * interval : (x + 1) * interval])
                    ) + ANNEX_A03
                else:
                    annex_load = ANNEX_UPS
                # print("MAX CALCULATED:" , annex_load)
                datetime_obj = datetime.fromtimestamp(
                    round(
                        sum(hpc_data["Date"][x * interval : (x + 1) * interval])
                        / interval
                    )
                )
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date] = round(annex_load, 2)
    else:  # for non main room
        for x in range(0, int(args.numPoints)):
            if args.avg:  # for the -a flag and default behavior
                average = round(
                    sum(hpc_data[args.group][x * interval : (x + 1) * interval])
                    / interval,
                    2,
                )
                datetime_obj = datetime.fromtimestamp(
                    round(
                        sum(hpc_data["Date"][x * interval : (x + 1) * interval])
                        / interval
                    )
                )
                date = datetime_obj.strftime("%m/%d-%H:%M")
                averages[date] = average
            if args.max:  # for the -m flag and default behavior
                maxim = round(
                    max(hpc_data[args.group][x * interval : (x + 1) * interval]), 2
                )
                datetime_obj = datetime.fromtimestamp(
                    round(
                        sum(hpc_data["Date"][x * interval : (x + 1) * interval])
                        / interval
                    )
                )
                date = datetime_obj.strftime("%m/%d-%H:%M")
                maxes[date] = maxim

    totAvg = "--"  # calculating cumulative values
    totMax = "--"
    if averages:
        totAvg = round(sum(averages.values()) / len(averages), 3)
    if maxes:
        totMax = round(max(maxes.values()), 3)
    stats = f"Cumulative Average: {totAvg} kW   Cumulative Max: {totMax} kW"
    period = f"Data from {startDate} to {endDate}"

    print("\nSETTING UP FIGURE...")
    fig, ax = plt.subplots()
    fig.set_size_inches(19.2, 14.4)

    if averages:
        dates, avgs = list(averages.keys()), list(averages.values())
        plt.plot(np.arange(len(dates)), avgs, label="average")
        if not args.plotClean:
            for i, val in enumerate(avgs):
                plt.text(i, val, str(val), fontsize=8)
        # print(dates, avgs)
    if maxes:
        dates, maxs = list(maxes.keys()), list(maxes.values())
        plt.plot(np.arange(len(dates)), maxs, label="maximum")
        if not args.plotClean:
            for i, val in enumerate(maxs):
                plt.text(i, val, str(val), fontsize=8)
        # print(dates, maxs)

    plt.xticks(np.arange(len(dates)), dates, fontsize=9)
    plt.annotate(stats, xy=(0.5, 0.9), xycoords="figure fraction", ha="center")
    plt.annotate(period, xy=(0.5, 0.92), xycoords="figure fraction", ha="center")
    for i, disclaimer in enumerate(disclaimers):
        plt.annotate(
            disclaimer,
            xy=(0.5, 0.85 - 0.01 * i),
            xycoords="figure fraction",
            ha="center",
            fontsize=8,
            color="red",
        )

    ax.set_title(f"Power Data for {args.group} {headerData}", y=1.07)
    ax.set_xlabel("Time")
    ax.set_ylabel("Power usage (kW)")
    # ax.set_ylim(min(filedata[args.group]) - totMax * 0.05, totMax + totMax * 0.1)

    ticks = ax.xaxis.get_ticklabels()

    if numDays < 5 and int(args.numPoints) < 26:  # labels 13 ticks
        for label in ax.xaxis.get_ticklabels()[1::2]:
            label.set_visible(False)

    elif numDays < 5:
        interval = int(args.numPoints) // 12 + (int(args.numPoints) % 12 > 0)
        for i in range(0, len(ticks)):
            if i % interval != 0:
                ticks[i].set_visible(False)

    else:  # only labels different days if plotting more than 5 days
        ticks[0].set_text(ticks[0].get_text()[0:5])
        if numDays > 21:
            interval = (numDays // 12) + (numDays % 12 > 0)
        else:
            interval = 1
        x = 1
        for i in range(1, len(ticks)):
            if ticks[i].get_text()[0:5] == ticks[i - 1].get_text()[0:5]:
                ticks[i].set_visible(False)
            else:
                if x % interval != 0:
                    ticks[i].set_visible(False)
                else:
                    ticks[i].set_text(ticks[i].get_text()[0:5])
                x = x + 1

    plt.xticks(np.arange(len(dates)), ticks)

    plt.legend()
    # plt.show()
    plt.savefig("out.png")


def main():
    locale.setlocale(locale.LC_ALL, "en_US")

    parse_HPC()
    print("HPC DATA PARSED:", list(hpc_data.keys()))
    if len(hpc_data[args.group]) < int(args.numPoints):
        print("Cannot have more points than there are data")
        exit()

    # determines data point per entry
    interval = int(len(hpc_data[args.group]) / int(args.numPoints))
    print("HPC LENGTH:", len(hpc_data[args.group]))

    # INCLUDE ENTERPRISE EQUIPMENT DATA
    if args.group == "Com Center Main Room" and not hpcOnly and not upsOnly:
        parse_ENT()
        for key, value in ent_data.items():
            print(key, value[:1])
        print("ENT LENGTH:", len(ent_data[args.group]))

    if args.group == "Com Center Main Room" and not hpcOnly and not entOnly:
        parse_UPS()
        for key, value in ups_data.items():
            print(key, value[:1])
        print("UPS LENGTH:", len(ups_data["UPS_AVG"]))

    clean_data(hpc_data)
    if ups_data is not None:
        clean_data(ups_data)
    if ent_data is not None:
        clean_data(ent_data)

    align()
    calculate(interval)
    return


main()
