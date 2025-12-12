import asyncio
import logging
import signal
from concurrent import futures

import grpc
import redis.asyncio as redis
from envoy.service.auth.v3 import external_auth_pb2_grpc

from domains.auth.core.config import get_settings
from domains.auth.rpc.servicer import AuthorizationServicer

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger("auth.rpc")


async def serve():
    settings = get_settings()

    # Initialize Redis connection for blacklist
    # Note: We use a separate Redis connection for gRPC to ensure isolation
    redis_client = redis.from_url(settings.redis_url, encoding="utf-8", decode_responses=True)

    server = grpc.aio.server(futures.ThreadPoolExecutor(max_workers=10))

    # Inject redis_client into Servicer
    external_auth_pb2_grpc.add_AuthorizationServicer_to_server(
        AuthorizationServicer(redis_client), server
    )

    listen_addr = "[::]:50051"
    server.add_insecure_port(listen_addr)
    logger.info(f"🚀 Starting Auth gRPC server on {listen_addr}")

    await server.start()

    # Graceful shutdown handler
    stop_event = asyncio.Event()

    def handle_signal(*args):
        logger.info("Received shutdown signal")
        stop_event.set()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        loop.add_signal_handler(sig, handle_signal)

    await stop_event.wait()
    logger.info("Stopping Auth gRPC server...")

    # Cleanup
    await redis_client.close()
    await server.stop(grace=5)
    logger.info("Auth gRPC server stopped.")


if __name__ == "__main__":
    asyncio.run(serve())
