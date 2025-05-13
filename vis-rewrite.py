import argparse
import datetime as dt
import pandas
import sys


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


def parse_cli_args(csv_headers):
    parser = argparse.ArgumentParser(
        description="Parses and visualizes SNMP power data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

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

    group_date = parser.add_mutually_exclusive_group(required=True)
    group_date.add_argument(
        "-d",
        "--days",
        dest="num_days",
        type=positive_float,
        default=7.0,
        help="number of days of data to include",
    )
    group_date.add_argument(
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
        help="chart average load only",
    )
    group_graphing.add_argument(
        "-m",
        "--max",
        dest="max_load",
        action="store_true",
        help="chart maximum load only",
    )

    def valid_date(str):
        try:
            timestamp = dt.datetime.strptime(str, "%m/%d/%Y")
        except ValueError:
            raise argparse.ArgumentTypeError(f"not a valid date: {str!r}")
        return timestamp

    def positive_float(number):
        try:
            float_number = float(number)
        except ValueError:
            raise argparse.ArgumentTypeError(f"Invalid numeric value: {number!r}")
        if float_number <= 0:
            raise argparse.ArgumentTypeError(f"Value must be > 0; got {number}")
        return float_number

    return parser.parse_args(sys.argv[1:] or ["-h"])


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


def main():
    csv_headers = get_headers()
    args = parse_cli_args(csv_headers)

    if args.group == None:
        option = prompt_missing_group_category()
        power_unit_list = get_headers(option)
        args.group = prompt_missing_group(power_unit_list)




if __name__ == "__main__":
    main()
