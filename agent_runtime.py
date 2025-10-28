import os
import asyncio
import logging
from typing import Any, Optional

from src.eqv_agent import ExamQuestionVerificationAgent


# ---------------------------
# Logging
# ---------------------------
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)

ENV_PATH = os.path.join(os.path.dirname(__file__), ".env")
if os.path.exists(ENV_PATH):
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH)

async def run_agent(agent: ExamQuestionVerificationAgent):
    try:
        await agent.connect("session_id1", "user_id1")
        await agent.deploy()
    except Exception as e:
        logger.error(f"Agent deployment failed: {e}")
        raise e
    except KeyboardInterrupt as e:
        logger.info(f"Agent deployment interrupted by user.")
    finally:
        logger.info("Cleaning up and closing agent...")
        await agent.close()
        logger.info("Agent deployment finished.")

if __name__ == "__main__":
    agent  = ExamQuestionVerificationAgent()
    asyncio.run(run_agent(agent))

