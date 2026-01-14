from pathlib import Path

from bio.engine import process_image
from bio.settings import OptimizeSettings


def main() -> None:
    src = Path("C:/test/sample.jpg")

    settings = OptimizeSettings(
        output_dir=Path("C:/test/output"),
        output_format="keep",     # try "webp" too
        strip_metadata=True,
        only_if_smaller=False,    # set True after testing once
        overwrite=True,
        jpeg_quality=82,
    )

    result = process_image(src, settings)
    print(result)
    if result.out_path:
        print("Wrote:", result.out_path)
        print(f"Saved: {result.saved_bytes} bytes ({result.saved_percent:.1f}%)")


if __name__ == "__main__":
    main()
