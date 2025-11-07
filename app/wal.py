"""
Worker Local SQLite WAL Manager

Robin 패턴을 적용한 Worker 로컬 WAL 구현
- 작업 수신 시 로컬 SQLite에 먼저 기록 (WAL)
- 작업 완료 후 PostgreSQL 동기화
- 장애 복구 기능 제공
"""

import json
import logging
import sqlite3
import time
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)


class WALManager:
    """Worker 로컬 SQLite WAL 매니저"""

    def __init__(self, db_path: str = "/var/lib/ecoeco/wal/task_queue.db"):
        """
        WAL Manager 초기화

        Args:
            db_path: SQLite DB 파일 경로 (PVC 마운트 위치)
        """
        self.db_path = db_path
        self._ensure_db_directory()
        self.conn = self._init_connection()
        self._init_wal_mode()
        self._create_tables()

    def _ensure_db_directory(self):
        """DB 디렉토리 생성"""
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)
        logger.info(f"WAL directory ensured: {db_dir}")

    def _init_connection(self) -> sqlite3.Connection:
        """SQLite 연결 초기화"""
        conn = sqlite3.connect(
            self.db_path,
            isolation_level=None,  # Autocommit for WAL
            check_same_thread=False,
        )
        conn.row_factory = sqlite3.Row  # Dict-like access
        logger.info(f"SQLite connection established: {self.db_path}")
        return conn

    def _init_wal_mode(self):
        """WAL 모드 활성화 및 최적화"""
        # WAL 모드 활성화
        result = self.conn.execute("PRAGMA journal_mode=WAL").fetchone()
        logger.info(f"WAL mode: {result[0]}")

        # WAL 최적화 설정
        self.conn.execute("PRAGMA synchronous=NORMAL")  # 성능 개선
        self.conn.execute("PRAGMA wal_autocheckpoint=1000")  # 1000 페이지마다 체크포인트
        self.conn.execute("PRAGMA cache_size=-64000")  # 64MB 캐시
        self.conn.execute("PRAGMA temp_store=MEMORY")  # 임시 저장소 메모리 사용

        logger.info("WAL optimizations applied")

    def _create_tables(self):
        """테이블 생성"""
        # Task WAL 테이블
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS task_wal (
                task_id TEXT PRIMARY KEY,
                task_name TEXT NOT NULL,
                worker_name TEXT NOT NULL,
                args TEXT,
                kwargs TEXT,
                status TEXT NOT NULL DEFAULT 'PENDING',
                result TEXT,
                error TEXT,
                retry_count INTEGER DEFAULT 0,
                created_at TEXT NOT NULL,
                started_at TEXT,
                completed_at TEXT,
                synced_to_postgres INTEGER DEFAULT 0
            )
        """
        )

        # 복구용 체크포인트 테이블
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS wal_checkpoint (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                checkpoint_time TEXT NOT NULL,
                tasks_synced INTEGER NOT NULL,
                tasks_pending INTEGER NOT NULL
            )
        """
        )

        # 인덱스 생성
        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_status_synced
            ON task_wal(status, synced_to_postgres)
        """
        )

        self.conn.execute(
            """
            CREATE INDEX IF NOT EXISTS idx_created_at
            ON task_wal(created_at)
        """
        )

        logger.info("WAL tables created")

    @contextmanager
    def transaction(self):
        """트랜잭션 컨텍스트 매니저"""
        try:
            self.conn.execute("BEGIN")
            yield
            self.conn.execute("COMMIT")
        except Exception as e:
            self.conn.execute("ROLLBACK")
            logger.error(f"Transaction rolled back: {e}")
            raise

    def write_task(
        self, task_id: str, task_name: str, worker_name: str, args: tuple, kwargs: dict
    ) -> bool:
        """
        작업 수신 시 WAL에 기록

        Args:
            task_id: Celery Task ID
            task_name: Task 이름
            worker_name: Worker 이름
            args: Positional arguments
            kwargs: Keyword arguments

        Returns:
            성공 여부
        """
        try:
            self.conn.execute(
                """
                INSERT INTO task_wal
                (task_id, task_name, worker_name, args, kwargs, status, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
                (
                    task_id,
                    task_name,
                    worker_name,
                    json.dumps(args),
                    json.dumps(kwargs),
                    "PENDING",
                    datetime.utcnow().isoformat(),
                ),
            )
            logger.debug(f"Task written to WAL: {task_id}")
            return True
        except sqlite3.IntegrityError:
            logger.warning(f"Task already exists in WAL: {task_id}")
            return False
        except Exception as e:
            logger.error(f"Failed to write task to WAL: {e}")
            return False

    def start_task(self, task_id: str) -> bool:
        """
        작업 시작 시 상태 업데이트

        Args:
            task_id: Task ID

        Returns:
            성공 여부
        """
        try:
            self.conn.execute(
                """
                UPDATE task_wal
                SET status = ?, started_at = ?
                WHERE task_id = ?
            """,
                ("RUNNING", datetime.utcnow().isoformat(), task_id),
            )
            logger.debug(f"Task started: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to start task: {e}")
            return False

    def complete_task(self, task_id: str, result: Any) -> bool:
        """
        작업 완료 시 상태 및 결과 업데이트

        Args:
            task_id: Task ID
            result: 작업 결과

        Returns:
            성공 여부
        """
        try:
            self.conn.execute(
                """
                UPDATE task_wal
                SET status = ?, result = ?, completed_at = ?
                WHERE task_id = ?
            """,
                ("SUCCESS", json.dumps(result), datetime.utcnow().isoformat(), task_id),
            )
            logger.debug(f"Task completed: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to complete task: {e}")
            return False

    def fail_task(self, task_id: str, error: str, retry_count: int = 0) -> bool:
        """
        작업 실패 시 상태 및 에러 업데이트

        Args:
            task_id: Task ID
            error: 에러 메시지
            retry_count: 재시도 횟수

        Returns:
            성공 여부
        """
        try:
            self.conn.execute(
                """
                UPDATE task_wal
                SET status = ?, error = ?, retry_count = ?, completed_at = ?
                WHERE task_id = ?
            """,
                ("FAILURE", error, retry_count, datetime.utcnow().isoformat(), task_id),
            )
            logger.debug(f"Task failed: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to fail task: {e}")
            return False

    def mark_synced(self, task_id: str) -> bool:
        """
        PostgreSQL 동기화 완료 표시

        Args:
            task_id: Task ID

        Returns:
            성공 여부
        """
        try:
            self.conn.execute(
                """
                UPDATE task_wal
                SET synced_to_postgres = 1
                WHERE task_id = ?
            """,
                (task_id,),
            )
            logger.debug(f"Task marked as synced: {task_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to mark task as synced: {e}")
            return False

    def get_unsynced_tasks(self, limit: int = 100) -> List[Dict]:
        """
        PostgreSQL로 동기화되지 않은 작업 조회

        Args:
            limit: 최대 조회 개수

        Returns:
            미동기화 작업 리스트
        """
        try:
            cursor = self.conn.execute(
                """
                SELECT * FROM task_wal
                WHERE synced_to_postgres = 0
                AND status IN ('SUCCESS', 'FAILURE')
                ORDER BY completed_at ASC
                LIMIT ?
            """,
                (limit,),
            )
            tasks = [dict(row) for row in cursor.fetchall()]
            logger.debug(f"Found {len(tasks)} unsynced tasks")
            return tasks
        except Exception as e:
            logger.error(f"Failed to get unsynced tasks: {e}")
            return []

    def get_pending_tasks(self) -> List[Dict]:
        """
        복구를 위한 PENDING/RUNNING 작업 조회

        Returns:
            PENDING/RUNNING 작업 리스트
        """
        try:
            cursor = self.conn.execute(
                """
                SELECT * FROM task_wal
                WHERE status IN ('PENDING', 'RUNNING')
                ORDER BY created_at ASC
            """
            )
            tasks = [dict(row) for row in cursor.fetchall()]
            logger.info(f"Found {len(tasks)} pending/running tasks")
            return tasks
        except Exception as e:
            logger.error(f"Failed to get pending tasks: {e}")
            return []

    def checkpoint(self) -> bool:
        """
        체크포인트 생성 (현재 상태 저장)

        Returns:
            성공 여부
        """
        try:
            # 동기화된 작업 수
            synced = self.conn.execute(
                "SELECT COUNT(*) FROM task_wal WHERE synced_to_postgres = 1"
            ).fetchone()[0]

            # 미동기화 작업 수
            pending = self.conn.execute(
                "SELECT COUNT(*) FROM task_wal WHERE synced_to_postgres = 0"
            ).fetchone()[0]

            # 체크포인트 기록
            self.conn.execute(
                """
                INSERT INTO wal_checkpoint
                (checkpoint_time, tasks_synced, tasks_pending)
                VALUES (?, ?, ?)
            """,
                (datetime.utcnow().isoformat(), synced, pending),
            )

            # WAL 체크포인트 강제 실행
            self.conn.execute("PRAGMA wal_checkpoint(PASSIVE)")

            logger.info(f"Checkpoint created: {synced} synced, {pending} pending")
            return True
        except Exception as e:
            logger.error(f"Failed to create checkpoint: {e}")
            return False

    def cleanup_old_tasks(self, days: int = 7) -> int:
        """
        오래된 동기화 완료 작업 정리

        Args:
            days: 보관 일수

        Returns:
            삭제된 작업 수
        """
        try:
            cutoff_time = datetime.utcnow().timestamp() - (days * 24 * 3600)
            cutoff_iso = datetime.fromtimestamp(cutoff_time).isoformat()

            cursor = self.conn.execute(
                """
                DELETE FROM task_wal
                WHERE synced_to_postgres = 1
                AND completed_at < ?
            """,
                (cutoff_iso,),
            )

            deleted = cursor.rowcount
            logger.info(f"Cleaned up {deleted} old tasks (> {days} days)")

            # VACUUM (선택적)
            if deleted > 1000:
                self.conn.execute("VACUUM")
                logger.info("VACUUM executed")

            return deleted
        except Exception as e:
            logger.error(f"Failed to cleanup old tasks: {e}")
            return 0

    def get_stats(self) -> Dict[str, Any]:
        """
        WAL 통계 조회

        Returns:
            통계 딕셔너리
        """
        try:
            stats = {}

            # 상태별 작업 수
            cursor = self.conn.execute(
                "SELECT status, COUNT(*) as count FROM task_wal GROUP BY status"
            )
            stats["by_status"] = {row[0]: row[1] for row in cursor.fetchall()}

            # 동기화 통계
            cursor = self.conn.execute(
                """
                SELECT
                    COUNT(*) as total,
                    SUM(CASE WHEN synced_to_postgres = 1 THEN 1 ELSE 0 END) as synced,
                    SUM(CASE WHEN synced_to_postgres = 0 THEN 1 ELSE 0 END) as unsynced
                FROM task_wal
            """
            )
            row = cursor.fetchone()
            stats["sync"] = {"total": row[0], "synced": row[1], "unsynced": row[2]}

            # WAL 파일 크기
            wal_path = Path(self.db_path + "-wal")
            if wal_path.exists():
                stats["wal_size_mb"] = wal_path.stat().st_size / (1024 * 1024)
            else:
                stats["wal_size_mb"] = 0

            return stats
        except Exception as e:
            logger.error(f"Failed to get stats: {e}")
            return {}

    def close(self):
        """연결 종료"""
        if self.conn:
            self.checkpoint()  # 마지막 체크포인트
            self.conn.close()
            logger.info("WAL connection closed")


