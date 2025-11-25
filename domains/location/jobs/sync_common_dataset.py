from __future__ import annotations

import argparse
import asyncio
from pathlib import Path

from sqlalchemy.ext.asyncio import create_async_engine

from domains.location.jobs.build_common_dataset import (
    build_dataset,
    resolve_keco_csv,
    resolve_zero_waste_csv,
)
from domains.location.jobs.import_common_locations import (
    ensure_table,
    resolve_database_url,
    upsert_batch,
)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Build normalized dataset and import directly into Postgres",
        formatter_class=argparse.ArgumentDefaultsHelpFormatter,
    )
    parser.add_argument(
        "--keco-csv",
        type=Path,
        default=resolve_keco_csv(),
        help="Path to KECO recycle compensation CSV",
    )
    parser.add_argument(
        "--zero-waste-csv",
        type=Path,
        default=resolve_zero_waste_csv(),
        help="Path to zero-waste map CSV",
    )
    parser.add_argument(
        "--database-url",
        help="Override LOCATION_DATABASE_URL or DATABASE_URL env variables",
    )
    parser.add_argument(
        "--batch-size",
        type=int,
        default=500,
        help="Rows per insert batch",
    )
    return parser.parse_args()


async def sync_dataset(args: argparse.Namespace) -> int:
    dataset = build_dataset(args)
    if not dataset:
        print("No records found; skipping import.")
        return 0

    database_url = resolve_database_url(args.database_url)
    engine = create_async_engine(database_url, echo=False, pool_pre_ping=True)
    total = 0
    batch: list[dict[str, str]] = []

    try:
        await ensure_table(engine)
        for row in dataset:
            batch.append(row)
            if len(batch) >= args.batch_size:
                await upsert_batch(engine, batch)
                total += len(batch)
                batch.clear()
        if batch:
            await upsert_batch(engine, batch)
            total += len(batch)
    finally:
        await engine.dispose()

    return total


def main() -> None:
    args = parse_args()
    total_rows = asyncio.run(sync_dataset(args))
    print(
        f"Imported {total_rows} normalized rows directly from "
        f"{args.keco_csv.name} / {args.zero_waste_csv.name}"
    )


if __name__ == "__main__":
    main()
