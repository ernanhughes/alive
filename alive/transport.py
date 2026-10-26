import asyncio
import contextlib
import json

import zmq
import zmq.asyncio

from alive.schemas import EventEnvelope


class ZmqTransport:
    """Ephemeral local PUB/SUB. Database sequence cursors provide durable recovery."""

    def __init__(self):
        self.context = zmq.asyncio.Context()
        self.publisher = self.context.socket(zmq.PUB)
        self.publisher.setsockopt(zmq.LINGER, 0)
        port = self.publisher.bind_to_random_port("tcp://127.0.0.1")
        self.endpoint = f"tcp://127.0.0.1:{port}"
        self.subscriber = self.context.socket(zmq.SUB)
        self.subscriber.setsockopt(zmq.LINGER, 0)
        self.subscriber.setsockopt(zmq.SUBSCRIBE, b"")
        self.subscriber.connect(self.endpoint)
        self.listeners: set[asyncio.Queue] = set()
        self.received = 0
        self.last_error = None
        self.task = None

    async def start(self):
        self.task = asyncio.create_task(self.listen())
        # PUB/SUB subscription handshake is asynchronous. History remains the recovery source.
        await asyncio.sleep(0.15)

    async def publish(self, event):
        EventEnvelope.model_validate(event)
        await self.publisher.send_json(event)

    async def listen(self):
        while True:
            raw = await self.subscriber.recv()
            try:
                event = json.loads(raw)
                EventEnvelope.model_validate(event)
                self.received += 1
                for queue in tuple(self.listeners):
                    if queue.full():
                        queue.get_nowait()
                    queue.put_nowait(event)
            except (ValueError, TypeError) as exc:
                self.last_error = type(exc).__name__

    async def close(self):
        if self.task:
            self.task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await self.task
        self.publisher.close()
        self.subscriber.close()
        self.context.term()


class InProcessTransport:
    def __init__(self):
        self.events = []

    async def publish(self, event):
        EventEnvelope.model_validate(event)
        self.events.append(event)
