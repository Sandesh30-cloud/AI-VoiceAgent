from __future__ import annotations

import argparse
import logging
import traceback
import uuid

from dotenv import load_dotenv

load_dotenv()

from videosdk.agents import AgentSession, JobContext, Options, RoomOptions, WorkerJob

from agent.pipeline import attach_observability, create_pipeline
from agent.receptionist import ReceptionistAgent, bind_session
from config import get_settings
from services.call_state import CallState
from services.db import init_db
from services.logging_setup import configure_logging
from services.metrics import CallMetrics

logger = logging.getLogger(__name__)


def make_context() -> JobContext:
    settings = get_settings()
    room_options = RoomOptions(
        name=f"{settings.owner_name} AI Receptionist",
        playground=settings.playground,
    )
    return JobContext(room_options=room_options)


async def start_session(context: JobContext) -> None:
    settings = get_settings()
    call_id = str(uuid.uuid4())
    state = CallState(call_id=call_id)
    metrics = CallMetrics(call_id=call_id)
    pipeline = create_pipeline(settings)
    agent = ReceptionistAgent(
        settings=settings,
        state=state,
        metrics=metrics,
        ctx=context,
    )
    attach_observability(pipeline, metrics, on_provider_error=agent.mark_provider_error)
    session = AgentSession(
        agent=agent,
        pipeline=pipeline,
        wake_up=settings.wake_up_seconds,
    )
    bind_session(agent, session)
    await session.start(wait_for_participant=True, run_until_shutdown=True)


def run_worker() -> None:
    settings = get_settings()
    init_db(settings.sqlite_path)
    if settings.pipeline_mode == "cascade":
        from videosdk.agents.plugins import pre_download_model

        pre_download_model()
    options = Options(
        agent_id=settings.agent_id,
        register=True,
        max_processes=settings.max_processes,
        host=settings.worker_host,
        port=settings.worker_port,
    )
    job = WorkerJob(entrypoint=start_session, jobctx=make_context, options=options)
    job.start()


def run_webhook() -> None:
    import uvicorn

    from webhook import app

    settings = get_settings()
    uvicorn.run(app, host=settings.webhook_host, port=settings.webhook_port)


def main() -> None:
    parser = argparse.ArgumentParser(description="Sandesh missed-call AI receptionist")
    parser.add_argument(
        "mode",
        nargs="?",
        default="worker",
        choices=["worker", "webhook", "console"],
        help="worker (default, SIP), webhook (FastAPI SIP events), or pass through console",
    )
    args, rest = parser.parse_known_args()
    settings = get_settings()
    configure_logging(settings.log_level)

    if args.mode == "webhook":
        run_webhook()
        return

    # VideoSDK console mode: `python main.py console`
    if args.mode == "console":
        import sys

        sys.argv = [sys.argv[0], "console", *rest]
    try:
        run_worker()
    except Exception:
        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
