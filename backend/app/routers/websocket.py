from fastapi import APIRouter, WebSocket, WebSocketDisconnect
import asyncio
import json
import redis.asyncio as redis
from app.core.config import settings

router = APIRouter(tags=["websocket"])


@router.websocket("/ws/meetings/{meeting_id}")
async def meeting_websocket(websocket: WebSocket, meeting_id: str):
    """
    WebSocket endpoint for real-time meeting updates.
    
    Events sent to client:
    - recording_status: Recording start/stop events
    - audio_level: Real-time audio levels (RMS)
    - transcript_partial: Live transcription segments
    - processing_progress: Progress of background jobs
    - note_added: When a note is added
    
    Messages from client:
    - add_note: Add a timestamped note
    - update_title: Update meeting title
    """
    await websocket.accept()
    
    # Connect to Redis
    redis_client = None
    pubsub = None
    
    try:
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        
        # Subscribe to audio levels channel
        pubsub = redis_client.pubsub()
        await pubsub.subscribe(f"audio:levels:{meeting_id}")
        
        # Send initial connection message
        await websocket.send_json({
            "event": "connected",
            "data": {"meeting_id": meeting_id}
        })
        
        # Create tasks for concurrent operation
        redis_task = asyncio.create_task(
            handle_redis_messages(pubsub, websocket)
        )
        client_task = asyncio.create_task(
            handle_client_messages(websocket, redis_client, meeting_id)
        )
        
        # Wait for either task to complete (disconnect or error)
        done, pending = await asyncio.wait(
            [redis_task, client_task],
            return_when=asyncio.FIRST_COMPLETED
        )
        
        # Cancel remaining tasks
        for task in pending:
            task.cancel()
            
    except Exception as e:
        print(f"WebSocket error: {e}")
        await websocket.close(code=1011, reason=str(e))
    finally:
        if pubsub:
            await pubsub.unsubscribe(f"audio:levels:{meeting_id}")
            await pubsub.close()
        if redis_client:
            await redis_client.close()


async def handle_redis_messages(pubsub, websocket: WebSocket):
    """Listen for Redis messages and forward to WebSocket."""
    try:
        async for message in pubsub.listen():
            if message["type"] == "message":
                data = json.loads(message["data"])
                await websocket.send_json({
                    "event": "audio_level",
                    "data": data
                })
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Redis handler error: {e}")


async def handle_client_messages(websocket: WebSocket, redis_client, meeting_id: str):
    """Handle messages from WebSocket client."""
    try:
        while True:
            # Receive message from client
            message = await websocket.receive_json()
            
            action = message.get("action")
            data = message.get("data", {})
            
            if action == "add_note":
                # Publish note event to Redis for other clients
                await redis_client.publish(
                    f"meeting:{meeting_id}:notes",
                    json.dumps({
                        "content": data.get("content"),
                        "note_type": data.get("note_type", "general"),
                        "recording_offset": data.get("recording_offset")
                    })
                )
                
                await websocket.send_json({
                    "event": "note_acknowledged",
                    "data": {"status": "received"}
                })
                
            elif action == "update_title":
                # Publish title update event
                await redis_client.publish(
                    f"meeting:{meeting_id}:updates",
                    json.dumps({
                        "type": "title_update",
                        "title": data.get("title")
                    })
                )
                
            else:
                await websocket.send_json({
                    "event": "error",
                    "data": {"message": f"Unknown action: {action}"}
                })
                
    except WebSocketDisconnect:
        print(f"Client disconnected from meeting {meeting_id}")
    except asyncio.CancelledError:
        pass
    except Exception as e:
        print(f"Client handler error: {e}")


# Simple health check endpoint for WebSocket
@router.get("/ws/health")
async def websocket_health():
    """Check WebSocket/Redis connectivity."""
    try:
        redis_client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True
        )
        await redis_client.ping()
        await redis_client.close()
        return {"status": "ok", "redis": "connected"}
    except Exception as e:
        return {"status": "error", "redis": str(e)}
