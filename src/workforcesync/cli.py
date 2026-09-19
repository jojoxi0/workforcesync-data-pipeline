import argparse
import json
import sys

from workforcesync.config import Settings
from workforcesync.database import connect
from workforcesync.source import seed


def main():
    parser = argparse.ArgumentParser(description="Workforce source and pipeline operations")
    commands = parser.add_subparsers(dest="command", required=True)
    seed_command = commands.add_parser("seed")
    seed_command.add_argument("--scenario", choices=["initial", "incremental"], default="initial")
    run = commands.add_parser("pipeline")
    run.add_argument("--full", action="store_true", help="Replay all current source records")
    run.add_argument("--fail-at", choices=["extraction", "validation", "load"])
    run.add_argument("--direct", action="store_true", help="Run without Prefect orchestration")
    commands.add_parser("status")
    args = parser.parse_args()
    try:
        config = Settings()
        if args.command == "seed":
            applied = seed(config, args.scenario)
            print(json.dumps({"scenario": args.scenario, "applied": applied}))
        elif args.command == "pipeline":
            if args.direct:
                from workforcesync.pipeline import run_pipeline

                result = run_pipeline(config, args.full, fail_at=args.fail_at)
            else:
                from orchestration.flows import workforce_daily_sync

                result = workforce_daily_sync(args.full, args.fail_at)
            print(json.dumps(result, default=str, indent=2))
        else:
            with connect(config) as db:
                runs = db.execute("""SELECT * FROM audit.pipeline_run
                    ORDER BY started_at DESC LIMIT 10""").fetchall()
                watermarks = db.execute("SELECT * FROM audit.pipeline_watermark").fetchall()
            print(json.dumps({"runs": runs, "watermarks": watermarks}, default=str, indent=2))
    except Exception as error:
        # Third-party exceptions may contain credentials or response bodies.
        print(
            f"Command failed: {type(error).__name__}. See structured pipeline logs.",
            file=sys.stderr,
        )
        raise SystemExit(1) from None


if __name__ == "__main__":
    main()
