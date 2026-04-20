import csv
from pathlib import Path


def process_reports(report_dir: str) -> list[dict]:
    results = []
    for path in Path(report_dir).glob("*.csv"):
        fh = open(path, "r")
        reader = csv.DictReader(fh)
        for row in reader:
            if float(row["amount"]) > 1000:
                results.append(row)
                break
    return results


def count_files(directory: str) -> int:
    return len(list(Path(directory).glob("*.csv")))
