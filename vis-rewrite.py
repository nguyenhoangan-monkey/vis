import argparse
import csv
import datetime as dt
import locale
import pandas
import pathlib
import re
import subprocess

from typing import Any


def get_headers(*args):
    # eventually do away with the constant and
    # fetch the headers directly in csv
    A_SERIES_PDUS = [
        "PDU-A10-1",
        "PDU-A10-2",
        "PDU-A10-3",
        "PDU-A4-1",
        "PDU-A4-2",
        "PDU-A5-1",
        "PDU-A5-2",
        "PDU-A5-3",
        "PDU-A5-4",
        "PDU-A5-5",
        "PDU-A6-1",
        "PDU-A6-2",
        "PDU-A6-3",
        "PDU-A7-1",
        "PDU-A7-2",
        "PDU-A7-3",
        "PDU-A8-1",
        "PDU-A8-2",
        "PDU-A8-3",
        "PDU-A8-4",
    ]

    B_SERIES_PDUS = [
        "PDU-B1-1",
        "PDU-B1-2",
        "PDU-B1-3",
        "PDU-B2-1",
        "PDU-B2-2",
        "PDU-B3-1",
        "PDU-B3-2",
        "PDU-B3-3",
        "PDU-B3-4",
        "PDU-B4-1",
        "PDU-B4-2",
    ]

    D_SERIES_PDUS = [
        "PDU-D1-1",
        "PDU-D1-2",
        "PDU-D1-3",
        "PDU-D1-4",
        "PDU-D2-1",
        "PDU-D2-2",
        "PDU-D2-3",
        "PDU-D2-4",
        "PDU-D3-1",
        "PDU-D3-2",
        "PDU-D3-3",
        "PDU-D3-4",
        "PDU-D4-1",
        "PDU-D4-2",
        "PDU-D4-3",
        "PDU-D4-4",
        "PDU-D5-1",
        "PDU-D5-2",
        "PDU-D5-3",
    ]

    OTHER_RACK_POWER_UNITS = [
        "UPS-PDU1",
        "UPS-PDU2",
        "SW-EPS1",
        "SW-EPS2",
        "SW-EPS3",
        "PDU-A0-1",
        "PDU-A0-2",
        "PDU-A0-3",
        "PDU-C4-1",
        "PDU-C4-2",
    ]

    FACILITY_LEVEL_AGGREGATES = [
        "Com Center Main Room",
        "Com Center A-Aisle",
        "Com Center B-Aisle",
        "SeaWulf Main Room on UPS",
        "SeaWulf Main Room on Non-UPS",
        "SeaWulf Annex on UPS",
        "SeaWulf Annex on Non-UPS",
        "Com Center Annex Total",
        "IACS Total",
        "IACS Main Panel",
        "IACS RP2 Panel",
    ]

    if len(args) == 0:
        return (
            A_SERIES_PDUS
            + B_SERIES_PDUS
            + D_SERIES_PDUS
            + OTHER_RACK_POWER_UNITS
            + FACILITY_LEVEL_AGGREGATES
        )
    elif len(args) == 1:
        # logic is in prompt_missing_group_category()
        if args[0] == 0:
            return A_SERIES_PDUS
        elif args[0] == 1:
            return B_SERIES_PDUS
        elif args[0] == 2:
            return D_SERIES_PDUS
        elif args[0] == 3:
            return OTHER_RACK_POWER_UNITS
        elif args[0] == 4:
            return FACILITY_LEVEL_AGGREGATES
        else:
            raise TypeError("get_headers() argument in /{0, 1, 2, 3, 4/}")
    else:
        raise TypeError("get_headers() only takes zero or one argument")


