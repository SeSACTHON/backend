"""
Storage Worker with Local SQLite WAL

S3 업로드 작업을 처리하는 Worker
- RabbitMQ에서 작업 수신
- 로컬 SQLite WAL에 먼저 기록
- S3 업로드 수행
- PostgreSQL에 결과 동기화
"""

import logging
import os
from typing import Any, Dict

from celery import Celery, Task
from celery.signals import (
    task_failure,
    task_postrun,
    task_prerun,
    task_retry,
    worker_ready,
    worker_shutdown,
)

from app.wal import WALManager, WALRecovery

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Celery App 초기화
app = Celery("storage-worker")
app.config_from_object(
    {
        "broker_url": os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//"),
        "result_backend": os.getenv(
            "REDIS_URL", "redis://redis:6379/0"
        ),  # 임시 결과만 Redis
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "task_acks_late": True,  # WAL 기록 후 ACK
        "task_reject_on_worker_lost": True,  # Worker 장애 시 재처리
        "worker_prefetch_multiplier": 1,  # 한 번에 1개씩 처리
    }
)

# WAL Manager (Global)
wal_manager: WALManager = None


# Celery Task 베이스 클래스 (WAL 통합)
class WALTask(Task):
    """WAL을 적용한 Celery Task"""

    def before_start(self, task_id, args, kwargs):
        """작업 시작 전 WAL에 기록"""
        if wal_manager:
            wal_manager.write_task(
                task_id=task_id,
                task_name=self.name,
                worker_name="storage-worker",
                args=args,
                kwargs=kwargs,
            )

    def on_success(self, retval, task_id, args, kwargs):
        """작업 성공 시 WAL 업데이트"""
        if wal_manager:
            wal_manager.complete_task(task_id, retval)
            # PostgreSQL 동기화는 별도 백그라운드 작업에서 수행

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        """작업 실패 시 WAL 업데이트"""
        if wal_manager:
            wal_manager.fail_task(
                task_id, str(exc), self.request.retries if hasattr(self, "request") else 0
            )

    def on_retry(self, exc, task_id, args, kwargs, einfo):
        """재시도 시 WAL 업데이트"""
        if wal_manager:
            wal_manager.fail_task(
                task_id, str(exc), self.request.retries if hasattr(self, "request") else 0
            )


# Worker 시작 시 WAL 초기화 및 복구
@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Worker 시작 시 WAL 초기화 및 복구"""
    global wal_manager

    logger.info("Initializing WAL Manager...")

    # WAL Manager 초기화
    db_path = os.getenv("WAL_DB_PATH", "/var/lib/growbin/wal/storage_worker.db")
    wal_manager = WALManager(db_path=db_path)

    # 통계 출력
    stats = wal_manager.get_stats()
    logger.info(f"WAL Stats: {stats}")

    # 복구 수행
    recovery = WALRecovery(wal_manager)
    pending_tasks = recovery.recover_pending_tasks()

    if pending_tasks:
        logger.warning(f"Recovered {len(pending_tasks)} pending tasks")
        # 필요 시 재처리 로직 추가

    logger.info("WAL Manager initialized successfully")


# Worker 종료 시 WAL 정리
@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Worker 종료 시 WAL 정리"""
    global wal_manager

    if wal_manager:
        logger.info("Closing WAL Manager...")

        # 최종 체크포인트
        wal_manager.checkpoint()

        # 통계 출력
        stats = wal_manager.get_stats()
        logger.info(f"Final WAL Stats: {stats}")

        # 연결 종료
        wal_manager.close()

        logger.info("WAL Manager closed successfully")


# Task 시작 시 WAL 업데이트
@task_prerun.connect
def on_task_prerun(sender, task_id, task, args, kwargs, **extra):
    """Task 시작 시 WAL 상태 업데이트"""
    if wal_manager:
        wal_manager.start_task(task_id)
        logger.debug(f"Task {task_id} started")


