"""
WebSocket Endpoint - Live Price Streaming
Phase 4 - Week 8 - Day 4-5

Endpoint: WebSocket /ws/prices/{symbol}
Streams: Real-time price updates from Redis Pub/Sub
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..database import get_redis
import json
import logging
import asyncio
from datetime import datetime

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """
    Manages WebSocket connections for real-time price streaming
    """
    
    def __init__(self):
        self.active_connections: list[WebSocket] = []
    
    async def connect(self, websocket: WebSocket):
        """Accept new WebSocket connection"""
        await websocket.accept()
        self.active_connections.append(websocket)
        logger.info(f"✅ New WebSocket connection. Total: {len(self.active_connections)}")
    
    def disconnect(self, websocket: WebSocket):
        """Remove disconnected WebSocket"""
        self.active_connections.remove(websocket)
        logger.info(f"❌ WebSocket disconnected. Total: {len(self.active_connections)}")
    
    async def send_personal_message(self, message: str, websocket: WebSocket):
        """Send message to specific client"""
        await websocket.send_text(message)
    
    async def broadcast(self, message: str):
        """Broadcast message to all connected clients"""
        for connection in self.active_connections:
            try:
                await connection.send_text(message)
            except Exception as e:
                logger.error(f"Error broadcasting to client: {e}")


# Global connection manager
manager = ConnectionManager()


@router.websocket("/ws/prices/{symbol}")
async def websocket_prices(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time price streaming
    
    Args:
        websocket: WebSocket connection
        symbol: Cryptocurrency symbol (BTC, ETH, or 'all')
    
    Usage (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws/prices/BTC');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Price update:', data);
        };
    """
    
    # Normalize symbol
    symbol = symbol.upper()
    
    # Accept connection
    await manager.connect(websocket)
    
    try:
        # Send welcome message
        welcome_msg = {
            "type": "connection",
            "message": f"Connected to {symbol} price stream",
            "timestamp": datetime.utcnow().isoformat()
        }
        await websocket.send_json(welcome_msg)
        
        # Get Redis client for polling
        redis_client = get_redis()
        
        # Stream prices in a loop
        while True:
            try:
                # Determine which symbols to stream
                symbols = ["BTC", "ETH"] if symbol == "ALL" else [symbol]
                
                # Fetch latest prices from Redis
                for sym in symbols:
                    redis_key = f"crypto:{sym}:latest"
                    cached_data = redis_client.get(redis_key)
                    
                    if cached_data:
                        data = json.loads(cached_data)
                        
                        # Send price update
                        message = {
                            "type": "price_update",
                            "symbol": sym,
                            "data": data,
                            "timestamp": datetime.utcnow().isoformat()
                        }
                        await websocket.send_json(message)
                
                # Poll every 2 seconds
                await asyncio.sleep(2)
                
            except WebSocketDisconnect:
                logger.info("Client disconnected")
                break
            
            except Exception as e:
                logger.error(f"Error in WebSocket loop: {e}")
                error_msg = {
                    "type": "error",
                    "message": str(e),
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_json(error_msg)
                await asyncio.sleep(5)  # Backoff on error
    
    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket disconnected for {symbol}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.get("/ws/test")
async def websocket_test_page():
    """
    HTML test page for WebSocket connection
    """
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>WebSocket Test - Crypto Prices</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; }
                #messages { border: 1px solid #ccc; height: 400px; overflow-y: scroll; padding: 10px; }
                .message { margin: 5px 0; padding: 5px; background: #f0f0f0; }
                button { padding: 10px 20px; margin: 10px 5px; font-size: 16px; }
            </style>
        </head>
        <body>
            <h1>🪙 Crypto Price WebSocket Test</h1>
            <div>
                <button onclick="connectBTC()">Connect BTC</button>
                <button onclick="connectETH()">Connect ETH</button>
                <button onclick="connectAll()">Connect ALL</button>
                <button onclick="disconnect()">Disconnect</button>
            </div>
            <div id="messages"></div>
            
            <script>
                let ws = null;
                
                function connectBTC() { connect('BTC'); }
                function connectETH() { connect('ETH'); }
                function connectAll() { connect('ALL'); }
                
                function connect(symbol) {
                    if (ws) ws.close();
                    
                    ws = new WebSocket(`ws://localhost:8000/ws/prices/${symbol}`);
                    
                    ws.onopen = () => {
                        addMessage('✅ Connected to ' + symbol + ' stream', 'green');
                    };
                    
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        addMessage(JSON.stringify(data, null, 2), 'blue');
                    };
                    
                    ws.onerror = (error) => {
                        addMessage('❌ Error: ' + error, 'red');
                    };
                    
                    ws.onclose = () => {
                        addMessage('❌ Disconnected', 'orange');
                    };
                }
                
                function disconnect() {
                    if (ws) {
                        ws.close();
                        ws = null;
                    }
                }
                
                function addMessage(msg, color) {
                    const div = document.createElement('div');
                    div.className = 'message';
                    div.style.borderLeft = `4px solid ${color}`;
                    div.innerHTML = '<strong>' + new Date().toLocaleTimeString() + '</strong><br>' + 
                                    '<pre>' + msg + '</pre>';
                    document.getElementById('messages').appendChild(div);
                    div.scrollIntoView();
                }
            </script>
        </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)
