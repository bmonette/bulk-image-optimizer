from pathlib import Path

from bio.batch import process_batch
from bio.settings import OptimizeSettings
from bio.report import build_report, save_report_json, save_report_csv
from bio.cli import main

if __name__ == "__main__":
    raise SystemExit(main())


def main() -> None:
    inputs = [Path("C:/test")]  # folder or list of files/folders

    settings = OptimizeSettings(
        output_dir=Path("C:/test/output"),
        output_format="keep",
        strip_metadata=True,
        only_if_smaller=True,
        write_even_if_bigger_when_stripping_metadata=True,  # <-- the whole point of Test B
        overwrite=False,
        jpeg_quality=82,
    )



    results, summary = process_batch(inputs, settings, recursive=True)

    print("\n=== Batch Summary ===")
    print("Total found:", summary.total_files)
    print("Processed  :", summary.processed)
    print("Skipped    :", summary.skipped)
    print(f"Saved      : {summary.saved_bytes} bytes ({summary.saved_percent:.1f}%)")

    report = build_report(results, summary)
    report_path = settings.output_dir / "report.json"
    save_report_json(report, report_path)
    print("\nReport written:", report_path)

    csv_path = settings.output_dir / "report.csv"
    save_report_csv(report, csv_path)
    print("CSV written   :", csv_path)

    # Optional: print skip reasons breakdown
    reasons = {}
    for r in results:
        if r.out_path is None and r.skipped_reason:
            reasons[r.skipped_reason] = reasons.get(r.skipped_reason, 0) + 1

    if reasons:
        print("\nSkip reasons:")
        for k, v in sorted(reasons.items(), key=lambda x: (-x[1], x[0])):
            print(f"  {k}: {v}")


if __name__ == "__main__":
    main()