# Task 완료 후 PostgreSQL 동기화 (비동기)
@task_postrun.connect
def on_task_postrun(sender, task_id, task, args, kwargs, retval, **extra):
    """Task 완료 후 비동기 PostgreSQL 동기화"""
    # 별도 백그라운드 작업으로 동기화
    # sync_to_postgres.apply_async((task_id,), countdown=5)
    pass


# 작업 정의
@app.task(base=WALTask, bind=True, max_retries=3)
def upload_to_s3(self, file_path: str, s3_key: str) -> Dict[str, Any]:
    """
    S3 업로드 작업

    Args:
        file_path: 업로드할 파일 경로
        s3_key: S3 키

    Returns:
        업로드 결과
    """
    import time

    try:
        logger.info(f"Uploading {file_path} to S3: {s3_key}")

        # S3 업로드 로직 (예시)
        # boto3.client('s3').upload_file(file_path, bucket, s3_key)

        # 시뮬레이션
        time.sleep(2)

        result = {
            "status": "success",
            "file_path": file_path,
            "s3_key": s3_key,
            "size_bytes": 12345,
            "uploaded_at": time.time(),
        }

        logger.info(f"Upload completed: {s3_key}")
        return result

    except Exception as e:
        logger.error(f"Upload failed: {e}")
        # 재시도
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@app.task(base=WALTask, bind=True)
def process_image(self, image_url: str, user_id: int) -> Dict[str, Any]:
    """
    이미지 처리 작업

    Args:
        image_url: 이미지 URL
        user_id: 사용자 ID

    Returns:
        처리 결과
    """
    import time

    logger.info(f"Processing image: {image_url} for user {user_id}")

    # 이미지 처리 로직
    time.sleep(1)

    result = {
        "status": "success",
        "image_url": image_url,
        "user_id": user_id,
        "processed_at": time.time(),
    }

    logger.info(f"Image processed: {image_url}")
    return result


@app.task(base=WALTask)
def sync_to_postgres(task_id: str) -> bool:
    """
    WAL에서 PostgreSQL로 결과 동기화

    Args:
        task_id: 동기화할 Task ID

    Returns:
        성공 여부
    """
    if not wal_manager:
        logger.error("WAL Manager not initialized")
        return False

    try:
        # WAL에서 작업 조회
        tasks = wal_manager.get_unsynced_tasks(limit=1)
        if not tasks:
            logger.debug(f"Task {task_id} already synced")
            return True

        task = tasks[0]

        # PostgreSQL에 저장 (예시)
        logger.info(f"Syncing task {task_id} to PostgreSQL")
        # db.execute("INSERT INTO task_results (...) VALUES (...)")

        # 동기화 완료 표시
        wal_manager.mark_synced(task_id)

        logger.info(f"Task {task_id} synced to PostgreSQL")
        return True

    except Exception as e:
        logger.error(f"Failed to sync task {task_id}: {e}")
        return False


@app.task
def periodic_wal_checkpoint():
    """주기적 WAL 체크포인트 (Celery Beat)"""
    if wal_manager:
        wal_manager.checkpoint()
        logger.info("Periodic WAL checkpoint completed")


@app.task
def periodic_wal_cleanup():
    """주기적 WAL 정리 (Celery Beat)"""
    if wal_manager:
        deleted = wal_manager.cleanup_old_tasks(days=7)
        logger.info(f"Periodic WAL cleanup: {deleted} tasks deleted")


# Celery Beat 스케줄 (주기적 작업)
app.conf.beat_schedule = {
    "wal-checkpoint-every-5min": {
        "task": "workers.storage_worker.periodic_wal_checkpoint",
        "schedule": 300.0,  # 5분마다
    },
    "wal-cleanup-daily": {
        "task": "workers.storage_worker.periodic_wal_cleanup",
        "schedule": 86400.0,  # 매일
    },
}

