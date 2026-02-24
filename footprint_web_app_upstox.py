from flask import Flask, render_template, request, jsonify, session, redirect, url_for
import requests
import json
import os
from datetime import datetime, timedelta
import threading
import time
from flask_socketio import SocketIO, emit, join_room, leave_room
import sqlite3
from instrument_manager import InstrumentManager
from upstox_websocket_v3 import UpstoxWebSocketV3

# Footprint Processing Logic
class FootprintProcessor:
    def __init__(self):
        self.price_levels = {}  # price -> {buy_qty, sell_qty, total_qty}
        self.tick_size = 0.25
        self.lot_size = 75
        self.prev_depth = {'buy': [], 'sell': []}  # Store previous depth for comparison
        
    def round_to_tick(self, price):
        return round(price / self.tick_size) * self.tick_size
    
    def process_intrabar_footprint(self, price, volume_diff, open_price, prev_close, prev_category):
        """
        Process footprint using standard Intrabar logic:
        - Close > Open: Buy
        - Close < Open: Sell
        - Close == Open: Compare with Previous Close
        """
        if volume_diff <= 0:
            return [], prev_category
            
        # Determine Category
        category = prev_category # Default to previous
        
        if price > open_price:
            category = 'buy'
        elif price < open_price:
            category = 'sell'
        else:
            # Doji (Price == Open)
            if price > prev_close:
                category = 'buy'
            elif price < prev_close:
                category = 'sell'
            else:
                category = prev_category # Unchanged
                
        # Create Footprint Level
        buy_qty = 0
        sell_qty = 0
        
        if category == 'buy':
            buy_qty = volume_diff
        else:
            sell_qty = volume_diff
            
        return [{
            'price': self.round_to_tick(price),
            'buy_qty': buy_qty,
            'sell_qty': sell_qty,
            'total_qty': volume_diff
        }], category
    

        
    def process_depth_update(self, ltp, buy_diff, sell_diff):
        """Legacy method for backward compatibility"""
        if buy_diff <= 0 and sell_diff <= 0:
            return None
            
        price = self.round_to_tick(ltp)
        
        return {
            'price': price,
            'buy_qty': buy_diff,
            'sell_qty': sell_diff,
            'total_qty': buy_diff + sell_diff,
            'imbalance': (buy_diff - sell_diff) / (buy_diff + sell_diff) if (buy_diff + sell_diff) > 0 else 0
        }
    def clear(self):
        pass

