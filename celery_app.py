import os
from celery import Celery

REDIS_URL = os.environ.get("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "afs",
    broker=REDIS_URL,
    backend=REDIS_URL,
    include=["tasks"],
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    timezone="Asia/Bangkok",
    enable_utc=True,
    worker_prefetch_multiplier=1,   # ให้แต่ละ worker รับงานทีละ 1 task เพื่อกระจายงานเท่ากัน
    task_acks_late=True,            # ยืนยัน task หลังทำงานเสร็จ ป้องกันข้อมูลหาย
    task_reject_on_worker_lost=True,
)
