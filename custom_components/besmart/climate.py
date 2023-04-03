import json
import logging

import voluptuous as vol

from homeassistant.components.besmart.mqtt_client import MqttClient
from homeassistant.components.climate import (
    ATTR_TARGET_TEMP_LOW,
    PLATFORM_SCHEMA,
    ClimateEntity,
)
from homeassistant.components.climate.const import (
    ATTR_TARGET_TEMP_HIGH,
    CURRENT_HVAC_COOL,
    CURRENT_HVAC_HEAT,
    CURRENT_HVAC_OFF,
    HVAC_MODE_COOL,
    HVAC_MODE_HEAT,
    HVAC_MODE_OFF,
    SUPPORT_PRESET_MODE,
    SUPPORT_TARGET_TEMPERATURE,
    SUPPORT_TARGET_TEMPERATURE_RANGE,
)
from homeassistant.const import (
    ATTR_TEMPERATURE,
    CONF_NAME,
    CONF_ROOM,
    TEMP_CELSIUS,
    TEMP_FAHRENHEIT,
)
from homeassistant.core import HomeAssistant
import homeassistant.helpers.config_validation as cv
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.typing import ConfigType, DiscoveryInfoType

from .const import *

_LOGGER = logging.getLogger(__name__)

SUPPORT_FLAGS = (
    SUPPORT_PRESET_MODE | SUPPORT_TARGET_TEMPERATURE
)

ATTR_MODE = "mode"

COMMAND_TOPIC = "besmart/command"



PLATFORM_SCHEMA = PLATFORM_SCHEMA.extend(
    {
        vol.Optional(CONF_NAME, default=DEFAULT_NAME): cv.string,
        vol.Optional(CONF_ROOM, default=DEFAULT_ROOM_NAME): cv.string,
        vol.Required(WIFIBOX_ID): cv.string,
        vol.Required(THERMOSTAT_ID): cv.string,
        vol.Required(MQTT_BROKER_HOST): cv.string,
        vol.Required(MQTT_BROKER_PORT): cv.positive_int,
        vol.Required(MQTT_BROKER_USERNAME): cv.string,
        vol.Required(MQTT_BROKER_PASSWORD): cv.string,
    }
)


def setup_platform(
    hass: HomeAssistant,
    config: ConfigType,
    add_entities: AddEntitiesCallback,
    discovery_info: DiscoveryInfoType | None = None,
) -> None:
   
    mqtt_client = MqttClient(
        config.get(MQTT_BROKER_HOST),
        config.get(MQTT_BROKER_PORT),
        config.get(MQTT_BROKER_USERNAME),
        config.get(MQTT_BROKER_PASSWORD),
    )
    thermostat = Thermostat(config.get(CONF_NAME), config.get(CONF_ROOM),config.get(WIFIBOX_ID),config.get(THERMOSTAT_ID),mqtt_client)
    topic = f"besmart/{config.get(WIFIBOX_ID)}/{config.get(THERMOSTAT_ID)}/status"
    mqtt_client.subscribe(topic, thermostat.on_status_message)
    add_entities([thermostat])  