def resample_data(flat_data, target_timeframe_min):
    """
    Resample flattened 1-minute data to target timeframe.
    Input: List of dicts, where each dict is a candle + optional single footprint_level.
    Output: Flattened list of aggregated candles + footprint levels.
    """
    if not flat_data:
        return []
        
    try:
        target_tf = int(target_timeframe_min)
        if target_tf <= 1:
            return flat_data
    except:
        return flat_data

    # 1. Group flattened items by 1m Timestamp
    # timestamp -> { 'ohlc': dict, 'levels': { price: {buy, sell} } }
    candles_1m = {}
    
    for item in flat_data:
        ts = int(item['timestamp'])
        if ts not in candles_1m:
            candles_1m[ts] = {
                'ohlc': item, # Keep first item as base for OHLC
                'levels': {}
            }
        
        # Aggregate logic for OHLC (though all items for same TS *should* be identical for OHLC)
        # We trust the first item for OHLC as per get_stored_data logic
        
        # Accumulate Footprint Level
        if 'footprint_level' in item and item['footprint_level']:
            fp = item['footprint_level']
            price = fp['price']
            if price not in candles_1m[ts]['levels']:
                candles_1m[ts]['levels'][price] = {'buy': 0, 'sell': 0}
            
            candles_1m[ts]['levels'][price]['buy'] += fp.get('buy_qty', 0)
            candles_1m[ts]['levels'][price]['sell'] += fp.get('sell_qty', 0)

    # 2. Sort 1m candles by time
    sorted_ts = sorted(candles_1m.keys())
    
    # 3. Aggregate 1m candles into Target Timeframe Buckets
    resampled_flat_list = []
    
    timeframe_ms = target_tf * 60 * 1000
    current_bucket_ts = None
    bucket_1m_candles = []
    
    def process_bucket(bucket_ts, candles_list):
        if not candles_list:
            return
            
        # Init Aggregated Candle
        first_1m = candles_list[0]
        base_ohlc = first_1m['ohlc']
        last_1m = candles_list[-1]
        last_ohlc = last_1m['ohlc']
        
        agg_ohlc = {
            'timestamp': bucket_ts,
            'symbol': base_ohlc['symbol'],
            'open': base_ohlc['open'],
            'high': max(c['ohlc']['high'] for c in candles_list),
            'low': min(c['ohlc']['low'] for c in candles_list),
            'close': last_ohlc['close'],
            'ltp': last_ohlc['ltp'],
            'volume': sum(c['ohlc']['volume_diff'] for c in candles_list), # Using volume_diff sum for period volume
            'volume_diff': sum(c['ohlc']['volume_diff'] for c in candles_list),
            'timeframe': str(target_tf),
            'historical': True
        }
        
        # Merge Levels
        agg_levels = {}
        for c in candles_list:
            for price, qty in c['levels'].items():
                if price not in agg_levels:
                    agg_levels[price] = {'buy': 0, 'sell': 0}
                agg_levels[price]['buy'] += qty['buy']
                agg_levels[price]['sell'] += qty['sell']
        
        # 4. Flatten and Convert to Output Format
        has_levels = False
        for price, qty in agg_levels.items():
            has_levels = True
            row = agg_ohlc.copy()
            row['footprint_level'] = {
                'price': price,
                'buy_qty': qty['buy'],
                'sell_qty': qty['sell'],
                'total_qty': qty['buy'] + qty['sell']
            }
            resampled_flat_list.append(row)
            
        # If no levels (empty candle), output just the OHLC
        if not has_levels:
            resampled_flat_list.append(agg_ohlc)


    # Iterate through sorted 1m timestamps
    for ts in sorted_ts:
        bucket_ts = (ts // timeframe_ms) * timeframe_ms
        
        if current_bucket_ts is not None and bucket_ts != current_bucket_ts:
            process_bucket(current_bucket_ts, bucket_1m_candles)
            bucket_1m_candles = []
            
        current_bucket_ts = bucket_ts
        bucket_1m_candles.append(candles_1m[ts])
        
    # Process last bucket
    if bucket_1m_candles:
        process_bucket(current_bucket_ts, bucket_1m_candles)
        
    return resampled_flat_list


# Data Storage for 25-day persistence
class DataStorage:
    def __init__(self, db_path='footprint_data.db'):
        self.db_path = db_path
        self.initialized_dbs = set()
        self.cleanup_old_data()
    
    def get_db_path(self, symbol):
        """Get database path based on symbol"""
        if 'BANKNIFTY' in symbol:
            return 'footprint_data_BANKNIFTY.db'
        elif 'NIFTY' in symbol:
            return 'footprint_data_NIFTY.db'
        else:
            return self.db_path

    def init_database(self, symbol=None):
        """Initialize database tables for a specific db or default"""
        target_db = self.get_db_path(symbol) if symbol else self.db_path
        
        if target_db in self.initialized_dbs:
            return

        conn = sqlite3.connect(target_db)
        cursor = conn.cursor()
        
        # Create candles table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS candles (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                open REAL NOT NULL,
                high REAL NOT NULL,
                low REAL NOT NULL,
                close REAL NOT NULL,
                ltp REAL NOT NULL,
                volume INTEGER NOT NULL,
                volume_diff INTEGER NOT NULL,
                timeframe TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                UNIQUE(timestamp, symbol, timeframe)
            )
        ''')
        
        # Create footprint_levels table
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS footprint_levels (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                candle_timestamp TEXT NOT NULL,
                symbol TEXT NOT NULL,
                price REAL NOT NULL,
                buy_qty INTEGER NOT NULL,
                sell_qty INTEGER NOT NULL,
                total_qty INTEGER NOT NULL,
                timeframe TEXT NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        
        # Create indexes for faster queries
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_candles_timestamp 
            ON candles(timestamp, symbol, timeframe)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_candles_created 
            ON candles(created_at)
        ''')
        cursor.execute('''
            CREATE INDEX IF NOT EXISTS idx_footprint_timestamp 
            ON footprint_levels(candle_timestamp, symbol, timeframe)
        ''')
        
        conn.commit()
        conn.close()
        self.initialized_dbs.add(target_db)
        print(f"✅ Database initialized: {target_db}")
    
    def cleanup_old_data(self):
        """Remove data older than 180 days from all DBs"""
        for db_file in ['footprint_data_NIFTY.db', 'footprint_data_BANKNIFTY.db']:
            if not os.path.exists(db_file):
                continue
                
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
        
            # Calculate cutoff date (180 days ago)
            cutoff_date = datetime.now() - timedelta(days=180)
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            cursor.execute('DELETE FROM candles WHERE created_at < ?', (cutoff_str,))
            deleted_candles = cursor.rowcount
            
            cursor.execute('DELETE FROM footprint_levels WHERE created_at < ?', (cutoff_str,))
            deleted_levels = cursor.rowcount
            
            conn.commit()
            conn.close()
            
            if deleted_candles > 0 or deleted_levels > 0:
                print(f"🧹 Cleaned up old data: {deleted_candles} candles, {deleted_levels} footprint levels")
    
    def store_candle(self, candle_data, timeframe='1'):
        """Store candle and footprint data"""
        try:
            target_db = self.get_db_path(candle_data['symbol'])
            self.init_database(candle_data['symbol']) # Ensure DB exists
            
            conn = sqlite3.connect(target_db)
            cursor = conn.cursor()
            
            # Insert or replace candle
            cursor.execute('''
                INSERT OR REPLACE INTO candles 
                (timestamp, symbol, open, high, low, close, ltp, volume, volume_diff, timeframe)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ''', (
                candle_data['timestamp'],
                candle_data['symbol'],
                candle_data['open'],
                candle_data['high'],
                candle_data['low'],
                candle_data['close'],
                candle_data['ltp'],
                candle_data['volume'],
                candle_data['volume_diff'],
                timeframe
            ))
            
            # Store footprint level if present
            if 'footprint_level' in candle_data:
                level = candle_data['footprint_level']
                cursor.execute('''
                    INSERT INTO footprint_levels 
                    (candle_timestamp, symbol, price, buy_qty, sell_qty, total_qty, timeframe)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                ''', (
                    candle_data['timestamp'],
                    candle_data['symbol'],
                    level['price'],
                    level['buy_qty'],
                    level['sell_qty'],
                    level['total_qty'],
                    timeframe
                ))
            
            conn.commit()
            conn.close()
            
        except Exception as e:
            print(f"Error storing candle: {e}")
    
    def get_stored_data(self, symbol, timeframe='1', days=180):
        """Retrieve stored data for last N days"""
        try:
            target_db = self.get_db_path(symbol)
            if not os.path.exists(target_db):
                return []

            conn = sqlite3.connect(target_db)
            cursor = conn.cursor()
            
            # Calculate cutoff date, skipping weekends
            cutoff_date = datetime.now()
            trading_days = 0
            while trading_days < days:
                cutoff_date -= timedelta(days=1)
                if cutoff_date.weekday() < 5:  # Monday=0, Friday=4
                    trading_days += 1
            cutoff_str = cutoff_date.strftime('%Y-%m-%d %H:%M:%S')
            
            # Single JOIN query to get all data at once
            cursor.execute('''
                SELECT 
                    c.timestamp, c.symbol, c.open, c.high, c.low, c.close, c.ltp, c.volume, c.volume_diff,
                    f.price, f.buy_qty, f.sell_qty, f.total_qty
                FROM candles c
                LEFT JOIN footprint_levels f ON c.timestamp = f.candle_timestamp 
                    AND c.symbol = f.symbol AND c.timeframe = f.timeframe
                WHERE c.symbol = ? AND c.timeframe = ? AND c.created_at >= ?
                ORDER BY c.timestamp ASC, f.id ASC
            ''', (symbol, timeframe, cutoff_str))
            
            rows = cursor.fetchall()
            conn.close()
            
            # Build result
            result = []
            for row in rows:
                candle_data = {
                    'timestamp': row[0],
                    'symbol': row[1],
                    'open': row[2],
                    'high': row[3],
                    'low': row[4],
                    'close': row[5],
                    'ltp': row[6],
                    'volume': row[7],
                    'volume_diff': row[8],
                    'historical': True
                }
                
                # Add footprint level if exists
                if row[9] is not None:
                    candle_data['footprint_level'] = {
                        'price': row[9],
                        'buy_qty': row[10],
                        'sell_qty': row[11],
                        'total_qty': row[12]
                    }
                
                result.append(candle_data)
            
            return result
            
        except Exception as e:
            print(f"Error retrieving stored data: {e}")
            return []

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*")

