"""
AI Worker with Local SQLite WAL

AI 추론 작업을 처리하는 Worker
- RabbitMQ에서 작업 수신
- 로컬 SQLite WAL에 먼저 기록
- AI 모델 추론 수행
- PostgreSQL에 결과 동기화
"""

import logging
import os
from typing import Any, Dict, List

from celery import Celery
from celery.signals import worker_ready, worker_shutdown

from app.wal import WALManager, WALRecovery
from workers.storage_worker import WALTask

# 로깅 설정
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

# Celery App 초기화
app = Celery("ai-worker")
app.config_from_object(
    {
        "broker_url": os.getenv("RABBITMQ_URL", "amqp://guest:guest@rabbitmq:5672//"),
        "result_backend": os.getenv("REDIS_URL", "redis://redis:6379/1"),
        "task_serializer": "json",
        "result_serializer": "json",
        "accept_content": ["json"],
        "timezone": "UTC",
        "enable_utc": True,
        "task_acks_late": True,
        "task_reject_on_worker_lost": True,
        "worker_prefetch_multiplier": 1,  # AI 작업은 무거우므로 1개씩
    }
)

# WAL Manager (Global)
wal_manager: WALManager = None


# Worker 시작 시 WAL 초기화
@worker_ready.connect
def on_worker_ready(sender, **kwargs):
    """Worker 시작 시 WAL 초기화 및 복구"""
    global wal_manager

    logger.info("Initializing AI Worker WAL Manager...")

    # WAL Manager 초기화
    db_path = os.getenv("WAL_DB_PATH", "/var/lib/growbin/wal/ai_worker.db")
    wal_manager = WALManager(db_path=db_path)

    # 통계
    stats = wal_manager.get_stats()
    logger.info(f"WAL Stats: {stats}")

    # 복구
    recovery = WALRecovery(wal_manager)
    pending_tasks = recovery.recover_pending_tasks()

    if pending_tasks:
        logger.warning(f"Recovered {len(pending_tasks)} pending tasks")

    logger.info("AI Worker WAL Manager initialized")


# Worker 종료 시 WAL 정리
@worker_shutdown.connect
def on_worker_shutdown(sender, **kwargs):
    """Worker 종료 시 WAL 정리"""
    global wal_manager

    if wal_manager:
        logger.info("Closing AI Worker WAL Manager...")
        wal_manager.checkpoint()
        stats = wal_manager.get_stats()
        logger.info(f"Final WAL Stats: {stats}")
        wal_manager.close()
        logger.info("AI Worker WAL Manager closed")


# 작업 정의
@app.task(base=WALTask, bind=True, max_retries=3)
def classify_waste_image(self, image_url: str, user_id: int) -> Dict[str, Any]:
    """
    폐기물 이미지 분류 (GPT-5 Vision)

    Args:
        image_url: 이미지 URL
        user_id: 사용자 ID

    Returns:
        분류 결과
    """
    import time

    try:
        logger.info(f"Classifying waste image: {image_url}")

        # GPT-5 Vision API 호출 (예시)
        # response = openai.ChatCompletion.create(
        #     model="gpt-5-vision",
        #     messages=[{
        #         "role": "user",
        #         "content": [
        #             {"type": "text", "text": "이 이미지의 폐기물 분류는?"},
        #             {"type": "image_url", "image_url": image_url}
        #         ]
        #     }]
        # )

        # 시뮬레이션
        time.sleep(3)  # AI 추론 시간

        result = {
            "status": "success",
            "image_url": image_url,
            "user_id": user_id,
            "classification": {
                "category": "plastic",
                "confidence": 0.95,
                "sub_category": "PET_bottle",
            },
            "disposal_method": "플라스틱 전용 수거함에 배출",
            "processed_at": time.time(),
        }

        logger.info(f"Classification completed: {result['classification']}")
        return result

    except Exception as e:
        logger.error(f"Classification failed: {e}")
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@app.task(base=WALTask, bind=True, max_retries=3)
def chat_with_llm(self, message: str, user_id: int, context: List[Dict]) -> Dict[str, Any]:
    """
    LLM 챗봇 응답 생성 (GPT-4o mini)

    Args:
        message: 사용자 메시지
        user_id: 사용자 ID
        context: 대화 컨텍스트

    Returns:
        LLM 응답
    """
    import time

    try:
        logger.info(f"Generating LLM response for user {user_id}")

        # GPT-4o mini API 호출 (예시)
        # response = openai.ChatCompletion.create(
        #     model="gpt-4o-mini",
        #     messages=context + [{"role": "user", "content": message}]
        # )

        # 시뮬레이션
        time.sleep(1)

        result = {
            "status": "success",
            "user_id": user_id,
            "message": message,
            "response": "안녕하세요! 폐기물 분류에 대해 도와드리겠습니다.",
            "processed_at": time.time(),
        }

        logger.info("LLM response generated")
        return result

    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        raise self.retry(exc=e, countdown=30 * (2 ** self.request.retries))


@app.task(base=WALTask, bind=True)
def extract_text_from_image(self, image_url: str) -> Dict[str, Any]:
    """
    이미지에서 텍스트 추출 (OCR)

    Args:
        image_url: 이미지 URL

    Returns:
        추출된 텍스트
    """
    import time

    logger.info(f"Extracting text from image: {image_url}")

    # OCR 로직
    time.sleep(2)

    result = {
        "status": "success",
        "image_url": image_url,
        "extracted_text": "재활용 가능",
        "confidence": 0.92,
        "processed_at": time.time(),
    }

    logger.info("Text extraction completed")
    return result


@app.task
def periodic_ai_metrics():
    """주기적 AI 메트릭 수집 (Prometheus)"""
    if wal_manager:
        stats = wal_manager.get_stats()

        # Prometheus 메트릭 업데이트 (예시)
        # ai_worker_tasks_total.labels(status='pending').set(stats['by_status'].get('PENDING', 0))
        # ai_worker_tasks_total.labels(status='running').set(stats['by_status'].get('RUNNING', 0))
        # ai_worker_tasks_total.labels(status='success').set(stats['by_status'].get('SUCCESS', 0))

        logger.debug(f"AI Worker metrics updated: {stats}")


# Celery Beat 스케줄
app.conf.beat_schedule = {
    "ai-metrics-every-30s": {
        "task": "workers.ai_worker.periodic_ai_metrics",
        "schedule": 30.0,
    },
}