class WALRecovery:
    """WAL 복구 매니저"""

    def __init__(self, wal_manager: WALManager):
        self.wal = wal_manager

    def recover_pending_tasks(self) -> List[Dict]:
        """
        미완료 작업 복구

        Returns:
            복구된 작업 리스트
        """
        logger.info("Starting WAL recovery...")

        pending_tasks = self.wal.get_pending_tasks()

        if not pending_tasks:
            logger.info("No pending tasks to recover")
            return []

        logger.warning(f"Found {len(pending_tasks)} tasks to recover")

        # 복구 대상 작업 분석
        for task in pending_tasks:
            task_id = task["task_id"]
            status = task["status"]
            created_at = task["created_at"]

            # 시간 초과 확인 (1시간 이상 RUNNING 상태)
            created_time = datetime.fromisoformat(created_at)
            elapsed_seconds = (datetime.utcnow() - created_time).total_seconds()

            if status == "RUNNING" and elapsed_seconds > 3600:
                logger.warning(f"Task {task_id} stuck in RUNNING for {elapsed_seconds}s")
                # FAILURE로 변경
                self.wal.fail_task(task_id, "Task timeout during recovery", 0)

        return pending_tasks

    def force_sync_all(self, postgres_sync_func) -> int:
        """
        모든 미동기화 작업을 PostgreSQL에 동기화

        Args:
            postgres_sync_func: PostgreSQL 동기화 함수

        Returns:
            동기화된 작업 수
        """
        logger.info("Force syncing all unsynced tasks...")

        synced_count = 0
        batch_size = 100

        while True:
            tasks = self.wal.get_unsynced_tasks(limit=batch_size)
            if not tasks:
                break

            for task in tasks:
                try:
                    # PostgreSQL에 동기화
                    postgres_sync_func(task)

                    # 동기화 완료 표시
                    self.wal.mark_synced(task["task_id"])
                    synced_count += 1

                except Exception as e:
                    logger.error(f"Failed to sync task {task['task_id']}: {e}")

        logger.info(f"Force sync completed: {synced_count} tasks synced")
        return synced_count

