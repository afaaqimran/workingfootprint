import websocket
import threading
import json
import ssl
import time
import uuid
import requests
import MarketDataFeed_pb2 as pb
from google.protobuf.json_format import MessageToDict

# Patch websocket-client to use the real (non-eventlet) socket
# This is needed because eventlet.monkey_patch() replaces the socket module
# which breaks websocket-client's SSL connections (EHOSTUNREACH)
try:
    import eventlet.patcher as _ep
    _real_socket = _ep.original('socket')
    import websocket._http as _ws_http
    import websocket._socket as _ws_sock
    _ws_http.socket = _real_socket
    _ws_sock.socket = _real_socket
except Exception:
    pass

class UpstoxWebSocketV3:
    def __init__(self, access_token, on_data_callback=None, on_error_callback=None):
        self.access_token = access_token
        self.on_data_callback = on_data_callback
        self.on_error_callback = on_error_callback
        self.ws = None
        self.thread = None
        self.stop_event = threading.Event()
        self.subscribed_instruments = set()
        self.current_mode = "full"  # Default to full mode
        self.session = requests.Session()  # Use session for cookies
        
    def get_authorized_url(self):
        """Get the authorized WebSocket URL"""
        url = "https://api.upstox.com/v3/feed/market-data-feed/authorize"
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/json",
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Connection": "keep-alive",
            "Sec-Fetch-Dest": "document",
            "Sec-Fetch-Mode": "navigate",
            "Sec-Fetch-Site": "none"
        }
        
        try:
            response = self.session.get(url, headers=headers, timeout=10)
            print(f"🔑 Auth response: {response.status_code} — {response.text[:300]}")
            if response.status_code == 200:
                data = response.json()
                if data.get("status") == "success":
                    ws_url = data["data"]["authorized_redirect_uri"]
                    print(f"✅ Got WS URL: {ws_url[:60]}...")
                    return ws_url
                print(f"❌ Auth status not success: {data}")
                return None
            elif response.status_code == 401:
                print(f"❌ Access token expired or invalid — please re-login")
                self.stop_event.set()  # Stop retrying on auth failure
                return None
            print(f"❌ API Error {response.status_code}: {response.text[:200]}")
            return None
        except Exception as e:
            print(f"❌ Connection error: {e}")
            return None

    def connect(self):
        """Start the WebSocket connection in a separate thread"""
        if self.thread and self.thread.is_alive():
            return

        self.stop_event.clear()
        self.thread = threading.Thread(target=self._connection_loop)
        self.thread.daemon = True
        self.thread.start()

    def _connection_loop(self):
        """Internal loop to handle connection and auto-reconnection"""
        self.reconnect_delay = 1
        
        while not self.stop_event.is_set():
            try:
                ws_url = self.get_authorized_url()
                if not ws_url:
                    print(f"⚠️ Failed to get URL, retrying in {self.reconnect_delay}s...")
                    time.sleep(self.reconnect_delay)
                    self.reconnect_delay = min(self.reconnect_delay * 2, 60)
                    continue

                print(f"🔗 (Re)Connecting to Upstox WebSocket...")
                
                self.ws = websocket.WebSocketApp(
                    ws_url,
                    on_open=self.on_open,
                    on_message=self.on_message,
                    on_error=self.on_error,
                    on_close=self.on_close
                )
                
                # run_forever blocks until the connection is closed
                self.ws.run_forever(sslopt={"cert_reqs": ssl.CERT_NONE})
                
            except Exception as e:
                print(f"❌ Critical error in connection loop: {e}")
            
            # If we get here, the connection has closed
            if not self.stop_event.is_set():
                print(f"⚠️ Connection lost. Reconnecting in {self.reconnect_delay}s...")
                time.sleep(self.reconnect_delay)
                self.reconnect_delay = min(self.reconnect_delay * 2, 60)
            else:
                print("🛑 WebSocket loop stopped by user")

    def subscribe(self, instrument_keys, mode="full"):
        """Subscribe to instruments"""
        self.subscribed_instruments.update(instrument_keys)
        self.current_mode = mode
        
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            print("⚠️ WebSocket not connected, subscription queued")
            return
        
        try:
            request = {
                "guid": str(uuid.uuid4()),
                "method": "sub",
                "data": {
                    "mode": mode,
                    "instrumentKeys": list(instrument_keys)
                }
            }
            
            # Send as binary (UTF-8 encoded JSON)
            self.ws.send(json.dumps(request).encode('utf-8'), opcode=websocket.ABNF.OPCODE_BINARY)
            print(f"📤 Subscribed to {len(instrument_keys)} instruments in {mode} mode")
        except Exception as e:
            print(f"❌ Error during subscription: {e}")

    def unsubscribe(self, instrument_keys):
        """Unsubscribe from instruments"""
        self.subscribed_instruments -= set(instrument_keys)
        if not self.ws or not self.ws.sock or not self.ws.sock.connected:
            return
        try:
            request = {
                "guid": str(uuid.uuid4()),
                "method": "unsub",
                "data": {"instrumentKeys": list(instrument_keys)}
            }
            self.ws.send(json.dumps(request).encode('utf-8'), opcode=websocket.ABNF.OPCODE_BINARY)
            print(f"📤 Unsubscribed {len(instrument_keys)} instruments")
        except Exception as e:
            print(f"❌ Error during unsubscription: {e}")

    def on_open(self, ws):
        print("✅ WebSocket Connected")
        self.reconnect_delay = 1  # Reset backoff on successful connection
        
        # Resubscribe if we have pending instruments
        if self.subscribed_instruments:
            # Small delay to ensure connection is stable
            time.sleep(0.5)
            self.subscribe(self.subscribed_instruments, self.current_mode)

    def on_message(self, ws, message):
        """Handle incoming messages (Protobuf)"""
        try:
            # Decode Protobuf message
            feed_response = pb.FeedResponse()
            feed_response.ParseFromString(message)
            
            # Convert to dict for easier handling
            data = MessageToDict(feed_response)
            
            # Handle different message types
            if data.get('type') == 'market_info':
                # Initial market status
                pass
            elif data.get('type') in ['initial_feed', 'live_feed']:
                # Process feeds
                if self.on_data_callback:
                    self.on_data_callback(data)
                    
        except Exception as e:
            print(f"❌ Error processing message: {e}")

    def on_error(self, ws, error):
        print(f"❌ WebSocket Error: {error}")
        if self.on_error_callback:
            # Don't propagate every error up to kill the app, just log it
            # self.on_error_callback(error)
            pass

    def on_close(self, ws, close_status_code, close_msg):
        print(f"🔌 WebSocket Closed: {close_status_code} - {close_msg}")

    def disconnect(self):
        print("🛑 Disconnecting WebSocket...")
        self.stop_event.set()
        if self.ws:
            self.ws.close()
        if self.thread and self.thread.is_alive():
            self.thread.join(timeout=2)
