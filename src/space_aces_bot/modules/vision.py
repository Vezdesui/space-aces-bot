from __future__ import annotations

import logging

from space_aces_bot.core.game_state import GameState, Npc, Position
from space_aces_bot.core.interfaces import Vision

logger = logging.getLogger(__name__)


class DummyVision(Vision):
    """Dummy vision module that pretends to update the game state.

    For now it advances the global tick counter and, if no NPCs are
    present yet, injects a single fake NPC so that farming/combat
    pipelines can be exercised end-to-end.
    """

    def update_state(self, state: GameState) -> None:
        logger.info("Vision.update_state: updating game state (dummy).")
        # Advance tick bookkeeping.
        state.advance_tick()

        # Inject a single fake NPC once so that BasicFarm/BasicCombat
        # have something to work with while real vision is not wired.
        if not state.npcs:
            npc = Npc(
                id="npc-1",
                position=Position(x=0.5, y=0.5),
                npc_type="weak_npc",
                hp=100,
                max_hp=100,
            )
            state.npcs[npc.id] = npc
            logger.info("DummyVision: injected fake NPC %s at (%.2f, %.2f).", npc.id, npc.position.x, npc.position.y)

    def screenshot(self):
        logger.debug("Vision.screenshot: returning dummy screenshot.")
        return None
