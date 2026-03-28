import logging
import re
from typing import Optional

from control_header import AllowedAction, PipelineStage
from orchestrator import Capability
from .base import BaseSpecialist, SpecialistContext, SpecialistResult
from .consent_manager import ConsentManager
from .registry import SpecialistRegistry

logger = logging.getLogger(__name__)

INVOKE_TAG_PATTERN = re.compile(r"\[INVOKE:(\w+)\]", re.IGNORECASE)


class SpecialistRouter:
    def __init__(
        self, registry: SpecialistRegistry, consent_manager: ConsentManager
    ) -> None:
        self.registry = registry
        self.consent = consent_manager

    async def maybe_route(
        self,
        answer: str,
        session_id: str,
        batch_id: Optional[str],
        document_context: Optional[dict],
        capabilities_granted: set[Capability],
        control_stage: PipelineStage,
        control_allowed_actions: set[AllowedAction],
    ) -> Optional[SpecialistResult]:
        match = INVOKE_TAG_PATTERN.search(answer)
        if not match:
            return None
        specialist_name = match.group(1).lower()

        if control_stage != PipelineStage.READY:
            logger.warning("Router blocked: stage=%s (not READY)", control_stage.value)
            return None
        if AllowedAction.INVOKE_SPECIALIST not in control_allowed_actions:
            logger.warning("Router blocked: invoke_specialist not in allowed_actions")
            return None

        if specialist_name not in self.registry:
            logger.warning("Router blocked: unknown specialist %s", specialist_name)
            return None
        specialist = self.registry.get(specialist_name)

        for cap in specialist.required_capabilities:
            if cap not in capabilities_granted and not self.consent.has_capability(
                session_id, cap
            ):
                logger.warning("Router blocked: missing capability %s", cap.value)
                return None

        if batch_id and not self.consent.has_invocation_approval(
            session_id, batch_id, specialist_name
        ):
            logger.warning(
                "Router blocked: no invocation approval for %s/%s",
                batch_id,
                specialist_name,
            )
            return None

        logger.info("Routing to specialist: %s", specialist_name)
        ctx = SpecialistContext(
            session_id=session_id,
            batch_id=batch_id,
            document_context=document_context,
            capabilities_granted=capabilities_granted,
        )
        return await specialist.invoke(ctx)
