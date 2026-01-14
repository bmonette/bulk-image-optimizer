from pathlib import Path

from bio.engine import process_image
from bio.settings import OptimizeSettings


def main() -> None:
    # Change these paths to something on your machine for a quick test.
    src = Path(r"C:\test\sample.jpg")

    settings = OptimizeSettings(
        output_dir=Path("output"),
        output_format="keep",
        strip_metadata=True,
        only_if_smaller=True,
    )

    result = process_image(src, settings)
    print(result)


if __name__ == "__main__":
    main()
