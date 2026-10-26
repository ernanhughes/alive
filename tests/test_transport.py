import asyncio
import uuid

import zmq

from alive.schemas import EventEnvelope
from alive.transport import InProcessTransport, ZmqTransport


async def test_actual_zmq_independent_subscriber_and_reconnect():
    transport = ZmqTransport()
    await transport.start()
    subscriber = transport.context.socket(zmq.SUB)
    subscriber.setsockopt(zmq.LINGER, 0)
    subscriber.setsockopt(zmq.SUBSCRIBE, b"")
    subscriber.connect(transport.endpoint)
    try:
        event = EventEnvelope(instance_id=uuid.uuid4(), event_type="alive.heartbeat", source="test")
        payload = event.model_dump(mode="json")
        for _ in range(2):
            await asyncio.sleep(0.2)
            await transport.publish(payload)
            received = await asyncio.wait_for(subscriber.recv_json(), 2)
            assert received["event_id"] == str(event.event_id)
            assert received["correlation_id"] == str(event.correlation_id)
            subscriber.disconnect(transport.endpoint)
            subscriber.connect(transport.endpoint)
        assert transport.received >= 1
    finally:
        subscriber.close()
        await transport.close()


async def test_inprocess_adapter():
    transport = InProcessTransport()
    event = EventEnvelope(instance_id=uuid.uuid4(), event_type="alive.started", source="test")
    await transport.publish(event.model_dump(mode="json"))
    assert transport.events[0]["event_id"] == str(event.event_id)