# USAGE: -g GROUP -d DAYS -p POINTS [-s START] [-e END] [-a] [-m]
def parse_cli_args(csv_headers):
    parser = argparse.ArgumentParser(
        description="Parses and visualizes SNMP power data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    def valid_date(str):
        try:
            timestamp = dt.datetime.strptime(str, "%m/%d/%Y")
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a valid date: {str!r}")
        return timestamp

    def greater_than_2_hours_float(number):
        try:
            float_number = float(number)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid numeric value: {number!r}")
        if float_number < 0.08:
            raise argparse.ArgumentTypeError(f"numDays must be >= 0.08; got {number}")
        return float_number

    parser.add_argument(
        "-g",
        "--group",
        choices=csv_headers,
        help="PDU group (e.g. ARACK, MAINROOM, IACS)",
    )
    parser.add_argument(
        "-s",
        "--start",
        dest="start_date",
        type=valid_date,
        default=dt.date.today() - dt.timedelta(days=7),
        metavar="MM/DD/YYYY",
        help="start date (inclusive)",
    )
    parser.add_argument(
        "-d",
        "--days",
        dest="num_days",
        type=greater_than_2_hours_float,
        default=7.0,
        help="number of days of data to include",
    )
    parser.add_argument(
        "-e",
        "--end",
        dest="end_date",
        type=valid_date,
        default=dt.date.today(),
        metavar="MM/DD/YYYY",
        help="end date (inclusive)",
    )
    parser.add_argument(
        "-p",
        "--points",
        dest="num_points",
        type=int,
        default=50,
        help="number of plot points",
    )
    parser.add_argument(
        "--clean",
        dest="plot_clean",
        action="store_true",
        help="omit labels on every data point",
    )

    group_graphing = parser.add_mutually_exclusive_group()
    group_graphing.add_argument(
        "-a",
        "--average",
        dest="avg",
        action="store_true",
        default=False,
        help="chart average load only",
    )
    group_graphing.add_argument(
        "-m",
        "--max",
        dest="max",
        action="store_true",
        default=False,
        help="chart maximum load only",
    )

    return parser.parse_args()


def prompt_missing_group_category():
    while True:
        prompt_input = input(
            """Group name is not specified in the command line.
        Please enter a value:
        0) A-series PDUs
        1) B-series PDUs
        2) D-series PDUs
        3) Other rack power units
        4) Facility level aggregates
        > """
        ).strip()

        if prompt_input.isdigit():
            option = int(prompt_input)
            if 0 <= option <= 4:
                return option

        print(f"Invalid input: {prompt_input!r}")
        print("Please enter a number between 0 and 4.")


def prompt_missing_group(power_unit_list):
    while True:
        prompt_input = input(
            f"""Please type in one of the following options:\n{power_unit_list}
        > """
        ).strip()

        if prompt_input in power_unit_list:
            return prompt_input

        print(f"Invalid name: {prompt_input!r}")


def prompt_com_center_main_room():
    # feeling that the upsOnly, entOnly, hpcOnly variables are redundant
    option = 0
    while True:
        prompt_input = input(
            """There are many sections within the Com Center Main Room.
        Please enter which sections you want its power data to be graphed:
        1) Whole room, total
        2) UPS data-only
        3) Enterprise aisle-only
        4) HPC data-only
        5) nonmetered equipment
        > """
        ).strip()

        if prompt_input.isdigit():
            option = int(prompt_input)
            if 1 <= option <= 5:
                break

        print(f"Invalid input: {prompt_input!r}")
        print("Please enter a number between 1 and 5.")

    if option == 1:
        return {
            "upsOnly": False,
            "entOnly": False,
            "hpcOnly": False,
            "nonmetered": False,
            "headerData": "",
        }
    elif option == 2:
        return {
            "upsOnly": True,
            "entOnly": False,
            "hpcOnly": False,
            "nonmetered": False,
            "headerData": "UPS",
        }
    elif option == 3:
        return {
            "upsOnly": False,
            "entOnly": True,
            "hpcOnly": False,
            "nonmetered": False,
            "headerData": "ENT",
        }
    elif option == 4:
        return {
            "upsOnly": False,
            "entOnly": False,
            "hpcOnly": True,
            "nonmetered": False,
            "headerData": "HPC",
        }
    elif option == 5:
        return {
            "upsOnly": False,
            "entOnly": False,
            "hpcOnly": False,
            "nonmetered": True,
            "headerData": "Nonmetered",
        }
    else:
        raise ValueError("Input is not santized in prompt_com_center_main_room()")


def get_date_bounds(args):
    # TODO: somewhat iffy logic in vis.py, not sure about expected behavior
    delta = dt.timedelta(days=float(args.num_days))
    time_now = dt.datetime.now()
    start_date = args.start_date or (time_now - delta)
    end_date = (start_date + delta) or args.end_date
    num_days = (end_date - start_date).days
    return {
        "startDate": start_date,
        "endDate": end_date,
        "numDays": num_days,
    }


def file_names_in_range(start: str, end: str):
    start_date = dt.datetime.strptime(start, "%Y-%m-%d").date()
    end_date = dt.datetime.strptime(end, "%Y-%m-%d").date()

    files = []
    for path in pathlib.Path(".").glob("*.csv"):
        try:
            filename_date = dt.datetime.strptime(path.stem, "%Y-%m-%d").date()
            if start_date <= filename_date <= end_date:
                files.append((filename_date, str(path)))
        except ValueError:
            continue

    return [f for _, f in sorted(files)]

def get_file_names_pandas():
    pass #TODO use pandas

def timestamp_in_range(row, search_config):
    after_start_date = int(row['Date']) >= dt.datetime.timestamp(search_config["startDate"])
    before_end_date = int(row['Date']) <= dt.datetime.timestamp(search_config["endDate"])
    return after_start_date and before_end_date

def write_to_hpc_data(row, file, search_config, group_name, hpc_data):
    hpc_data['Date'].append(int(row['Date']))
    if group_name not in row: # data does not exists, use 0 as a placeholder
        hpc_data[group_name].append(float(0))

    if (group_name == 'Com Center Main Room'):
        ups_watts = float(row['SeaWulf Main Room on UPS'])
        non_ups_watts = float(row['SeaWulf Main Room on Non-UPS'])

        hpc_data['SeaWulf Main Room on UPS'].append(ups_watts)
        hpc_data['SeaWulf Main Room on Non-UPS'].append(non_ups_watts)
        hpc_data[group_name].append(ups_watts + non_ups_watts)

        annex_data_needed = not (search_config["hpcOnly"]
                                    or search_config["upsOnly"]
                                    or search_config["entOnly"])
        if (annex_data_needed):
            if (file >= '2024-02-16.csv'):
                hpc_data['SeaWulf Annex on UPS'].append(float(row['SeaWulf Annex on UPS']))
            else: # annex data does not exists, use 0 as a placeholder
                hpc_data['SeaWulf Annex on UPS'].append(float(0))
    else: 
        hpc_data[group_name].append(float(row[group_name]))

def parse_HPC(group_name: str, search_config: dict[str, Any]):
    # TODO: check logic and make the function more resilient
    # TODO: use PANDAS
    # Parses the files from the relevant time period generated by HPC polling.
    #     hpc_data -> {Date: [timestamps], 'group_name': [values] ...}
    # HPC is a dictionary with an array for timestamps,
    # and array(s) for the relevant polling data.
    # This includes Computing Center Annex UPS and Non-UPS, if necessary.

    hpc_data = {
        "Date": [],
        group_name: [],
        "SeaWulf Main Room on UPS": [],
        "SeaWulf Main Room on Non-UPS": [],
        "SeaWulf Annex on UPS": [],
    }

    files = file_names_in_range(search_config['startDate'].date(), search_config['endDate'].date())
    print(files)

    for file in files:
        with open(file, 'r') as f:
            for row in csv.DictReader(f): # TODO: use pandas
                if (timestamp_in_range(row, search_config)):
                    write_to_hpc_data(row, file, search_config, group_name, hpc_data)
    
    return hpc_data



def main():
    locale.setlocale(locale.LC_ALL, "en_US")
    csv_headers = get_headers()
    args = parse_cli_args(csv_headers)

    if args.group == None:
        option = prompt_missing_group_category()
        power_unit_list = get_headers(option)
        args.group = prompt_missing_group(power_unit_list)

    if args.group == "Com Center Main Room":
        search_config = prompt_com_center_main_room()
    else:
        search_config = {
            "upsOnly": False,
            "entOnly": False,
            "hpcOnly": False,
            "nonmetered": False,
            "headerData": "",
        }

    date_dict = get_date_bounds(args)
    search_config.update(date_dict)

    print(
        f"""
    Group:            {args.group}
    Start Date:       {args.start_date}
    Days:             {args.num_days}
    Average?          {args.avg}
    Max?              {args.max}
    Number of Points? {args.num_points}
    ---
    Start time:       {search_config['startDate']}
    End time:         {search_config['endDate']}
    """
    )

    hpc_data = parse_HPC(args.group, search_config)


if __name__ == "__main__":
    main()
