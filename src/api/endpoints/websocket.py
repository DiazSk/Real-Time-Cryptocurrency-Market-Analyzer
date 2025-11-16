"""
WebSocket Endpoint - Live Price Streaming with Redis Pub/Sub
Phase 4 - Week 8 - Day 4-5

Endpoint: WebSocket /ws/prices/{symbol}
Streams: Real-time price updates via Redis Pub/Sub (event-driven, not polling)
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect
from ..database import get_redis
from ..pubsub import pubsub_manager
import json
import logging
import asyncio
from datetime import datetime
from typing import Set

logger = logging.getLogger(__name__)

router = APIRouter(tags=["WebSocket"])


class ConnectionManager:
    """
    Manages WebSocket connections for real-time price streaming
    Enhanced with Redis Pub/Sub for event-driven updates
    """
    
    def __init__(self):
        # Store connections by symbol filter
        self.connections: dict[str, Set[WebSocket]] = {
            "ALL": set(),
            "BTC": set(),
            "ETH": set()
        }
        self.total_connections = 0
    
    async def connect(self, websocket: WebSocket, symbol: str = "ALL"):
        """Accept new WebSocket connection"""
        await websocket.accept()
        
        symbol = symbol.upper()
        if symbol not in self.connections:
            self.connections[symbol] = set()
        
        self.connections[symbol].add(websocket)
        self.total_connections += 1
        
        logger.info(f"✅ New WebSocket connection for {symbol}. "
                   f"Total: {self.total_connections} "
                   f"({symbol}: {len(self.connections[symbol])})")
    
    def disconnect(self, websocket: WebSocket, symbol: str = "ALL"):
        """Remove disconnected WebSocket"""
        symbol = symbol.upper()
        
        if symbol in self.connections and websocket in self.connections[symbol]:
            self.connections[symbol].remove(websocket)
            self.total_connections -= 1
            
            logger.info(f"❌ WebSocket disconnected for {symbol}. "
                       f"Total: {self.total_connections} "
                       f"({symbol}: {len(self.connections[symbol])})")
    
    async def send_personal_message(self, message: dict, websocket: WebSocket):
        """Send message to specific client"""
        try:
            await websocket.send_json(message)
        except Exception as e:
            logger.error(f"Error sending to client: {e}")
    
    async def broadcast_to_symbol(self, symbol: str, message: dict):
        """
        Broadcast message to all clients subscribed to a specific symbol
        """
        symbol = symbol.upper()
        
        # Send to ALL subscribers
        disconnected = set()
        if "ALL" in self.connections:
            for connection in self.connections["ALL"]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to ALL client: {e}")
                    disconnected.add(connection)
        
        # Send to symbol-specific subscribers
        if symbol in self.connections:
            for connection in self.connections[symbol]:
                try:
                    await connection.send_json(message)
                except Exception as e:
                    logger.error(f"Error broadcasting to {symbol} client: {e}")
                    disconnected.add(connection)
        
        # Clean up disconnected clients
        for conn in disconnected:
            for sym in self.connections:
                if conn in self.connections[sym]:
                    self.connections[sym].remove(conn)
                    self.total_connections -= 1
        
        if disconnected:
            logger.info(f"Cleaned up {len(disconnected)} disconnected clients")
    
    async def handle_pubsub_message(self, data: dict):
        """
        Handler for Redis Pub/Sub messages
        Broadcasts to appropriate WebSocket clients based on symbol
        """
        try:
            symbol = data.get("symbol", "UNKNOWN")
            
            # Create WebSocket message
            message = {
                "type": "price_update",
                "symbol": symbol,
                "data": data,
                "timestamp": datetime.utcnow().isoformat(),
                "source": "redis_pubsub"
            }
            
            # Broadcast to clients subscribed to this symbol
            await self.broadcast_to_symbol(symbol, message)
            
            logger.debug(f"📡 Broadcasted {symbol} update to WebSocket clients")
            
        except Exception as e:
            logger.error(f"Error handling Pub/Sub message: {e}")


# Global connection manager
manager = ConnectionManager()


@router.on_event("startup")
async def startup_websocket():
    """
    Initialize Redis Pub/Sub on application startup
    """
    try:
        # Connect to Redis Pub/Sub
        pubsub_manager.connect()
        
        # Register message handler
        pubsub_manager.add_handler(manager.handle_pubsub_message)
        
        # Start listening in background thread
        pubsub_manager.start_listening()
        
        logger.info("✅ WebSocket Pub/Sub system initialized")
        
    except Exception as e:
        logger.error(f"❌ Failed to initialize WebSocket Pub/Sub: {e}")


@router.on_event("shutdown")
async def shutdown_websocket():
    """
    Cleanup Redis Pub/Sub on application shutdown
    """
    try:
        pubsub_manager.stop_listening()
        logger.info("✅ WebSocket Pub/Sub system shut down")
    except Exception as e:
        logger.error(f"Error shutting down Pub/Sub: {e}")


@router.websocket("/ws/prices/{symbol}")
async def websocket_prices(websocket: WebSocket, symbol: str):
    """
    WebSocket endpoint for real-time price streaming via Redis Pub/Sub
    
    Args:
        websocket: WebSocket connection
        symbol: Cryptocurrency symbol (BTC, ETH, or 'all')
    
    Features:
        - Event-driven updates (no polling)
        - Sub-second latency
        - Automatic reconnection support
        - Connection health monitoring
    
    Usage (JavaScript):
        const ws = new WebSocket('ws://localhost:8000/ws/prices/BTC');
        ws.onmessage = (event) => {
            const data = JSON.parse(event.data);
            console.log('Price update:', data);
        };
    """
    
    # Normalize symbol
    symbol = symbol.upper()
    
    # Validate symbol
    if symbol not in ["BTC", "ETH", "ALL"]:
        await websocket.close(code=1008, reason=f"Invalid symbol: {symbol}")
        return
    
    # Accept connection
    await manager.connect(websocket, symbol)
    
    try:
        # Send welcome message
        welcome_msg = {
            "type": "connection",
            "message": f"Connected to {symbol} price stream (Pub/Sub mode)",
            "symbol": symbol,
            "timestamp": datetime.utcnow().isoformat(),
            "mode": "event_driven"
        }
        await websocket.send_json(welcome_msg)
        
        # Send initial data from Redis cache
        redis_client = get_redis()
        symbols = ["BTC", "ETH"] if symbol == "ALL" else [symbol]
        
        for sym in symbols:
            redis_key = f"crypto:{sym}:latest"
            cached_data = redis_client.get(redis_key)
            
            if cached_data:
                data = json.loads(cached_data)
                
                initial_msg = {
                    "type": "initial_data",
                    "symbol": sym,
                    "data": data,
                    "timestamp": datetime.utcnow().isoformat()
                }
                await websocket.send_json(initial_msg)
        
        # Keep connection alive and handle incoming messages
        # Real updates are pushed via Pub/Sub handler (no polling needed!)
        while True:
            try:
                # Wait for client messages (ping/pong, etc.)
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                
                # Handle client messages if needed
                try:
                    client_msg = json.loads(data)
                    
                    # Handle ping
                    if client_msg.get("type") == "ping":
                        await websocket.send_json({
                            "type": "pong",
                            "timestamp": datetime.utcnow().isoformat()
                        })
                
                except json.JSONDecodeError:
                    pass  # Ignore invalid JSON
                
            except asyncio.TimeoutError:
                # Send keepalive ping
                try:
                    await websocket.send_json({
                        "type": "keepalive",
                        "timestamp": datetime.utcnow().isoformat(),
                        "connections": manager.total_connections
                    })
                except:
                    break  # Connection closed
            
    except WebSocketDisconnect:
        manager.disconnect(websocket, symbol)
        logger.info(f"WebSocket disconnected for {symbol}")
    
    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket, symbol)


@router.get("/ws/test")
async def websocket_test_page():
    """
    HTML test page for WebSocket connection (Pub/Sub mode)
    """
    html_content = """
    <!DOCTYPE html>
    <html>
        <head>
            <title>WebSocket Test - Crypto Prices (Pub/Sub)</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 20px; background: #1a1a1a; color: #fff; }
                h1 { color: #4CAF50; }
                #messages { 
                    border: 1px solid #444; 
                    height: 500px; 
                    overflow-y: scroll; 
                    padding: 10px; 
                    background: #2a2a2a;
                    margin: 20px 0;
                }
                .message { 
                    margin: 5px 0; 
                    padding: 10px; 
                    background: #333; 
                    border-radius: 5px;
                    border-left: 4px solid #4CAF50;
                }
                .message.connection { border-left-color: #2196F3; }
                .message.error { border-left-color: #f44336; }
                .message.initial { border-left-color: #FF9800; }
                button { 
                    padding: 12px 24px; 
                    margin: 5px; 
                    font-size: 16px; 
                    border: none;
                    border-radius: 5px;
                    cursor: pointer;
                    background: #4CAF50;
                    color: white;
                    font-weight: bold;
                }
                button:hover { background: #45a049; }
                button.disconnect { background: #f44336; }
                button.disconnect:hover { background: #da190b; }
                .status { 
                    display: inline-block;
                    padding: 5px 10px;
                    border-radius: 3px;
                    font-weight: bold;
                    margin-left: 10px;
                }
                .status.connected { background: #4CAF50; }
                .status.disconnected { background: #f44336; }
                .badge { 
                    background: #2196F3;
                    padding: 2px 8px;
                    border-radius: 3px;
                    font-size: 12px;
                    font-weight: bold;
                }
            </style>
        </head>
        <body>
            <h1>🪙 Crypto Price WebSocket Test <span class="badge">Pub/Sub Mode</span></h1>
            <p>Event-driven updates via Redis Pub/Sub (no polling!)</p>
            <p>Status: <span class="status disconnected" id="status">Disconnected</span></p>
            <div>
                <button onclick="connectBTC()">Connect BTC</button>
                <button onclick="connectETH()">Connect ETH</button>
                <button onclick="connectAll()">Connect ALL</button>
                <button onclick="sendPing()">Send Ping</button>
                <button class="disconnect" onclick="disconnect()">Disconnect</button>
                <button onclick="clearMessages()">Clear Messages</button>
            </div>
            <div id="messages"></div>
            
            <script>
                let ws = null;
                let messageCount = 0;
                
                function updateStatus(connected) {
                    const status = document.getElementById('status');
                    if (connected) {
                        status.textContent = 'Connected';
                        status.className = 'status connected';
                    } else {
                        status.textContent = 'Disconnected';
                        status.className = 'status disconnected';
                    }
                }
                
                function connectBTC() { connect('BTC'); }
                function connectETH() { connect('ETH'); }
                function connectAll() { connect('ALL'); }
                
                function connect(symbol) {
                    if (ws) ws.close();
                    
                    ws = new WebSocket(`ws://localhost:8000/ws/prices/${symbol}`);
                    
                    ws.onopen = () => {
                        updateStatus(true);
                        addMessage('✅ Connected to ' + symbol + ' stream (Pub/Sub mode)', 'connection');
                    };
                    
                    ws.onmessage = (event) => {
                        const data = JSON.parse(event.data);
                        messageCount++;
                        
                        let className = 'message';
                        if (data.type === 'connection') className += ' connection';
                        else if (data.type === 'initial_data') className += ' initial';
                        else if (data.type === 'error') className += ' error';
                        
                        addMessage(`[${messageCount}] ${JSON.stringify(data, null, 2)}`, className);
                    };
                    
                    ws.onerror = (error) => {
                        addMessage('❌ Error: ' + error, 'error');
                    };
                    
                    ws.onclose = () => {
                        updateStatus(false);
                        addMessage('❌ Disconnected', 'connection');
                    };
                }
                
                function sendPing() {
                    if (ws && ws.readyState === WebSocket.OPEN) {
                        ws.send(JSON.stringify({type: 'ping'}));
                        addMessage('📤 Sent ping', 'connection');
                    } else {
                        alert('Not connected!');
                    }
                }
                
                function disconnect() {
                    if (ws) {
                        ws.close();
                        ws = null;
                    }
                }
                
                function clearMessages() {
                    document.getElementById('messages').innerHTML = '';
                    messageCount = 0;
                }
                
                function addMessage(msg, className = 'message') {
                    const div = document.createElement('div');
                    div.className = className;
                    div.innerHTML = '<strong>' + new Date().toLocaleTimeString() + '</strong><br>' + 
                                    '<pre>' + msg + '</pre>';
                    const container = document.getElementById('messages');
                    container.appendChild(div);
                    container.scrollTop = container.scrollHeight;
                }
            </script>
        </body>
    </html>
    """
    from fastapi.responses import HTMLResponse
    return HTMLResponse(content=html_content)


@router.get("/ws/stats")
async def websocket_stats():
    """
    Get WebSocket connection statistics
    """
    return {
        "total_connections": manager.total_connections,
        "connections_by_symbol": {
            symbol: len(connections) 
            for symbol, connections in manager.connections.items()
        },
        "pubsub_active": pubsub_manager.is_running,
        "mode": "event_driven_pubsub"
    }
