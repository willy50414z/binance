import argparse
from pathlib import Path

import pandas as pd


def convert_feather_to_csv(input_path: Path, output_path: Path) -> None:
    df = pd.read_feather(input_path)
    df.to_csv(output_path, index=False)


def main() -> None:
    parser = argparse.ArgumentParser(description="Convert market_change.feather to CSV.")
    parser.add_argument("--input", required=True, help="Input feather file path")
    parser.add_argument("--output", help="Output CSV file path (default: same name with .csv)")
    args = parser.parse_args()

    input_path = Path(args.input).expanduser().resolve()
    if not input_path.exists():
        raise FileNotFoundError(f"Input file not found: {input_path}")

    output_path = (
        Path(args.output).expanduser().resolve()
        if args.output
        else input_path.with_suffix(".csv")
    )
    output_path.parent.mkdir(parents=True, exist_ok=True)

    convert_feather_to_csv(input_path, output_path)
    print(f"Converted: {input_path}")
    print(f"Output: {output_path}")


if __name__ == "__main__":
    main()
