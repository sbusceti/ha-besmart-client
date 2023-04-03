import logging

import paho.mqtt.client as mqtt

_LOGGER = logging.getLogger(__name__)


class MqttClient:
    def __init__(self, host, port, username, password):
        self.client = mqtt.Client()
        self.client.username_pw_set(username, password)
        self.client.connect(host, port)
        self.client.on_connect = self.on_connect
        self.client.on_disconnect = self.on_disconnect
        self.client.loop_start()

    def on_connect(self, client, userdata, flags, rc):
        if rc == 0:
            _LOGGER.info("Connected to mqtt broker")
        else:
            _LOGGER.error(f"Connection to mqtt broker failed: {rc}")

    def on_disconnect(client, userdata, rc):
        _LOGGER.info("Mqtt broker disconnected")

    def subscribe(self, topic, callback):
        self.client.on_message = callback
        self.client.subscribe(topic)
        _LOGGER.info(f"Subscribed to {topic}")
