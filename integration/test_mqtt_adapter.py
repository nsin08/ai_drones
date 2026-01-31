"""Integration tests for MQTT adapter with real broker."""
import json
import time
import pytest
import threading
from poc.src.adapters.mqtt_broker import MQTTBrokerAdapter


class TestMQTTBrokerAdapter:
    """Test real MQTT broker connectivity and pub/sub."""
    
    @pytest.fixture
    def adapter(self):
        """Create MQTT adapter (assumes broker on localhost:1883)."""
        return MQTTBrokerAdapter(
            broker_host="localhost",
            broker_port=1883,
            client_id="test-client",
            timeout_sec=5.0
        )
    
    def test_connect_to_broker(self, adapter):
        """Test connection to real MQTT broker."""
        assert adapter.connect(), "Should connect to broker"
        assert adapter._connected, "Should be connected"
        adapter.disconnect()
    
    def test_publish_message(self, adapter):
        """Test publishing message to topic."""
        assert adapter.connect(), "Should connect"
        
        success = adapter.publish(
            "test/topic",
            json.dumps({"test": "data"})
        )
        assert success, "Should publish successfully"
        adapter.disconnect()
    
    def test_subscribe_and_receive(self, adapter):
        """Test subscribe callback receives published messages."""
        assert adapter.connect(), "Should connect"
        
        # Prepare to receive message
        received = []
        
        def callback(topic, payload):
            received.append((topic, payload))
        
        assert adapter.subscribe("test/receive", callback), "Should subscribe"
        
        # Allow subscription to register on broker
        time.sleep(0.5)
        
        # Publish message
        msg = {"test": "message", "number": 123}
        adapter.publish("test/receive", json.dumps(msg))
        
        # Wait for callback
        time.sleep(0.5)
        
        # Verify message was received
        assert len(received) == 1, "Should receive 1 message"
        topic, payload = received[0]
        assert topic == "test/receive"
        assert json.loads(payload) == msg
        
        adapter.disconnect()
    
    def test_multiple_subscribers(self, adapter):
        """Test multiple subscribers on same topic."""
        assert adapter.connect(), "Should connect"
        
        received1 = []
        received2 = []
        
        def callback1(topic, payload):
            received1.append((topic, payload))
        
        def callback2(topic, payload):
            received2.append((topic, payload))
        
        assert adapter.subscribe("test/multi", callback1), "Should subscribe 1st"
        assert adapter.subscribe("test/multi", callback2), "Should subscribe 2nd"
        
        time.sleep(0.5)
        
        msg = {"test": "broadcast"}
        adapter.publish("test/multi", json.dumps(msg))
        
        time.sleep(0.5)
        
        # Both should receive
        assert len(received1) == 1
        assert len(received2) == 1
        assert json.loads(received1[0][1]) == msg
        assert json.loads(received2[0][1]) == msg
        
        adapter.disconnect()
    
    def test_wildcard_subscription(self, adapter):
        """Test subscribing to topic wildcard."""
        assert adapter.connect(), "Should connect"
        
        received = []
        
        def callback(topic, payload):
            received.append((topic, payload))
        
        # Subscribe to all test/wildcard/* topics
        assert adapter.subscribe("test/wildcard/+", callback), "Should subscribe"
        
        time.sleep(0.5)
        
        # Publish to different subtopics
        adapter.publish("test/wildcard/alpha", json.dumps({"n": 1}))
        adapter.publish("test/wildcard/beta", json.dumps({"n": 2}))
        adapter.publish("test/wildcard/gamma", json.dumps({"n": 3}))
        
        time.sleep(0.5)
        
        # Should receive all 3
        assert len(received) == 3
        topics = [msg[0] for msg in received]
        assert "test/wildcard/alpha" in topics
        assert "test/wildcard/beta" in topics
        assert "test/wildcard/gamma" in topics
        
        adapter.disconnect()
    
    def test_unsubscribe(self, adapter):
        """Test unsubscribing from topic."""
        assert adapter.connect(), "Should connect"
        
        received = []
        
        def callback(topic, payload):
            received.append((topic, payload))
        
        assert adapter.subscribe("test/unsub", callback), "Should subscribe"
        time.sleep(0.5)
        
        # Unsubscribe
        assert adapter.unsubscribe("test/unsub"), "Should unsubscribe"
        time.sleep(0.5)
        
        # Publish after unsubscribe
        adapter.publish("test/unsub", json.dumps({"msg": "test"}))
        time.sleep(0.5)
        
        # Should not receive
        assert len(received) == 0
        
        adapter.disconnect()
    
    def test_drone_telemetry_format(self, adapter):
        """Test publishing drone telemetry in expected format."""
        assert adapter.connect(), "Should connect"
        
        received = []
        
        def callback(topic, payload):
            received.append(json.loads(payload))
        
        assert adapter.subscribe("ai_drones/telemetry/D001", callback)
        time.sleep(0.5)
        
        # Publish telemetry in standard format
        telemetry = {
            "drone_id": "D001",
            "timestamp": time.time(),
            "position": {
                "lat": 28.6139,
                "lon": 77.2090,
                "alt_m": 50.0
            },
            "battery_pct": 87.5,
            "velocity_mps": 15.0,
            "armed": True,
            "mode": "GUIDED"
        }
        
        adapter.publish(
            "ai_drones/telemetry/D001",
            json.dumps(telemetry)
        )
        
        time.sleep(0.5)
        
        assert len(received) == 1
        msg = received[0]
        assert msg["drone_id"] == "D001"
        assert msg["battery_pct"] == 87.5
        assert msg["position"]["lat"] == 28.6139
        
        adapter.disconnect()


# Pytest markers for integration vs unit tests
def pytest_configure(config):
    """Register custom marker."""
    config.addinivalue_line(
        "markers", "integration: mark test as requiring real MQTT broker"
    )


# Mark all tests as integration
pytestmark = pytest.mark.integration
