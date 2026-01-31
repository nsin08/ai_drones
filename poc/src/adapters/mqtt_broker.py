"""MQTT broker adapter for real-world integrations."""
import json
import time
import threading
from typing import Callable, Dict, List, Optional, Any
import paho.mqtt.client as mqtt
from src.ports.message_broker import MessageBroker


class MQTTBrokerAdapter(MessageBroker):
    """Production MQTT broker adapter using Eclipse Mosquitto.
    
    Connects to a real MQTT broker to enable communication between:
    - Drone simulators (publish telemetry)
    - Fault injectors (modify telemetry)
    - Mission planners (subscribe to telemetry, publish commands)
    - AI advisory (subscribe to telemetry, publish recommendations)
    - Mission Planner UI (MQTT.Cool for debugging)
    """
    
    def __init__(
        self,
        broker_host: str = "localhost",
        broker_port: int = 1883,
        client_id: str = "fleet-services",
        timeout_sec: float = 30.0
    ):
        """Initialize MQTT broker adapter.
        
        Args:
            broker_host: MQTT broker hostname (default: localhost)
            broker_port: MQTT broker port (default: 1883)
            client_id: MQTT client ID for this service
            timeout_sec: Connection timeout
        """
        self.broker_host = broker_host
        self.broker_port = broker_port
        self.client_id = client_id
        self.timeout_sec = timeout_sec
        
        # Try both paho-mqtt v2 and v1 API versions for compatibility
        try:
            self._client = mqtt.Client(mqtt.CallbackAPIVersion.V1, client_id=client_id)
        except AttributeError:
            # Fallback for older paho-mqtt versions
            self._client = mqtt.Client(client_id=client_id)
        
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message
        
        self._subscribers: Dict[str, List[Callable]] = {}
        self._connected = False
        self._lock = threading.Lock()
    
    def start(self) -> bool:
        """Start MQTT broker connection. Alias for connect()."""
        return self.connect()
    
    def stop(self) -> None:
        """Stop MQTT broker connection. Alias for disconnect()."""
        self.disconnect()
    
    def connect(self) -> bool:
        """Connect to MQTT broker.
        
        Returns:
            True if connected successfully, False otherwise
        """
        try:
            self._client.connect(
                self.broker_host,
                self.broker_port,
                keepalive=60
            )
            self._client.loop_start()
            
            # Wait for connection callback
            start = time.time()
            while not self._connected and (time.time() - start) < self.timeout_sec:
                time.sleep(0.1)
            
            return self._connected
        except Exception as e:
            print(f"[MQTT] Connection error: {e}")
            return False
    
    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        self._client.loop_stop()
        self._client.disconnect()
        self._connected = False
    
    def publish(self, topic: str, message: str) -> bool:
        """Publish message to topic.
        
        Args:
            topic: MQTT topic (e.g., 'telemetry/D001')
            message: Message payload (JSON string)
        
        Returns:
            True if published successfully
        """
        if not self._connected:
            return False
        
        try:
            result = self._client.publish(topic, message, qos=1)
            return result.rc == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"[MQTT] Publish error on {topic}: {e}")
            return False
    
    def subscribe(self, topic: str, callback: Callable[[str, str], None]) -> bool:
        """Subscribe to topic with callback.
        
        Args:
            topic: MQTT topic pattern (e.g., 'commands/+' subscribes to all commands)
            callback: Function(topic, message) called when message received
        
        Returns:
            True if subscription succeeded
        """
        if not self._connected:
            return False
        
        with self._lock:
            if topic not in self._subscribers:
                self._subscribers[topic] = []
            self._subscribers[topic].append(callback)
        
        try:
            result = self._client.subscribe(topic, qos=1)
            return result[0] == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"[MQTT] Subscribe error on {topic}: {e}")
            return False
    
    def unsubscribe(self, topic: str) -> bool:
        """Unsubscribe from topic.
        
        Args:
            topic: MQTT topic to unsubscribe
        
        Returns:
            True if unsubscribed successfully
        """
        with self._lock:
            if topic in self._subscribers:
                del self._subscribers[topic]
        
        try:
            result = self._client.unsubscribe(topic)
            return result[0] == mqtt.MQTT_ERR_SUCCESS
        except Exception as e:
            print(f"[MQTT] Unsubscribe error on {topic}: {e}")
            return False
    
    # Private callbacks
    
    def _on_connect(self, client, userdata, flags, rc):
        """Called when client connects to broker."""
        if rc == 0:
            self._connected = True
            print(f"[MQTT] Connected to {self.broker_host}:{self.broker_port}")
        else:
            print(f"[MQTT] Connection failed with code {rc}")
    
    def _on_disconnect(self, client, userdata, rc):
        """Called when client disconnects from broker."""
        self._connected = False
        if rc != 0:
            print(f"[MQTT] Unexpected disconnection: {rc}")
    
    def _on_message(self, client, userdata, msg):
        """Called when message received from subscribed topic."""
        topic = msg.topic
        payload = msg.payload.decode("utf-8")
        
        with self._lock:
            if topic in self._subscribers:
                for callback in self._subscribers[topic]:
                    try:
                        callback(topic, payload)
                    except Exception as e:
                        print(f"[MQTT] Callback error on {topic}: {e}")