class Thermostat(ClimateEntity):
    """Representation of a Besmart thermostat."""

    # BeSmart WorkMode
    AUTO = 0  # 'Auto'
    MANUAL = 1  # 'Manuale - Confort'
    ECONOMY = 2  # 'Holiday - Economy'
    PARTY = 3  # 'Party - Confort'
    IDLE = 4  # 'Spento - Antigelo'
    DHW = 5  # 'Sanitario - Domestic hot water only'

    PRESET_HA_TO_BESMART = {
        "AUTO": AUTO,
        "MANUAL": MANUAL,
        "ECO": ECONOMY,
        "PARTY": PARTY,
        "IDLE": IDLE,
        "DHW": DHW,
    }

    PRESET_BESMART_TO_HA = {
        AUTO: "AUTO",
        MANUAL: "MANUAL",
        ECONOMY: "ECO",
        PARTY: "PARTY",
        IDLE: "IDLE",
        DHW: "DHW",
    }

    HVAC_MODE_LIST = (HVAC_MODE_COOL, HVAC_MODE_HEAT)
    PRESET_MODE_LIST = list(PRESET_HA_TO_BESMART)
    # BeSmart Season
    HVAC_MODE_HA_BESMART = {HVAC_MODE_HEAT: "1", HVAC_MODE_COOL: "0"}
    HVAC_MODE_BESMART_TO_HA = {"1": HVAC_MODE_HEAT, "0": HVAC_MODE_COOL}

    def __init__(self, name, room,wifiBoxId,thermostatId,client:MqttClient):
        """Initialize the thermostat."""
        self._name = name
        self._room_name = room
        self._current_temp = 0
        self._current_state = self.IDLE
        self._current_operation = ""
        self._current_unit = 0
        self._tempSetMark = 0
        self._battery = "0"
        self._frostT = 0
        self._saveT = 0
        self._comfT = 0
        self._season = "1"
        self._outside_temp = 0
        self._client = client
        self._wifiBoxId = wifiBoxId
        self._thermostatId = thermostatId
        self._maxSetPoint = 60
        self._minSetPoint = 45
        self._current_setpoint = 0
        self._climaticCurve = 0
        self._currentHeatingSetpoint = 0
        self._heating = False

    @property
    def should_poll(self):
        return False

    def on_status_message(self, client, userdata, message):
        jsonString = message.payload.decode()
        _LOGGER.info(f"Mqtt message received: {jsonString}")

        data = json.loads(jsonString)
        if ROOM_TEMPERATURE in data:
            self._current_temp = data[ROOM_TEMPERATURE]
        if ANTI_FROST_TEMPERATURE in data:
            self._frostT = data[ANTI_FROST_TEMPERATURE]
        if ECONOMY_TEMPERATURE in data:
            self._saveT = data[ECONOMY_TEMPERATURE]
        if COMFORT_TEMPERATURE in data:
            self._comfT = data[COMFORT_TEMPERATURE]
        if MIN_SETPOINT in data:
            self._minSetPoint = data[MIN_SETPOINT]
        if MAX_SETPOINT in data:
            self._maxSetPoint = data[MAX_SETPOINT]
        if CURRENT_SETPOINT in data:
            self._current_setpoint = data[CURRENT_SETPOINT]
        if CLIMATIC_CURVE in data:
            self._climaticCurve = data[CLIMATIC_CURVE]
        if CURRENT_HEATING_SETPOINT in data:
            self._currentHeatingSetpoint = data[CURRENT_HEATING_SETPOINT]
        if HEATING in data:
            self._heating = data[HEATING]
        if MODE in data:
            self._current_state = data[MODE]
        if OUTSIDE_TEMPERATURE in data:
            self._outside_temp = data[OUTSIDE_TEMPERATURE]
        self.update()

    def update(self):
        if not self.hass:
            return
        self.schedule_update_ha_state()

    @property
    def hvac_mode(self):
        """Current mode."""
        return self.HVAC_MODE_BESMART_TO_HA.get(self._season)

    @property
    def hvac_modes(self):
        """List of available operation modes."""
        return self.HVAC_MODE_LIST

    def set_hvac_mode(self, hvac_mode):
        """Set HVAC mode (COOL, HEAT)."""
        self._season = self.HVAC_MODE_HA_BESMART.get(hvac_mode)
        # TODO send command
        _LOGGER.info("Set hvac_mode hvac_mode=%s(%s)", str(hvac_mode), str(self._season))
        self.update()

    @property
    def hvac_action(self):
        """Current mode."""
        if self._heating:
            mode = self.hvac_mode
            if mode == HVAC_MODE_HEAT:
                return CURRENT_HVAC_HEAT
            else:
                return CURRENT_HVAC_COOL
        else:
            return CURRENT_HVAC_OFF

    @property
    def preset_mode(self):
        return self.PRESET_BESMART_TO_HA.get(self._current_state, "IDLE")

    @property
    def preset_modes(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""

        return self.PRESET_MODE_LIST

    def set_preset_mode(self, preset_mode):
        """Set HVAC mode (comfort, home, sleep, Party, Off)."""

        self._current_state = self.PRESET_HA_TO_BESMART.get(preset_mode, self.AUTO)
        data = {}
        data["command"] = "setMode"
        data["value"] = self._current_state
        data["wifiBoxId"] = self._wifiBoxId
        data["thermostatId"] = self._thermostatId
        json_data = json.dumps(data)
        self._client.client.publish(topic="besmart/command",payload=json_data)
        _LOGGER.info("json=%s", json_data)
        _LOGGER.info("Set operation mode=%s(%s)", str(preset_mode), str(self._current_state))
        self.update()

    @property
    def temperature_unit(self):
        """Return the unit of measurement."""
        if self._current_unit == 0:
            return TEMP_CELSIUS
        else:
            return TEMP_FAHRENHEIT

    @property
    def current_temperature(self):
        """Return the current temperature."""
        return self._current_temp

    @property
    def target_temperature(self):
        """Return the temperature we try to reach."""
        return self._current_setpoint

    @property
    def target_temperature_high(self):
        return self._comfT

    @property
    def target_temperature_low(self):
        return self._saveT

    @property
    def target_temperature_step(self):
        """Return the supported step of target temperature."""
        return 0.2

    @property
    def supported_features(self):
        """Return the list of supported features."""
        return SUPPORT_FLAGS

    @property
    def name(self):
        """Return the name of the thermostat."""
        return self._name

    @property
    def preset_modes(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""

        return self.PRESET_MODE_LIST

    @property
    def preset_mode(self):
        """List of supported preset (comfort, home, sleep, Party, Off)."""

        return self.PRESET_BESMART_TO_HA.get(self._current_state, "IDLE")

    def set_temperature(self, **kwargs):
        """Set new target temperature."""
        temperature = kwargs.get(ATTR_TEMPERATURE)

        _LOGGER.info(
            "target temperature: {} ".format(
                temperature
            )
        )
                
        if temperature:
            jsonObject = {"command": "setComfortTemperature", "value": temperature, "wifiBoxId": self._wifiBoxId, "thermostatId": self._thermostatId}
            self._client.client.publish(COMMAND_TOPIC,json.dumps(jsonObject))

            

    @property
    def extra_state_attributes(self):
        """Return the device specific state attributes."""
        return {
            ATTR_MODE: self._current_state,
            "battery_state": self._battery,
            "frost_t": self._frostT,
            "confort_t": self._comfT,
            "save_t": self._saveT,
            "season_mode": self.hvac_mode,
            "heating": self._heating,
            "outside_temperature": self._outside_temp,
            "maxSetPoint": self._maxSetPoint,
            "minSetPoint": self._minSetPoint
        }
