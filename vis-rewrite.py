import argparse
import pandas
import datetime as dt


def get_headers():
    # eventually do away with the constant and
    # fetch the headers directly in csv
    return [
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


def parse_cli_args(csv_headers):
    parser = argparse.ArgumentParser(
        description="Parses and visualizes SNMP power data.",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )

    parser.add_argument(
        "-g",
        "--group",
        choices=csv_headers,
        default="Com Center Main Room",
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
    
    return parser.parse_args()



def main():
    csv_headers = get_headers()
    args = parse_cli_args(csv_headers)


if __name__ == "__main__":
    main()
