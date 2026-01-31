"""In-memory message broker adapter (for testing)."""
from typing import Callable, Dict, Any, List
from ..ports.message_broker import MessageBroker


class InMemoryBroker(MessageBroker):
    """In-memory broker for testing (no external dependencies)."""
    
    def __init__(self):
        self._subscribers: Dict[str, List[Callable]] = {}
        self._published: List[tuple[str, Dict[str, Any]]] = []  # History for testing
    
    def publish(self, topic: str, payload: Dict[str, Any]):
        """Publish to in-memory subscribers."""
        self._published.append((topic, payload))
        
        # Notify subscribers
        for pattern, callbacks in self._subscribers.items():
            if self._topic_matches(topic, pattern):
                for callback in callbacks:
                    callback(topic, payload)
    
    def subscribe(self, topic_pattern: str, callback: Callable[[str, Dict[str, Any]], None]):
        """Subscribe to topic pattern."""
        if topic_pattern not in self._subscribers:
            self._subscribers[topic_pattern] = []
        self._subscribers[topic_pattern].append(callback)
    
    def start(self):
        """No-op for in-memory broker."""
        pass
    
    def stop(self):
        """No-op for in-memory broker."""
        pass
    
    def get_published(self) -> List[tuple[str, Dict[str, Any]]]:
        """Get history of published messages (for testing)."""
        return self._published.copy()
    
    def clear_history(self):
        """Clear published message history."""
        self._published.clear()
    
    @staticmethod
    def _topic_matches(topic: str, pattern: str) -> bool:
        """Simple topic matching (supports '+' wildcard)."""
        topic_parts = topic.split('/')
        pattern_parts = pattern.split('/')
        
        if len(topic_parts) != len(pattern_parts):
            return False
        
        for t, p in zip(topic_parts, pattern_parts):
            if p == '+':
                continue  # Wildcard matches any single level
            if t != p:
                return False
        
        return True