# Global variables
authenticated_users = {}
live_data = {}
data_storage = DataStorage()  # Initialize persistent storage
instrument_manager = InstrumentManager()  # Initialize instrument manager

# Refresh instrument data on startup (if cache is older than 24 hours)
print("🔄 Checking instrument data...")
instrument_manager.refresh_if_needed(max_age_hours=24)

class UpstoxAPI:
    def __init__(self):
        self.base_url = "https://api.upstox.com"
        self.access_token = None
        self.logged_in = False
        self.footprint_processor = FootprintProcessor()
        self.prev_volume = 0
        self.prev_ltp = 0
        self.prev_close = 0
        self.prev_category = 'buy'
        self.current_minute_candle = None  # Local aggregation cache
        
        # WebSocket Client
        
        # WebSocket Client
        self.ws_client = None
        
        # Get default instrument token
        try:
            contracts = instrument_manager.get_contract_list_for_dropdown()
            nifty_contracts = [c for c in contracts if c['type'] == 'NIFTY']
            if nifty_contracts:
                self.instrument_token = nifty_contracts[0]['instrument_key']
                self.current_symbol = nifty_contracts[0]['symbol']
                print(f"✅ Default instrument: {nifty_contracts[0]['display_name']} ({self.instrument_token})")
            else:
                self.instrument_token = "NSE_FO|37054"
                print(f"⚠️ Using fallback instrument token: {self.instrument_token}")
        except Exception as e:
            self.instrument_token = "NSE_FO|37054"
            print(f"⚠️ Error getting default instrument: {e}, using fallback")
        
        self.current_timeframe = '3'
        self.user_id = None
        if not hasattr(self, 'current_symbol'):
            self.current_symbol = 'NIFTY_DEC'  # Fallback only if init failed
        
    def login(self, api_key, api_secret, access_token):
        try:
            self.access_token = access_token
            # Verify token
            headers = {'Authorization': f'Bearer {access_token}', 'Accept': 'application/json'}
            response = requests.get(f"{self.base_url}/v2/user/profile", headers=headers)
            
            if response.status_code == 200:
                self.logged_in = True
                return {'success': True, 'message': 'Login successful'}
            else:
                return {'success': False, 'message': 'Invalid access token'}
        except Exception as e:
            return {'success': False, 'message': str(e)}

    def start_data_polling(self, user_id, timeframe='3'):
        """Start WebSocket connection instead of polling"""
        self.user_id = user_id
        self.current_timeframe = timeframe
        
        if self.ws_client:
            self.ws_client.disconnect()
            
        print(f"🔄 Starting WebSocket for {user_id}...")
        self.ws_client = UpstoxWebSocketV3(
            access_token=self.access_token,
            on_data_callback=self.process_websocket_data,
            on_error_callback=self.on_ws_error
        )
        self.ws_client.connect()
        
        # Wait for connection then subscribe
        time.sleep(1)
        self.ws_client.subscribe({self.instrument_token}, mode="full")
        print("📡 Started Upstox WebSocket V3")

    def process_websocket_data(self, data):
        """Process incoming WebSocket data"""
        try:
            feeds = data.get('feeds', {})
            current_ts = int(data.get('currentTs', time.time() * 1000))
            
            for instrument_key, feed_data in feeds.items():
                if instrument_key != self.instrument_token:
                    continue
                    
                full_feed = feed_data.get('fullFeed', {}).get('marketFF', {})
                if not full_feed:
                    continue
                
                # Extract Data
                ltpc = full_feed.get('ltpc', {})
                market_level = full_feed.get('marketLevel', {})
                market_ohlc = full_feed.get('marketOHLC', {})
                
                ltp = ltpc.get('ltp', 0)
                vtt = int(full_feed.get('vtt', 0))  # Volume Traded Today
                
                # Pure LTP-Based Candle Construction
                # Timestamp flooring to configured timeframe (in minutes) to group ticks
                timeframe_ms = int(self.current_timeframe) * 60000  # Convert minutes to milliseconds
                candle_ts = int(current_ts // timeframe_ms) * timeframe_ms
                
                # Check if we're in the same candle period or starting a new one
                if self.current_minute_candle and abs(self.current_minute_candle['ts'] - candle_ts) < 1000:
                    # Same minute - update High/Low/Close
                    self.current_minute_candle['high'] = max(self.current_minute_candle['high'], ltp)
                    self.current_minute_candle['low'] = min(self.current_minute_candle['low'], ltp)
                    self.current_minute_candle['close'] = ltp
                    # Open remains unchanged (first tick of the minute)
                else:
                    # New candle period - create fresh candle
                    self.current_minute_candle = {
                        'open': ltp,   # First tick = Open
                        'high': ltp,   # Will expand as we see higher prices
                        'low': ltp,    # Will contract as we see lower prices
                        'close': ltp,  # Current price
                        'vol': 0,
                        'ts': candle_ts
                    }
                
                current_ohlc = self.current_minute_candle
                
                # Prepare Depth Data
                depth_data = {'buy': [], 'sell': []}
                quotes = market_level.get('bidAskQuote', [])
                for q in quotes:
                    depth_data['buy'].append({'price': q.get('bidP', 0), 'quantity': int(q.get('bidQ', 0))})
                    depth_data['sell'].append({'price': q.get('askP', 0), 'quantity': int(q.get('askQ', 0))})
                
                # Calculate Volume Diff (using VTT for robustness)
                if self.prev_volume == 0:
                    self.prev_volume = vtt
                    volume_diff = 0
                    print(f"📊 Initializing: LTP:{ltp} VTT:{vtt}")
                else:
                    volume_diff = max(0, vtt - self.prev_volume)
                    self.prev_volume = vtt
                
                # Process Footprint
                footprint_levels = []
                if volume_diff > 0:
                    # Ensure lot size compliance
                    volume_diff = (volume_diff // self.footprint_processor.lot_size) * self.footprint_processor.lot_size
                    
                    if volume_diff > 0:
                        footprint_levels, new_category = self.footprint_processor.process_intrabar_footprint(
                            price=ltp,
                            volume_diff=volume_diff,
                            open_price=current_ohlc.get('open', ltp),
                            prev_close=self.prev_close,
                            prev_category=self.prev_category
                        )
                        self.prev_category = new_category
                
                # Prepare Candle Update
                candle_timestamp = int(current_ohlc.get('ts', current_ts))
                
                # Validate timestamp
                current_time_ms = int(time.time() * 1000)
                if candle_timestamp > current_time_ms + (60 * 60 * 1000):
                    candle_timestamp = current_time_ms

                base_update = {
                    'symbol': self.current_symbol,
                    'timestamp': candle_timestamp,
                    'open': current_ohlc.get('open', ltp),
                    'high': current_ohlc.get('high', ltp),
                    'low': current_ohlc.get('low', ltp),
                    'close': current_ohlc.get('close', ltp),
                    'ltp': ltp,
                    'volume': vtt,
                    'volume_diff': volume_diff,
                    'historical': False
                }
                
                # Emit Data
                if footprint_levels:
                    for level in footprint_levels:
                        update = base_update.copy()
                        update['footprint_level'] = level
                        socketio.emit('ohlc_data', update, room=self.user_id)
                        data_storage.store_candle(update, '1')  # Always store as 1-min
                else:
                    socketio.emit('ohlc_data', base_update, room=self.user_id)
                    data_storage.store_candle(base_update, '1')  # Always store as 1-min
                
                # Update previous values
                self.prev_ltp = ltp
                self.prev_close = current_ohlc.get('close', ltp)
                
        except Exception as e:
            print(f"❌ Error processing WS data: {e}")

    def on_ws_error(self, error):
        print(f"❌ WebSocket Error Callback: {error}")

@app.route('/favicon.ico')
def favicon():
    return '', 204

@app.route('/')
def index():
    if 'user_id' in session and session['user_id'] in authenticated_users:
        return render_template('chart.html')
    return render_template('login_upstox.html')

@app.route('/login', methods=['POST'])
def login():
    data = request.json
    
    upstox = UpstoxAPI()
    result = upstox.login(
        api_key=data.get('api_key'),
        api_secret=data.get('api_secret'),
        access_token=data.get('access_token')
    )
    
    if result['success']:
        user_id = data.get('api_key')  # Use API key as user ID
        session['user_id'] = user_id
        authenticated_users[user_id] = upstox
        
        # Start data polling for live data (default 3-minute)
        upstox.start_data_polling(user_id, '3')
        
        return jsonify(result)
    
    return jsonify(result), 401

@app.route('/api/current-user')
def current_user():
    if 'user_id' in session and session['user_id'] in authenticated_users:
        return jsonify({'success': True, 'user': session['user_id']})
    return jsonify({'success': False}), 401

@app.route('/api/user-symbols')
def user_symbols():
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401
    
    try:
        # Get dynamic contract list from instrument manager
        contracts = instrument_manager.get_contract_list_for_dropdown()
        
        return jsonify({
            'success': True, 
            'data': contracts,
            'plan_type': 'Live Upstox Data',
            'message': f'Loaded {len(contracts)} active futures contracts'
        })
    except Exception as e:
        print(f"Error getting contracts: {e}")
        # Fallback to static list if there's an error
        return jsonify({
            'success': True, 
            'data': [],
            'plan_type': 'Live Upstox Data',
            'message': 'Error loading contracts'
        })

@app.route('/api/live-data')
def get_live_data():
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401
    
    user_id = session['user_id']
    if user_id in live_data:
        return jsonify({'success': True, 'data': live_data[user_id]})
    
    return jsonify({'success': False, 'message': 'No live data available'})

@app.route('/api/stored-data')
def get_stored_data():
    """Retrieve stored data from database for last 180 days"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    # Get query parameters
    symbol = request.args.get('symbol', 'NIFTY_DEC')
    timeframe = request.args.get('timeframe', '1')
    days = int(request.args.get('days', 180))
    
    try:
        # 1. Always fetch 1-minute data from DB
        # The DB *only* stores 1-minute data now.
        raw_data = data_storage.get_stored_data(symbol, timeframe='1', days=days)
        print(f"🔍 Raw data count: {len(raw_data)}")
        if raw_data:
            print(f"🔍 First raw item timestamp: {raw_data[0].get('timestamp')}")
            print(f"🔍 Last raw item timestamp: {raw_data[-1].get('timestamp')}")
        
        # 2. Resample if needed
        if timeframe != '1':
            stored_data = resample_data(raw_data, timeframe)
            print(f"🔍 Resampled data count: {len(stored_data)}")
        else:
            stored_data = raw_data
            
        return jsonify({
            'success': True,
            'data': stored_data,
            'count': len(stored_data)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

@socketio.on('connect')
def handle_connect():
    print("🚨 WEBSOCKET CONNECT ATTEMPT")
    if 'user_id' in session:
        join_room(session['user_id'])
        user_id = session['user_id']
        print(f"🚨 USER {user_id} AUTHENTICATED")
        print(f"User {user_id} connected to WebSocket")
    else:
        print("🚨 NO USER_ID IN SESSION")

@socketio.on('disconnect')
def handle_disconnect():
    if 'user_id' in session:
        leave_room(session['user_id'])
        print(f"User {session['user_id']} disconnected from WebSocket")

@app.route('/api/change-instrument', methods=['POST'])
def change_instrument():
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    symbol = data.get('symbol', 'NIFTY_NOV')
    instrument_token = data.get('instrument_token', 'NSE_FO|50971')
    lot_size = data.get('lot_size', 75)  # Get lot size from request
    
    user_id = session['user_id']
    upstox = authenticated_users[user_id]
    
    try:
        # Update instrument token and symbol
        upstox.instrument_token = instrument_token
        upstox.current_symbol = symbol
        
        # Update lot size for footprint processor
        # Ensure we have a valid integer
        try:
            new_lot_size = int(lot_size)
            if new_lot_size > 0:
                upstox.footprint_processor.lot_size = new_lot_size
                print(f"✅ Updated lot size to {new_lot_size} for {symbol}")
            else:
                print(f"⚠️ Invalid lot size {lot_size}, keeping {upstox.footprint_processor.lot_size}")
        except Exception as e:
            print(f"❌ Error updating lot size: {e}")
            
        # Reset volume tracking and candle state for new instrument
        upstox.prev_volume = 0
        upstox.prev_ltp = 0
        upstox.prev_close = 0
        upstox.prev_category = 'buy'
        upstox.current_minute_candle = None
        
        # Subscribe to new instrument
        if upstox.ws_client:
            upstox.ws_client.subscribe({instrument_token}, mode="full")
        
        return jsonify({'success': True, 'message': f'Switched to {symbol}'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/api/change-timeframe', methods=['POST'])
def change_timeframe():
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'error': 'Not authenticated'}), 401
    
    data = request.json
    timeframe = data.get('timeframe', '1')
    user_id = session['user_id']
    upstox = authenticated_users[user_id]
    
    try:
        # Update timeframe and reset tracking
        upstox.current_timeframe = timeframe
        upstox.prev_volume = 0
        upstox.current_minute_candle = None
        
        return jsonify({'success': True, 'message': f'Switched to {timeframe}min timeframe'})
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)})

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        if user_id in authenticated_users:
            upstox = authenticated_users[user_id]
            upstox.logged_in = False
            del authenticated_users[user_id]
        if user_id in live_data:
            del live_data[user_id]
        session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    socketio.run(app, debug=True, host='0.0.0.0', port=5001, allow_unsafe_werkzeug=True)
