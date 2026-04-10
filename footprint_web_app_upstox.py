import eventlet
eventlet.monkey_patch()

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
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25, async_mode='eventlet')

# Analytics token (1-year validity, read-only, no OAuth redirect needed)
ANALYTICS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBVjYwMDEiLCJqdGkiOiI2OWJlNzhiZTg3YTgwYjEzMWJkZTg0MWMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlzRXh0ZW5kZWQiOnRydWUsImlhdCI6MTc3NDA5MDQzMCwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxODA1NjY2NDAwfQ.edEAi8hh4gU63ceOAK_Kqfww786nI0zO8LP-7kLm9pQ"

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

        # Options real-time cache: instrument_key -> {ltp, atp, open, high, low, cp, oi}
        self.options_cache = {}
        self.options_instrument_keys = set()  # currently subscribed option keys
        self.options_meta = []  # [{strike, type, label, instrument_key}, ...]
        self.nifty_spot_ltp = 0  # NIFTY 50 index spot price for ATM calculation
        # OI history for change tracking: instrument_key -> [(timestamp_ms, oi), ...]
        self.oi_history = {}

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
        
    def login(self, api_key=None, api_secret=None, access_token=None):
        try:
            # Use analytics token (long-lived, no OAuth redirect needed)
            self.access_token = ANALYTICS_TOKEN
            # Verify token works against market data feed authorize endpoint
            headers = {'Authorization': f'Bearer {self.access_token}', 'Accept': 'application/json'}
            response = requests.get(f"{self.base_url}/v3/feed/market-data-feed/authorize", headers=headers)
            if response.status_code == 200:
                self.logged_in = True
                # Check analytics token expiry (expires 21 Mar 2027)
                expiry = datetime(2027, 3, 21)
                days_left = (expiry - datetime.now()).days
                warning = None
                if days_left <= 10:
                    warning = f'⚠️ Analytics token expires in {days_left} day(s) on 21 Mar 2027. Please regenerate it.'
                return {'success': True, 'message': 'Login successful', 'warning': warning}
            else:
                return {'success': False, 'message': f'Token verification failed: {response.status_code}'}
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
        
        # Wait for connection then subscribe futures instrument
        time.sleep(1)
        self.ws_client.subscribe({self.instrument_token}, mode="full")
        # Also subscribe NIFTY 50 spot index for accurate ATM strike calculation
        self.ws_client.subscribe({'NSE_INDEX|Nifty 50'}, mode="ltpc")
        print("📡 Started Upstox WebSocket V3")

        # Subscribe NIFTY options strikes in background
        threading.Thread(target=self.subscribe_options_strikes, daemon=True).start()
        # Start ATM monitor — re-subscribes when spot moves by 1 strike
        threading.Thread(target=self._atm_monitor, daemon=True).start()

    def subscribe_options_strikes(self, nifty_ltp=None):
        """
        Resolve ATM/ITM NIFTY option strikes and subscribe them on the existing WebSocket.
        Uses full mode so we get LTP, ATP, OHLC in every tick.
        Called once after login and again whenever the futures instrument changes.
        """
        try:
            # Wait up to 5s for NIFTY spot to arrive before calculating ATM
            if not nifty_ltp:
                for _ in range(10):
                    if self.nifty_spot_ltp > 0:
                        break
                    time.sleep(0.5)
                if self.nifty_spot_ltp == 0:
                    print("⚠️ NIFTY spot not yet available, falling back to futures LTP")
            if not instrument_manager.instruments:
                instrument_manager.load_cached_instruments()

            today = datetime.now().date()
            strike_step = 50

            # Determine ATM from NIFTY spot LTP, fallback to futures LTP, then median strike
            atm_ltp = nifty_ltp or self.nifty_spot_ltp or self.prev_ltp
            options = [
                inst for inst in instrument_manager.instruments
                if inst.get('segment') == 'NSE_FO'
                and inst.get('instrument_type') in ('CE', 'PE')
                and inst.get('name') == 'NIFTY'
            ]

            valid_options = []
            for opt in options:
                try:
                    expiry_val = opt.get('expiry')
                    if expiry_val:
                        expiry_date = (datetime.fromtimestamp(expiry_val / 1000).date()
                                       if isinstance(expiry_val, (int, float))
                                       else datetime.strptime(str(expiry_val), '%Y-%m-%d').date())
                        if expiry_date >= today:
                            opt['expiry_date'] = expiry_date
                            valid_options.append(opt)
                except Exception:
                    continue

            if not valid_options:
                print("⚠️ No valid NIFTY options found for subscription")
                return

            nearest_expiry = min(o['expiry_date'] for o in valid_options)
            expiry_options = [o for o in valid_options if o['expiry_date'] == nearest_expiry]

            if atm_ltp > 0:
                atm_strike = round(atm_ltp / strike_step) * strike_step
            else:
                strikes = sorted(set(float(o.get('strike_price', 0)) for o in expiry_options if o.get('strike_price')))
                atm_strike = strikes[len(strikes) // 2] if strikes else 24000

            # 7 strikes above and below ATM — subscribe both CE and PE for each
            all_strikes = [atm_strike + i * strike_step for i in range(-6, 7)]  # ATM-300 to ATM+300

            opt_lookup = {}
            for opt in expiry_options:
                key = (float(opt.get('strike_price', 0)), opt.get('instrument_type'))
                opt_lookup[key] = opt.get('instrument_key')

            new_meta = []
            new_keys = set()

            for strike in all_strikes:
                for opt_type in ('CE', 'PE'):
                    ikey = opt_lookup.get((float(strike), opt_type))
                    if strike < atm_strike:
                        label = f'ATM-{int(atm_strike - strike)}'
                    elif strike > atm_strike:
                        label = f'ATM+{int(strike - atm_strike)}'
                    else:
                        label = 'ATM'
                    new_meta.append({'strike': strike, 'type': opt_type, 'label': label,
                                      'instrument_key': ikey, 'expiry': nearest_expiry.strftime('%d %b %Y')})
                    if ikey:
                        new_keys.add(ikey)

            # Unsubscribe old option keys if they changed
            if self.options_instrument_keys and self.options_instrument_keys != new_keys:
                if self.ws_client:
                    self.ws_client.unsubscribe(self.options_instrument_keys)
                # Do NOT clear cache for dropped keys — retain last known LTP to avoid
                # straddle dips during the re-subscription gap while new ticks arrive

            self.options_meta = new_meta
            self.options_instrument_keys = new_keys

            if new_keys and self.ws_client:
                self.ws_client.subscribe(new_keys, mode="full")
                print(f"📡 Subscribed {len(new_keys)} NIFTY option strikes (ATM={atm_strike}, expiry={nearest_expiry})")

        except Exception as e:
            print(f"❌ Error subscribing options strikes: {e}")

    def _atm_monitor(self):
        """Re-subscribe options whenever ATM strike shifts by 50 pts or expiry rolls over"""
        last_atm = None
        last_subscribed_expiry = None  # track the expiry date we last subscribed
        HYSTERESIS = 15  # spot must move 15 pts past strike boundary before switching ATM
        while True:
            try:
                time.sleep(10)  # check every 10 seconds
                spot = self.nifty_spot_ltp
                if spot <= 0:
                    continue
                current_atm = round(spot / 50) * 50

                # Detect expiry rollover: if today is past the subscribed expiry, re-subscribe
                if self.options_meta:
                    subscribed_expiry_str = self.options_meta[0].get('expiry')
                    if subscribed_expiry_str != last_subscribed_expiry:
                        last_subscribed_expiry = subscribed_expiry_str
                    else:
                        try:
                            subscribed_expiry = datetime.strptime(subscribed_expiry_str, '%d %b %Y').date()
                            if datetime.now().date() > subscribed_expiry:
                                print(f"🔄 Expiry {subscribed_expiry_str} has passed, rolling to next expiry...")
                                self.subscribe_options_strikes(nifty_ltp=spot)
                                last_atm = current_atm
                                continue
                        except Exception:
                            pass

                if last_atm is None:
                    last_atm = current_atm
                    self.subscribe_options_strikes(nifty_ltp=spot)
                    continue
                # Only shift ATM if spot has moved beyond hysteresis buffer
                if current_atm != last_atm:
                    if current_atm > last_atm and spot >= last_atm + 25 + HYSTERESIS:
                        print(f"🔄 ATM shifted {last_atm} → {current_atm}, re-subscribing options...")
                        self.subscribe_options_strikes(nifty_ltp=spot)
                        last_atm = current_atm
                    elif current_atm < last_atm and spot <= last_atm - 25 - HYSTERESIS:
                        print(f"🔄 ATM shifted {last_atm} → {current_atm}, re-subscribing options...")
                        self.subscribe_options_strikes(nifty_ltp=spot)
                        last_atm = current_atm
            except Exception as e:
                print(f"❌ ATM monitor error: {e}")

    def process_websocket_data(self, data):
        """Process incoming WebSocket data"""
        try:
            feeds = data.get('feeds', {})
            current_ts = int(data.get('currentTs', time.time() * 1000))
            
            for instrument_key, feed_data in feeds.items():
                # ── NIFTY spot index LTP ─────────────────────────────
                if instrument_key == 'NSE_INDEX|Nifty 50':
                    ltpc = feed_data.get('ltpc') \
                           or (feed_data.get('fullFeed') or {}).get('indexFF', {}).get('ltpc', {})
                    ltp_val = ltpc.get('ltp', 0) if ltpc else 0
                    if ltp_val:
                        self.nifty_spot_ltp = ltp_val
                    continue

                # ── Options cache update ──────────────────────────────
                if instrument_key in self.options_instrument_keys:
                    full = (feed_data.get('fullFeed') or feed_data.get('ff') or {}).get('marketFF', {})
                    if full:
                        ltpc = full.get('ltpc', {})
                        ohlc_list = full.get('marketOHLC', {}).get('ohlc', [])
                        # Pick the 1-day OHLC entry
                        day_ohlc = next((o for o in ohlc_list if o.get('interval') == '1d'), {})
                        oi_val = int(full.get('oi', 0) or 0)
                        self.options_cache[instrument_key] = {
                            'ltp':    ltpc.get('ltp', 0),
                            'cp':     ltpc.get('cp', 0),
                            'atp':    float(full.get('atp', 0) or 0),
                            'volume': int(full.get('vtt', 0) or 0),
                            'open':   day_ohlc.get('open', 0),
                            'high':   day_ohlc.get('high', 0),
                            'low':    day_ohlc.get('low', 0),
                            'oi':     oi_val,
                            'ts':     current_ts,
                        }
                        # Record OI history for change tracking (keep last 35 min)
                        if oi_val > 0:
                            hist = self.oi_history.setdefault(instrument_key, [])
                            hist.append((current_ts, oi_val))
                            cutoff = current_ts - 35 * 60 * 1000
                            self.oi_history[instrument_key] = [(t, v) for t, v in hist if t >= cutoff]
                    continue  # don't process options as futures candles

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
    upstox = UpstoxAPI()
    result = upstox.login()

    if result['success']:
        user_id = 'analytics_user'
        session['user_id'] = user_id
        # Disconnect existing WebSocket before replacing (Upstox allows only 1 concurrent connection)
        existing = authenticated_users.get(user_id)
        if existing and existing.ws_client:
            existing.ws_client.disconnect()
        authenticated_users[user_id] = upstox
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

        # Re-subscribe options strikes for new instrument context
        threading.Thread(target=upstox.subscribe_options_strikes, daemon=True).start()

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

@app.route('/api/options-chain')
def get_options_chain():
    """Return NIFTY ATM/ITM options data from the live WebSocket cache"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]

    try:
        if not upstox.options_meta:
            # Trigger subscription if not yet done (e.g. first open before first tick)
            threading.Thread(target=upstox.subscribe_options_strikes, daemon=True).start()
            return jsonify({'success': False, 'message': 'Options data loading — please retry in a few seconds'})

        result_rows = []
        atm_strike = None

        for meta in upstox.options_meta:
            if meta['label'] == 'ATM' and atm_strike is None:
                atm_strike = meta['strike']

            ikey = meta.get('instrument_key')
            cached = upstox.options_cache.get(ikey, {}) if ikey else {}

            ltp  = cached.get('ltp', 0)
            atp  = cached.get('atp', 0)
            diff = round(atp - ltp, 2) if (atp and ltp) else None

            result_rows.append({
                'strike':        meta['strike'],
                'type':          meta['type'],
                'label':         meta['label'],
                'ltp':           ltp,
                'atp':           atp,
                'atp_minus_ltp': diff,
                'open':          cached.get('open', 0),
                'high':          cached.get('high', 0),
                'low':           cached.get('low', 0),
                'volume':        cached.get('volume', 0),
            })

        expiry = upstox.options_meta[0].get('expiry', '—') if upstox.options_meta else '—'

        return jsonify({
            'success':    True,
            'atm_strike': atm_strike,
            'nifty_ltp':  upstox.nifty_spot_ltp or upstox.prev_ltp,
            'expiry':     expiry,
            'data':       result_rows
        })

    except Exception as e:
        print(f"❌ Error in options-chain: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/straddle')
def get_straddle():
    """Return straddle premiums (CE+PE LTP) per strike, sorted by strike"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]

    try:
        if not upstox.options_meta:
            threading.Thread(target=upstox.subscribe_options_strikes, daemon=True).start()
            return jsonify({'success': False, 'message': 'Options data loading — retry in a few seconds'})

        # Build strike -> {ce_ltp, pe_ltp} map
        strikes = {}
        for meta in upstox.options_meta:
            strike = meta['strike']
            ikey = meta.get('instrument_key')
            ltp = upstox.options_cache.get(ikey, {}).get('ltp', 0) if ikey else 0
            if strike not in strikes:
                strikes[strike] = {'ce': 0, 'pe': 0}
            if meta['type'] == 'CE':
                strikes[strike]['ce'] = ltp
            else:
                strikes[strike]['pe'] = ltp

        nifty_spot = upstox.nifty_spot_ltp or upstox.prev_ltp
        atm_strike = round(nifty_spot / 50) * 50 if nifty_spot else None

        rows = []
        for strike, ltps in sorted(strikes.items()):
            straddle = round(ltps['ce'] + ltps['pe'], 2)
            rows.append({
                'strike': strike,
                'ce_ltp': ltps['ce'],
                'pe_ltp': ltps['pe'],
                'straddle': straddle,
                'is_atm': strike == atm_strike
            })

        # Find lowest straddle premium
        if rows:
            min_row = min(rows, key=lambda r: r['straddle'] if r['straddle'] > 0 else float('inf'))
            for r in rows:
                r['is_lowest'] = (r['strike'] == min_row['strike'])

        expiry = upstox.options_meta[0].get('expiry', '—') if upstox.options_meta else '—'
        return jsonify({
            'success': True,
            'nifty_spot': nifty_spot,
            'atm_strike': atm_strike,
            'expiry': expiry,
            'data': rows,
            'timestamp': int(time.time() * 1000)
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/oi-tracker')
def get_oi_tracker():
    """Return OI data with change % over 5m/10m/15m/30m intervals for all subscribed options"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]

    try:
        if not upstox.options_meta:
            return jsonify({'success': False, 'message': 'Options data loading — please retry in a few seconds'})

        now_ms = int(time.time() * 1000)
        intervals = [5, 10, 15, 30]
        calls, puts = [], []

        for meta in upstox.options_meta:
            ikey = meta.get('instrument_key')
            cached = upstox.options_cache.get(ikey, {}) if ikey else {}
            oi = cached.get('oi', 0)
            hist = upstox.oi_history.get(ikey, []) if ikey else []

            oi_changes = {}
            for mins in intervals:
                target_ms = now_ms - mins * 60 * 1000
                past = min(hist, key=lambda x: abs(x[0] - target_ms), default=None) if hist else None
                if past and abs(past[0] - target_ms) < 5 * 60 * 1000 and past[1] > 0:
                    pct = round((oi - past[1]) / past[1] * 100, 2)
                else:
                    pct = None
                oi_changes[f'{mins}m'] = pct

            row = {
                'strike':  meta['strike'],
                'type':    meta['type'],
                'label':   meta['label'],
                'ltp':     cached.get('ltp', 0),
                'oi':      oi,
                'volume':  cached.get('volume', 0),
                'oi_chg':  oi_changes,
            }
            if meta['type'] == 'CE':
                calls.append(row)
            else:
                puts.append(row)

        nifty_spot = upstox.nifty_spot_ltp or upstox.prev_ltp
        atm_strike = round(nifty_spot / 50) * 50 if nifty_spot else None
        expiry = upstox.options_meta[0].get('expiry', '—') if upstox.options_meta else '—'

        return jsonify({
            'success':    True,
            'nifty_spot': nifty_spot,
            'atm_strike': atm_strike,
            'expiry':     expiry,
            'calls':      sorted(calls, key=lambda r: r['strike']),
            'puts':       sorted(puts, key=lambda r: r['strike']),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        if user_id in authenticated_users:
            upstox = authenticated_users[user_id]
            try:
                if upstox.ws_client:
                    upstox.ws_client.stop_event.set()
                    if upstox.ws_client.ws:
                        upstox.ws_client.ws.close()
            except Exception:
                pass
            upstox.logged_in = False
            del authenticated_users[user_id]
        if user_id in live_data:
            del live_data[user_id]
        session.pop('user_id', None)
    return redirect(url_for('index'))

if __name__ == '__main__':
    socketio.run(app, debug=False, host='0.0.0.0', port=5001)
