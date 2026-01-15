import threading
import queue
from typing import Any
import tkinter as tk
from tkinter import filedialog, messagebox, ttk
from pathlib import Path

from .batch import process_batch
from .report import build_report, save_report_csv, save_report_json
from .settings import OptimizeSettings


APP_VERSION = "1.0.0"


def run_app() -> None:
    app = BioGui()
    app.mainloop()


class BioGui(tk.Tk):
    def __init__(self) -> None:
        super().__init__()
        self.title("Bulk Image Optimizer v{APP_VERSION}")
        self.geometry("820x520")
        self.minsize(780, 480)

        # ---------- Variables ----------
        self.input_dir = tk.StringVar(value=str(Path.home()))
        self.output_dir = tk.StringVar(value=str(Path.home() / "bio_output"))

        self.preset = tk.StringVar(value="(none)")
        self.output_format = tk.StringVar(value="keep")
        self.suffix = tk.StringVar(value="_optimized")

        self.strip_metadata = tk.BooleanVar(value=True)
        self.only_if_smaller = tk.BooleanVar(value=True)
        self.allow_bigger_for_metadata = tk.BooleanVar(value=False)
        self.dry_run = tk.BooleanVar(value=False)
        self.allow_reprocess = tk.BooleanVar(value=False)

        self.max_width = tk.StringVar(value="")
        self.max_height = tk.StringVar(value="")
        self.crop_ratio = tk.StringVar(value="")  # accepts 1:1, 16:9, 1.777...

        self.jpeg_quality = tk.StringVar(value="82")
        self.webp_quality = tk.StringVar(value="80")
        self.webp_lossless = tk.BooleanVar(value=False)

        self._worker: threading.Thread | None = None
        self._cancel_event = threading.Event()

        self._q: queue.Queue[tuple[Any, ...]] = queue.Queue()
        self._polling = False

        self._option_widgets: list[tk.Widget] = []

        # ---------- UI ----------
        self._build_ui()

    # ---------------- UI building ----------------
    def _build_ui(self) -> None:
        root = ttk.Frame(self, padding=12)
        root.pack(fill="both", expand=True)

        # Top: paths
        paths = ttk.LabelFrame(root, text="Paths", padding=10)
        paths.pack(fill="x")

        self._path_row(paths, "Input folder:", self.input_dir, self._browse_input)
        self._path_row(paths, "Output folder:", self.output_dir, self._browse_output)

        # Middle: options (two columns)
        mid = ttk.Frame(root)
        mid.pack(fill="both", expand=True, pady=(12, 0))

        left = ttk.LabelFrame(mid, text="Options", padding=10)
        left.pack(side="left", fill="both", expand=True, padx=(0, 6))

        right = ttk.LabelFrame(mid, text="Advanced", padding=10)
        right.pack(side="left", fill="both", expand=True, padx=(6, 0))

        self._build_left(left)
        self._build_right(right)

        # Bottom: run + status
        bottom = ttk.Frame(root)
        bottom.pack(fill="x", pady=(12, 0))

        self.run_btn = ttk.Button(bottom, text="Run", command=self._on_run)
        self.run_btn.pack(side="left")

        self.cancel_btn = ttk.Button(bottom, text="Cancel", command=self._on_cancel, state="disabled")
        self.cancel_btn.pack(side="left", padx=(8, 0))

        self.open_btn = ttk.Button(bottom, text="Open Output Folder", command=self._open_output, state="disabled")
        self.open_btn.pack(side="left", padx=(8, 0))

        self.file_label = ttk.Label(bottom, text="", anchor="w")
        self.file_label.pack(side="left", fill="x", expand=True, padx=(12, 0))

        self.progress_var = tk.IntVar(value=0)

        self.progress_label = ttk.Label(bottom, text="0 / 0")
        self.progress_label.pack(side="right", padx=(8, 0))

        self.progress = ttk.Progressbar(bottom, mode="determinate", variable=self.progress_var)
        self.progress.pack(side="right", fill="x", expand=True, padx=(12, 0))

        self.status = tk.Text(root, height=7, wrap="word")
        self.status.pack(fill="both", expand=False, pady=(12, 0))
        self._log("Ready.")

    def _path_row(self, parent: ttk.Frame, label: str, var: tk.StringVar, browse_cmd) -> None:
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)

        ttk.Label(row, text=label, width=12).pack(side="left")

        entry = ttk.Entry(row, textvariable=var)
        entry.pack(side="left", fill="x", expand=True, padx=(6, 6))

        btn = ttk.Button(row, text="Browse...", command=browse_cmd)
        btn.pack(side="left")

        self._option_widgets.extend([entry, btn])

    def _build_left(self, parent: ttk.Frame) -> None:
        # Preset
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Preset:", width=10).pack(side="left")

        presets = ["(none)", "blog", "ecommerce", "aggressive", "webp"]
        preset_cb = ttk.Combobox(
            row,
            textvariable=self.preset,
            values=presets,
            state="readonly",
        )
        preset_cb.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._option_widgets.append(preset_cb)

        # Format
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Format:", width=10).pack(side="left")

        formats = ["keep", "jpeg", "png", "webp"]
        format_cb = ttk.Combobox(
            row,
            textvariable=self.output_format,
            values=formats,
            state="readonly",
        )
        format_cb.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._option_widgets.append(format_cb)

        # Suffix
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Suffix:", width=10).pack(side="left")
        suffix_entry = ttk.Entry(row, textvariable=self.suffix)
        suffix_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._option_widgets.append(suffix_entry)

        ttk.Separator(parent).pack(fill="x", pady=8)

        # Toggles
        cb = ttk.Checkbutton(parent, text="Strip metadata", variable=self.strip_metadata)
        cb.pack(anchor="w")
        self._option_widgets.append(cb)

        cb = ttk.Checkbutton(parent, text="Only write if smaller", variable=self.only_if_smaller)
        cb.pack(anchor="w")
        self._option_widgets.append(cb)

        cb = ttk.Checkbutton(parent, text="Allow bigger when stripping metadata", variable=self.allow_bigger_for_metadata)
        cb.pack(anchor="w")
        self._option_widgets.append(cb)

        cb = ttk.Checkbutton(parent, text="Dry run (estimate only)", variable=self.dry_run)
        cb.pack(anchor="w")
        self._option_widgets.append(cb)

        cb = ttk.Checkbutton(parent, text="Allow reprocess (files already ending with suffix)", variable=self.allow_reprocess)
        cb.pack(anchor="w")
        self._option_widgets.append(cb)

        ttk.Separator(parent).pack(fill="x", pady=8)

        # Resize + Crop
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Max width:", width=10).pack(side="left")

        maxw_entry = ttk.Entry(row, textvariable=self.max_width, width=10)
        maxw_entry.pack(side="left", padx=(6, 12))
        self._option_widgets.append(maxw_entry)

        ttk.Label(row, text="Max height:").pack(side="left")

        maxh_entry = ttk.Entry(row, textvariable=self.max_height, width=10)
        maxh_entry.pack(side="left", padx=(6, 0))
        self._option_widgets.append(maxh_entry)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="Crop ratio:", width=10).pack(side="left")

        crop_entry = ttk.Entry(row, textvariable=self.crop_ratio)
        crop_entry.pack(side="left", fill="x", expand=True, padx=(6, 0))
        self._option_widgets.append(crop_entry)

        ttk.Label(
            parent,
            text='Examples: 1:1, 16:9, 4:3, or 1.777',
            foreground="gray",
        ).pack(anchor="w", pady=(2, 0))

    def _build_right(self, parent: ttk.Frame) -> None:
        # JPEG/WebP options
        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="JPEG quality:", width=12).pack(side="left")

        jpegq_entry = ttk.Entry(row, textvariable=self.jpeg_quality, width=8)
        jpegq_entry.pack(side="left", padx=(6, 0))
        self._option_widgets.append(jpegq_entry)

        row = ttk.Frame(parent)
        row.pack(fill="x", pady=4)
        ttk.Label(row, text="WebP quality:", width=12).pack(side="left")

        webpq_entry = ttk.Entry(row, textvariable=self.webp_quality, width=8)
        webpq_entry.pack(side="left", padx=(6, 0))
        self._option_widgets.append(webpq_entry)

        cb = ttk.Checkbutton(parent, text="WebP lossless", variable=self.webp_lossless)
        cb.pack(anchor="w", pady=(6, 0))
        self._option_widgets.append(cb)

        ttk.Separator(parent).pack(fill="x", pady=10)

        ttk.Label(
            parent,
            text="Notes:\n- GUI v1 uses a determinate progress bar.\n- Reports are always written to output folder.",
            foreground="gray",
            justify="left",
        ).pack(anchor="w")


    # ---------------- Actions ----------------
    def _browse_input(self) -> None:
        p = filedialog.askdirectory(title="Select input folder")
        if p:
            self.input_dir.set(p)

    def _browse_output(self) -> None:
        p = filedialog.askdirectory(title="Select output folder")
        if p:
            self.output_dir.set(p)

    def _open_output(self) -> None:
        out = Path(self.output_dir.get())
        if out.exists():
            # Windows-friendly folder open
            import os
            os.startfile(out)  # type: ignore[attr-defined]

    def _on_run(self) -> None:
        if self._worker and self._worker.is_alive():
            messagebox.showinfo("Running", "A batch is already running.")
            return

        try:
            settings, inputs = self._build_settings_from_ui()
        except ValueError as e:
            messagebox.showerror("Invalid settings", str(e))
            return

        self.run_btn.config(state="disabled")
        self.open_btn.config(state="disabled")
        self._cancel_event.clear()
        self.cancel_btn.config(state="normal")
        self.progress_var.set(0)
        self.progress["maximum"] = 1
        self.progress_label.config(text="0 / 0")
        self.file_label.config(text="")
        self._log("Running...")
        self._set_options_enabled(False)


        self._polling = True
        self.after(50, self._poll_queue)

        def work():
            try:
                def on_progress(current: int, total: int) -> None:
                    self._q.put(("progress", current, total))

                def on_file(path: Path, current: int, total: int) -> None:
                    self._q.put(("file", path.name, current, total))

                results, summary = process_batch(
                    inputs,
                    settings,
                    recursive=True,
                    progress_callback=on_progress,
                    cancel_event=self._cancel_event,
                    file_callback=on_file,
                )

                report = build_report(results, summary)
                save_report_json(report, settings.output_dir / "report.json")
                save_report_csv(report, settings.output_dir / "report.csv")

                was_cancelled = self._cancel_event.is_set()

                status_line = "CANCELLED" if was_cancelled else "DONE"
                msg = (
                    f"\n=== Batch Summary ({status_line}) ===\n"
                    f"Total found: {summary.total_files}\n"
                    f"Processed  : {summary.processed}\n"
                    f"Skipped    : {summary.skipped}\n"
                    f"Saved      : {summary.saved_bytes} bytes ({summary.saved_percent:.1f}%)\n"
                    f"Report: {settings.output_dir / 'report.json'}\n"
                    f"CSV   : {settings.output_dir / 'report.csv'}\n"
                )
                self._q.put(("done", msg))
            except Exception as ex:
                self._q.put(("error", ex))

        self._worker = threading.Thread(target=work, daemon=True)
        self._worker.start()

    def _on_cancel(self) -> None:
        if self._worker and self._worker.is_alive():
            self._cancel_event.set()
            self._log("Cancel requested... finishing current file.")
            self.cancel_btn.config(state="disabled")

    def _poll_queue(self) -> None:
        try:
            while True:
                item = self._q.get_nowait()
                kind = item[0]

                if kind == "progress":
                    _, current, total = item
                    self._set_progress(int(current), int(total))

                elif kind == "file":
                    _, filename, current, total = item
                    self.file_label.config(text=f"Processing: {filename}")

                elif kind == "done":
                    _, msg = item
                    self._polling = False
                    self._finish_ok(str(msg))
                    return

                elif kind == "error":
                    _, ex = item
                    self._polling = False
                    self._finish_err(ex)
                    return

        except queue.Empty:
            pass
        except Exception as ex:
            # If polling crashes, recover UI instead of freezing
            self._polling = False
            self._finish_err(ex)
            return

        if self._polling:
            self.after(50, self._poll_queue)

    def _finish_ok(self, msg: str) -> None:
        self.run_btn.config(state="normal")
        self.open_btn.config(state="normal")
        self.cancel_btn.config(state="disabled")
        self._log(msg)
        self._log("Done.")
        self.file_label.config(text="")
        self._set_options_enabled(True)

    def _finish_err(self, ex: Exception) -> None:
        self.run_btn.config(state="normal")
        self.open_btn.config(state="disabled")
        self.cancel_btn.config(state="disabled")
        self._log(f"ERROR: {ex}")
        messagebox.showerror("Error", str(ex))
        self.file_label.config(text="")
        self._set_options_enabled(True)

    # ---------------- Helpers ----------------
    def _build_settings_from_ui(self) -> tuple[OptimizeSettings, list[Path]]:
        inp = Path(self.input_dir.get()).expanduser()
        out = Path(self.output_dir.get()).expanduser()

        if not inp.exists() or not inp.is_dir():
            raise ValueError("Input folder does not exist.")
        if inp.resolve() == out.resolve():
            raise ValueError("Output folder cannot be the same as input folder.")

        # Parse ints safely
        max_w = self._parse_optional_int(self.max_width.get())
        max_h = self._parse_optional_int(self.max_height.get())

        jpeg_q = self._parse_int_range(self.jpeg_quality.get(), 1, 100, "JPEG quality")
        webp_q = self._parse_int_range(self.webp_quality.get(), 1, 100, "WebP quality")

        crop = self._parse_ratio_or_none(self.crop_ratio.get())

        fmt = self.output_format.get().strip().lower()
        if fmt not in {"keep", "jpeg", "png", "webp"}:
            raise ValueError("Invalid output format.")

        s = OptimizeSettings(
            output_dir=out,
            output_format=fmt,  # "keep"|"jpeg"|"png"|"webp"
            overwrite=False,
            only_if_smaller=bool(self.only_if_smaller.get()),
            write_even_if_bigger_when_stripping_metadata=bool(self.allow_bigger_for_metadata.get()),
            suffix=self.suffix.get().strip() or "_optimized",
            skip_existing_suffix=not bool(self.allow_reprocess.get()),
            strip_metadata=bool(self.strip_metadata.get()),
            auto_orient=True,
            max_width=max_w,
            max_height=max_h,
            crop_ratio=crop,
            jpeg_quality=jpeg_q,
            webp_quality=webp_q,
            webp_lossless=bool(self.webp_lossless.get()),
            dry_run=bool(self.dry_run.get()),
        )

        # Apply preset (optional)
        preset = self.preset.get().strip().lower()
        if preset and preset != "(none)":
            from .presets import apply_preset
            s = apply_preset(preset, s)

        return s, [inp]

    def _set_progress(self, current: int, total: int) -> None:
        # total can be 0 if folder has no supported files
        self.progress["maximum"] = max(total, 1)
        self.progress_var.set(min(current, max(total, 1)))
        self.progress_label.config(text=f"{current} / {total}")

    def _set_options_enabled(self, enabled: bool) -> None:
        for w in self._option_widgets:
            try:
                if not enabled:
                    # Disable everything uniformly
                    w.configure(state="disabled")
                else:
                    # Restore correct enabled state
                    if isinstance(w, ttk.Combobox):
                        w.configure(state="readonly")
                    else:
                        w.configure(state="normal")
            except Exception:
                # Ignore non-standard widgets safely
                pass

    def _parse_optional_int(self, text: str):
        t = text.strip()
        if not t:
            return None
        v = int(t)
        if v <= 0:
            raise ValueError("Resize values must be positive.")
        return v

    def _parse_int_range(self, text: str, lo: int, hi: int, label: str) -> int:
        t = text.strip()
        v = int(t)
        if not (lo <= v <= hi):
            raise ValueError(f"{label} must be between {lo} and {hi}.")
        return v

    def _parse_ratio_or_none(self, text: str):
        t = text.strip()
        if not t:
            return None
        if ":" in t:
            a, b = t.split(":", 1)
            num = float(a)
            den = float(b)
            if den == 0:
                raise ValueError("Crop ratio denominator cannot be 0.")
            return num / den
        return float(t)

    def _log(self, msg: str) -> None:
        self.status.insert("end", msg + "\n")
        self.status.see("end")
