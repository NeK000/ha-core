"""Support for SwitchBot vacuum."""

from typing import Any

from switchbot_api import Device, Remote, SwitchBotAPI, VacuumCommands

from homeassistant.components.vacuum import (
    StateVacuumEntity,
    VacuumActivity,
    VacuumEntityFeature,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import SwitchbotCloudData
from .const import (
    DOMAIN,
    VACUUM_CLEANING_MODE_SWEEP,
    VACUUM_CLEANING_MODE_SWEEP_MOP,
    VACUUM_FAN_SPEED_MAX,
    VACUUM_FAN_SPEED_QUIET,
    VACUUM_FAN_SPEED_STANDARD,
    VACUUM_FAN_SPEED_STRONG,
    VACUUM_WATER_LEVEL_HIGH,
    VACUUM_WATER_LEVEL_LOW,
)
from .coordinator import SwitchBotCoordinator
from .entity import SwitchBotCloudEntity


async def async_setup_entry(
    hass: HomeAssistant,
    config: ConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up SwitchBot Cloud entry."""
    data: SwitchbotCloudData = hass.data[DOMAIN][config.entry_id]
    async_add_entities(
        _async_make_entity(data.api, device, coordinator)
        for device, coordinator in data.devices.vacuums
    )


VACUUM_SWITCHBOT_STATE_TO_HA_STATE: dict[str, VacuumActivity] = {
    "StandBy": VacuumActivity.IDLE,
    "Clearing": VacuumActivity.CLEANING,
    "Paused": VacuumActivity.PAUSED,
    "GotoChargeBase": VacuumActivity.RETURNING,
    "Charging": VacuumActivity.DOCKED,
    "ChargeDone": VacuumActivity.DOCKED,
    "Dormant": VacuumActivity.IDLE,
    "InTrouble": VacuumActivity.ERROR,
    "InRemoteControl": VacuumActivity.CLEANING,
    "InDustCollecting": VacuumActivity.DOCKED,
    "explore": VacuumActivity.CLEANING,
    "cleanAll": VacuumActivity.CLEANING,
    "cleanArea": VacuumActivity.CLEANING,
    "cleanRoom": VacuumActivity.CLEANING,
    "fillWater": VacuumActivity.CLEANING,
    "deepWashing": VacuumActivity.CLEANING,
    "backToCharge": VacuumActivity.RETURNING,
    "markingWaterBase": VacuumActivity.CLEANING,
    "drying": VacuumActivity.DOCKED,
    "collectDust": VacuumActivity.DOCKED,
    "remoteControl": VacuumActivity.CLEANING,
    "cleanWithExplorer": VacuumActivity.CLEANING,
    "fillWaterForHumi": VacuumActivity.CLEANING,
    "markingHumi": VacuumActivity.CLEANING,
}

VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED: dict[str, str] = {
    VACUUM_FAN_SPEED_QUIET: "0",
    VACUUM_FAN_SPEED_STANDARD: "1",
    VACUUM_FAN_SPEED_STRONG: "2",
    VACUUM_FAN_SPEED_MAX: "3",
}

VACUUM_S10_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED: dict[str, int] = {
    VACUUM_FAN_SPEED_QUIET: 1,
    VACUUM_FAN_SPEED_STANDARD: 2,
    VACUUM_FAN_SPEED_STRONG: 3,
    VACUUM_FAN_SPEED_MAX: 4,
}

VACUUM_S10_WATER_LEVEL_TO_SWITCHBOT_WATER_LEVEL: dict[str, int] = {
    VACUUM_WATER_LEVEL_LOW: 1,
    VACUUM_WATER_LEVEL_HIGH: 2,
}

VACUUM_S10_CLEANING_MODE_TO_SWITCHBOT_CLEANING_MODE: dict[str, str] = {
    VACUUM_CLEANING_MODE_SWEEP: "sweep",
    VACUUM_CLEANING_MODE_SWEEP_MOP: "Sweep and Mop",
}


# https://github.com/OpenWonderLabs/SwitchBotAPI?tab=readme-ov-file#robot-vacuum-cleaner-s1-plus-1
class SwitchBotCloudVacuum(SwitchBotCloudEntity, StateVacuumEntity):
    """Representation of a SwitchBot vacuum."""

    _attr_supported_features: VacuumEntityFeature = (
        VacuumEntityFeature.BATTERY
        | VacuumEntityFeature.FAN_SPEED
        | VacuumEntityFeature.PAUSE
        | VacuumEntityFeature.RETURN_HOME
        | VacuumEntityFeature.START
        | VacuumEntityFeature.STATE
    )

    _attr_name = None
    _attr_fan_speed_list: list[str] = list(
        VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED.keys()
    )

    async def async_set_fan_speed(self, fan_speed: str, **kwargs: Any) -> None:
        """Set fan speed."""
        self._attr_fan_speed = fan_speed
        if fan_speed in VACUUM_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED:
            await self.send_api_command(
                "changeParam",
                parameters={
                    "fanLevel": VACUUM_S10_FAN_SPEED_TO_SWITCHBOT_FAN_SPEED[fan_speed],
                    "waterLevel": VACUUM_S10_WATER_LEVEL_TO_SWITCHBOT_WATER_LEVEL[
                        VACUUM_WATER_LEVEL_HIGH
                    ],
                    "times": 1,
                },
            )

    async def async_pause(self) -> None:
        """Pause the cleaning task."""
        await self.send_api_command("pause")

    async def async_return_to_base(self, **kwargs: Any) -> None:
        """Set the vacuum cleaner to return to the dock."""
        await self.send_api_command(VacuumCommands.DOCK)

    async def async_start(self) -> None:
        """Start or resume the cleaning task."""
        await self.send_api_command(
            "startClean",
            parameters={
                "action": "sweep",
                "param": {"fanLevel": 1, "waterLevel": 1, "times": 1},
            },
        )

    def _set_attributes(self) -> None:
        """Set attributes from coordinator data."""
        if not self.coordinator.data:
            return

        self._attr_battery_level = self.coordinator.data.get("battery")
        self._attr_available = self.coordinator.data.get("onlineStatus") == "online"

        switchbot_state = (
            str(self.coordinator.data.get("workingStatus"))
            if str(self.coordinator.data.get("taskType")) == "standBy"
            else str(self.coordinator.data.get("taskType"))
        )

        self._attr_activity = VACUUM_SWITCHBOT_STATE_TO_HA_STATE.get(switchbot_state)


@callback
def _async_make_entity(
    api: SwitchBotAPI, device: Device | Remote, coordinator: SwitchBotCoordinator
) -> SwitchBotCloudVacuum:
    """Make a SwitchBotCloudVacuum."""
    return SwitchBotCloudVacuum(api, device, coordinator)
