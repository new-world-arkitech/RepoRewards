from __future__ import annotations

import logging
from typing import Dict, Any, Optional
from repo_investigator.bench_rotation.models import HealthScoreResult, SubstitutionEvent
from repo_investigator.config import get_settings, TelemetrySinkType

logger = logging.getLogger(__name__)

class TelemetryManager:
    """
    Production Telemetry & Observability Manager.
    Streams Zero-LLM Coach Telemetry, turn health scores, and bench substitutions
    to OpenTelemetry, Prometheus, or local structured logging.
    """

    def __init__(self, service_name: str = "flowmind"):
        self.service_name = service_name
        self.settings = get_settings()
        self._tracer = None
        self._init_opentelemetry()

    def _init_opentelemetry(self):
        if self.settings.telemetry_sink == TelemetrySinkType.OPENTELEMETRY:
            try:
                from opentelemetry import trace
                self._tracer = trace.get_tracer(self.service_name)
                logger.info("OpenTelemetry tracer initialized for %s", self.service_name)
            except ImportError:
                logger.warning("opentelemetry packages not installed; telemetry sink falling back to local.")
                self._tracer = None

    def record_turn_telemetry(
        self,
        workflow_id: str,
        step_number: int,
        player_id: str,
        stint_number: int,
        health: HealthScoreResult,
    ):
        """Records metrics and traces for an individual agent turn."""
        log_msg = (
            f"[Turn {step_number}] Workflow={workflow_id} Player={player_id} Stint={stint_number} "
            f"Shealth={health.s_health:.2f} (Srep={health.s_rep:.2f}, Sstag={health.s_stag:.2f}, Scycle={health.s_cycle:.2f})"
        )
        if health.substitution_triggered:
            logger.warning("TELEMETRY ALERT: %s -> %s", log_msg, health.trigger_reason)
        else:
            logger.debug(log_msg)

        if self._tracer:
            with self._tracer.start_as_current_span("agent_turn") as span:
                span.set_attribute("workflow.id", workflow_id)
                span.set_attribute("turn.step_number", step_number)
                span.set_attribute("agent.player_id", player_id)
                span.set_attribute("agent.stint_number", stint_number)
                span.set_attribute("coach.s_health", health.s_health)
                span.set_attribute("coach.s_rep", health.s_rep)
                span.set_attribute("coach.s_stag", health.s_stag)
                span.set_attribute("coach.s_cycle", health.s_cycle)
                span.set_attribute("coach.substitution_triggered", health.substitution_triggered)

    def record_substitution_event(self, workflow_id: str, event: SubstitutionEvent):
        """Records an atomic bench substitution event."""
        logger.info(
            "BENCH SUBSTITUTION: Workflow=%s Stint #%d: %s -> %s | Fencing: %d -> %d | Reason: %s",
            workflow_id, event.stint_number, event.outgoing_player, event.incoming_player,
            event.old_fencing_token, event.new_fencing_token, event.reason,
        )

        if self._tracer:
            with self._tracer.start_as_current_span("bench_substitution") as span:
                span.set_attribute("workflow.id", workflow_id)
                span.set_attribute("substitution.stint_number", event.stint_number)
                span.set_attribute("substitution.outgoing_player", event.outgoing_player)
                span.set_attribute("substitution.incoming_player", event.incoming_player)
                span.set_attribute("substitution.old_token", event.old_fencing_token)
                span.set_attribute("substitution.new_token", event.new_fencing_token)
                span.set_attribute("substitution.reason", event.reason)
                if event.restored_snapshot_id:
                    span.set_attribute("substitution.restored_snapshot_id", event.restored_snapshot_id)


_telemetry_instance: Optional[TelemetryManager] = None

def get_telemetry_manager() -> TelemetryManager:
    global _telemetry_instance
    if _telemetry_instance is None:
        _telemetry_instance = TelemetryManager()
    return _telemetry_instance

