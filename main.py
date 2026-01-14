from pathlib import Path

from bio.batch import process_batch
from bio.settings import OptimizeSettings


def main() -> None:
    inputs = [Path("C:/test")]  # folder or list of files/folders

    settings = OptimizeSettings(
        output_dir=Path("C:/test/output"),
        output_format="keep",
        strip_metadata=True,
        only_if_smaller=True,  # skip outputs that are larger...
        write_even_if_bigger_when_stripping_metadata=False,  # ...unless you want guaranteed metadata stripping
        overwrite=False,
        jpeg_quality=82,
    )


    results, summary = process_batch(inputs, settings, recursive=True)

    print("\n=== Batch Summary ===")
    print("Total found:", summary.total_files)
    print("Processed  :", summary.processed)
    print("Skipped    :", summary.skipped)
    print(f"Saved      : {summary.saved_bytes} bytes ({summary.saved_percent:.1f}%)")

    # Optional: print skip reasons breakdown (simple)
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
