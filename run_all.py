"""Run a flat, offline replication workflow without writing into the input directory.

Snapshot mode regenerates article assets from the included derived data. Full mode
stages external inputs, estimates returns, verifies archived results, and regenerates
article assets. Only explicitly listed outputs leave the temporary workspace.
"""

from pathlib import Path
import argparse
import hashlib
import json
import os
import shutil
import subprocess
import sys
import tempfile
import time

ROOT = Path(__file__).resolve().parent
ASSETS = [
    "price_table.tex",
    "sensitivity_table.tex",
    "content_combinations.tex",
    "role_table.tex",
    "history_cases.tex",
    "date_diagnostics.tex",
    "information_system.pdf",
    "matched_differences.pdf",
    "event_level_matching.csv",
    "date_level_diagnostics.csv",
]
SNAPSHOTS = ["article_data.json", "content_evidence.json", "historical_evidence.json"]


def run_script(work, name, environment):
    """Execute one stage and preserve its complete output in a separate log."""
    print(f"Running {name}", flush=True)
    log_path = work / ("result_" + Path(name).stem + "_run.log")
    with log_path.open("w", encoding="utf-8") as log:
        process = subprocess.run(
            [sys.executable, str(work / name)],
            cwd=work,
            env=environment,
            stdout=log,
            stderr=subprocess.STDOUT,
        )
    if process.returncode:
        print(log_path.read_text(encoding="utf-8")[-10000:], file=sys.stderr)
        raise RuntimeError(f"{name} failed with exit code {process.returncode}")


def main():
    """Validate inputs, run the selected workflow and export a flat output directory."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=["snapshot", "full"], default="snapshot")
    parser.add_argument(
        "--data-dir", type=Path, help="External flat input directory for full mode"
    )
    parser.add_argument(
        "--output-dir", type=Path, required=True, help="New, empty output directory"
    )
    args = parser.parse_args()
    output = args.output_dir.expanduser().resolve()
    # Keep full outputs and external records outside the public checkout.
    if output == ROOT or ROOT in output.parents:
        parser.error("--output-dir must be outside the repository")
    if output.exists() and any(output.iterdir()):
        parser.error(
            "--output-dir must be empty; existing results are never overwritten"
        )
    manifest = json.loads((ROOT / "external_inputs_manifest.json").read_text())
    if args.mode == "full":
        if args.data_dir is None:
            parser.error("full mode requires --data-dir; raw inputs are not bundled")
        source = args.data_dir.expanduser().resolve()
        if source == output:
            parser.error("input and output directories must differ")
        for item in manifest:
            path = source / item["name"]
            if not path.is_file():
                parser.error(f'Missing external input: {item["name"]}')
            if hashlib.sha256(path.read_bytes()).hexdigest() != item["sha256"]:
                parser.error(f'Input differs from the frozen release: {item["name"]}')
    output.mkdir(parents=True, exist_ok=True)
    start = time.monotonic()
    with tempfile.TemporaryDirectory(prefix="disclosure-replication-") as directory:
        work = Path(directory)
        for path in ROOT.glob("*.py"):
            shutil.copy2(path, work / path.name)
        for name in SNAPSHOTS:
            shutil.copy2(ROOT / name, work / name)
        environment = dict(os.environ)
        # Avoid inheriting a stale data directory or oversubscribing BLAS threads.
        environment.pop("DISCLOSURE_INPUT_DIR", None)
        environment.update(
            OPENBLAS_NUM_THREADS="1", OMP_NUM_THREADS="1", MKL_NUM_THREADS="1"
        )
        try:
            if args.mode == "full":
                # Input links are only read. All new results have different filenames.
                for item in manifest:
                    (work / item["name"]).symlink_to(source / item["name"])
                for name in [
                    "content_tables.py",
                    "main_analysis.py",
                    "supplementary_analysis.py",
                    "verify_outputs.py",
                    "verify_event_records.py",
                    "revision_audit.py",
                ]:
                    run_script(work, name, environment)
                audit = json.loads((work / "result_revision_audit.json").read_text())
                comparisons = json.loads(
                    (work / "result_supplementary.json").read_text()
                )
                article = dict(
                    source_directory="Full replication workspace",
                    source_files=[
                        "result_revision_audit.json",
                        "result_supplementary.json",
                    ],
                    core=audit["core"],
                    comparisons=comparisons,
                    event_rows=audit["match_rows"],
                )
                (work / "article_data.json").write_text(
                    json.dumps(article, indent=2) + "\n"
                )
                environment["DISCLOSURE_INPUT_DIR"] = str(work)
            for name in [
                "prepare_content_evidence.py",
                "verify_snapshot.py",
                "prepare_assets.py",
                "prepare_detail_tables.py",
            ]:
                run_script(work, name, environment)
            for name in ASSETS + SNAPSHOTS:
                shutil.copy2(work / name, output / name)
            for path in work.glob("result_*"):
                if path.is_file() and not path.is_symlink():
                    shutil.copy2(path, output / path.name)
            report = dict(
                mode=args.mode,
                passed=True,
                elapsed_seconds=round(time.monotonic() - start, 2),
                full_input_hashes_verified=args.mode == "full",
                human_coding_validation=False,
                note="Snapshot checks do not re-estimate returns or validate source coding.",
            )
            (output / "replication_report.json").write_text(
                json.dumps(report, indent=2) + "\n"
            )
        except Exception:
            for path in work.glob("*.log"):
                shutil.copy2(path, output / path.name)
            raise
    print(f"{args.mode.capitalize()} replication passed. Outputs: {output}")


if __name__ == "__main__":
    main()
