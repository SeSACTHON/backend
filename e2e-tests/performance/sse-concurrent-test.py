#!/usr/bin/env python3
"""
SSE 동시접속 부하테스트

Usage:
    pip install aiohttp
    python tests/performance/sse-concurrent-test.py --vus 50 --token "eyJ..."
"""

import argparse
import asyncio
import json
import time
from dataclasses import dataclass, field
from typing import Optional

import aiohttp


@dataclass
class SSEMetrics:
    """SSE 테스트 메트릭"""
    connections_opened: int = 0
    connections_closed: int = 0
    connections_failed: int = 0
    events_received: int = 0
    done_received: int = 0
    rewards_received: int = 0
    stages: dict = field(default_factory=lambda: {
        "vision": 0, "rule": 0, "answer": 0, "reward": 0, "done": 0
    })
    latencies: list = field(default_factory=list)
    errors: list = field(default_factory=list)

    def print_summary(self, duration: float):
        print("\n" + "=" * 70)
        print("                    SSE CONCURRENT TEST RESULTS")
        print("=" * 70)
        print(f"\n  Duration        : {duration:.1f}s")
        print(f"  Connections     : {self.connections_opened} opened / {self.connections_closed} closed / {self.connections_failed} failed")
        print(f"  Success Rate    : {(self.done_received / max(self.connections_opened, 1) * 100):.1f}%")
        print(f"\n  Events Received : {self.events_received}")
        print(f"  Done Events     : {self.done_received}")
        print(f"  Rewards         : {self.rewards_received}")

        print(f"\n  Stages:")
        for stage, count in self.stages.items():
            print(f"    {stage:10} : {count}")

        if self.latencies:
            sorted_lat = sorted(self.latencies)
            p50 = sorted_lat[len(sorted_lat) // 2]
            p95 = sorted_lat[int(len(sorted_lat) * 0.95)]
            avg = sum(self.latencies) / len(self.latencies)
            print(f"\n  Time to Done:")
            print(f"    avg : {avg/1000:.2f}s")
            print(f"    p50 : {p50/1000:.2f}s")
            print(f"    p95 : {p95/1000:.2f}s")
            print(f"    min : {min(self.latencies)/1000:.2f}s")
            print(f"    max : {max(self.latencies)/1000:.2f}s")

        if self.errors:
            print(f"\n  Errors ({len(self.errors)}):")
            for err in self.errors[:5]:
                print(f"    - {err}")
            if len(self.errors) > 5:
                print(f"    ... and {len(self.errors) - 5} more")

        print("\n" + "=" * 70)


async def submit_scan(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    image_url: str
) -> Optional[str]:
    """POST /api/v1/scan → job_id 반환"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
    }
    try:
        async with session.post(
            f"{base_url}/api/v1/scan",
            headers=headers,
            json={"image_url": image_url},
            timeout=aiohttp.ClientTimeout(total=30)
        ) as resp:
            if resp.status == 200:
                data = await resp.json()
                return data.get("job_id")
            else:
                return None
    except Exception as e:
        return None


async def subscribe_sse(
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    job_id: str,
    metrics: SSEMetrics,
    vu_id: int
) -> None:
    """SSE 스트림 구독"""
    headers = {
        "Authorization": f"Bearer {token}",
        "Accept": "text/event-stream",
    }

    start_time = time.time() * 1000
    metrics.connections_opened += 1

    try:
        async with session.get(
            f"{base_url}/api/v1/stream?job_id={job_id}",
            headers=headers,
            timeout=aiohttp.ClientTimeout(total=120)
        ) as resp:
            if resp.status != 200:
                metrics.connections_failed += 1
                metrics.errors.append(f"VU{vu_id}: HTTP {resp.status}")
                return

            async for line in resp.content:
                line = line.decode("utf-8").strip()

                if line.startswith("data:"):
                    try:
                        data = json.loads(line[5:].strip())
                        stage = data.get("stage", "unknown")
                        metrics.events_received += 1

                        if stage in metrics.stages:
                            metrics.stages[stage] += 1

                        if stage == "done":
                            metrics.done_received += 1
                            elapsed = time.time() * 1000 - start_time
                            metrics.latencies.append(elapsed)

                            # reward 체크
                            result = data.get("result", {})
                            if isinstance(result, dict) and result.get("reward"):
                                metrics.rewards_received += 1

                            break

                        if stage == "reward":
                            result = data.get("result", {})
                            if isinstance(result, dict) and result.get("reward"):
                                metrics.rewards_received += 1

                    except json.JSONDecodeError:
                        pass

            metrics.connections_closed += 1

    except asyncio.TimeoutError:
        metrics.connections_failed += 1
        metrics.errors.append(f"VU{vu_id}: Timeout")
    except Exception as e:
        metrics.connections_failed += 1
        metrics.errors.append(f"VU{vu_id}: {type(e).__name__}: {str(e)[:50]}")


async def run_vu(
    vu_id: int,
    session: aiohttp.ClientSession,
    base_url: str,
    token: str,
    image_url: str,
    metrics: SSEMetrics
) -> None:
    """단일 VU 실행: POST → SSE 구독"""
    # 1. POST scan
    job_id = await submit_scan(session, base_url, token, image_url)
    if not job_id:
        metrics.connections_failed += 1
        metrics.errors.append(f"VU{vu_id}: Failed to submit scan")
        return

    print(f"  [VU {vu_id:3}] job_id: {job_id[:8]}... SSE 연결 중...")

    # 2. SSE 구독
    await subscribe_sse(session, base_url, token, job_id, metrics, vu_id)


async def main():
    parser = argparse.ArgumentParser(description="SSE Concurrent Load Test")
    parser.add_argument("--vus", type=int, default=10, help="Number of virtual users")
    parser.add_argument("--token", type=str, required=True, help="JWT token")
    parser.add_argument("--base-url", type=str, default="https://api.dev.growbin.app")
    parser.add_argument("--image-url", type=str,
                        default="https://images.dev.growbin.app/scan/e09725344fc2418a88f293b0f20db173.png")
    parser.add_argument("--ramp-up", type=float, default=0.1, help="Delay between VU starts (seconds)")
    args = parser.parse_args()

    print("=" * 70)
    print("                    SSE CONCURRENT LOAD TEST")
    print("=" * 70)
    print(f"\n  VUs         : {args.vus}")
    print(f"  Base URL    : {args.base_url}")
    print(f"  Ramp-up     : {args.ramp_up}s per VU")
    print(f"\n  Starting...\n")

    metrics = SSEMetrics()
    start_time = time.time()

    connector = aiohttp.TCPConnector(limit=args.vus + 50, limit_per_host=args.vus + 50)
    async with aiohttp.ClientSession(connector=connector) as session:
        tasks = []
        for i in range(args.vus):
            task = asyncio.create_task(
                run_vu(i + 1, session, args.base_url, args.token, args.image_url, metrics)
            )
            tasks.append(task)
            if args.ramp_up > 0:
                await asyncio.sleep(args.ramp_up)

        await asyncio.gather(*tasks, return_exceptions=True)

    duration = time.time() - start_time
    metrics.print_summary(duration)


if __name__ == "__main__":
    asyncio.run(main())
