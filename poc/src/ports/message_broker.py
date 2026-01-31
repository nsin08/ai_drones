"""Message broker port (interface for hexagonal architecture)."""
from abc import ABC, abstractmethod
from typing import Callable, Dict, Any


class MessageBroker(ABC):
    """Abstract message broker interface (port)."""
    
    @abstractmethod
    def publish(self, topic: str, payload: Dict[str, Any]):
        """
        Publish message to topic.
        
        Args:
            topic: Topic path (e.g., "fleet/D001/telemetry")
            payload: Message payload (will be JSON-serialized)
        """
        pass
    
    @abstractmethod
    def subscribe(self, topic_pattern: str, callback: Callable[[str, Dict[str, Any]], None]):
        """
        Subscribe to topic pattern.
        
        Args:
            topic_pattern: Topic pattern (e.g., "fleet/+/telemetry")
            callback: Function called with (topic, payload) when message arrives
        """
        pass
    
    @abstractmethod
    def start(self):
        """Start broker connection."""
        pass
    
    @abstractmethod
    def stop(self):
        """Stop broker connection."""
        pass
