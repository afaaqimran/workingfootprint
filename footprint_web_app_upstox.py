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
from log_manager import initialize_logging, get_logger

# Footprint Processing Logic
class FootprintProcessor:
    def __init__(self):
        self.price_levels = {}  # price -> {buy_qty, sell_qty, total_qty}
        self.tick_size = 0.25
        self.lot_size = 65
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
        if 'NIFTY_CE' in symbol or 'NIFTY_PE' in symbol:
            # For options footprint charts (all 14 strike combinations)
            # Store all in footprint_data_OPTIONS_ATM.db (renamed to more generic later if needed)
            return 'footprint_data_OPTIONS_ATM.db'
        elif 'BANKNIFTY' in symbol:
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
        for db_file in ['footprint_data_NIFTY.db', 'footprint_data_BANKNIFTY.db', 'footprint_data_OPTIONS_ATM.db']:
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
        """Retrieve stored data for last N days. Always returns 1-minute candles."""
        try:
            target_db = self.get_db_path(symbol)
            if not os.path.exists(target_db):
                return []

            conn = sqlite3.connect(target_db)
            cursor = conn.cursor()
            
            # Calculate cutoff timestamp based on trading data (not created_at)
            # Convert timestamp from milliseconds to seconds for comparison
            cutoff_date = datetime.now()
            trading_days = 0
            while trading_days < days:
                cutoff_date -= timedelta(days=1)
                if cutoff_date.weekday() < 5:  # Monday=0, Friday=4
                    trading_days += 1
            
            # Convert cutoff date to Unix timestamp in MILLISECONDS (since timestamp is stored in ms)
            cutoff_timestamp_ms = int(cutoff_date.timestamp() * 1000)
            
            # Always fetch 1-minute data (timeframe='1') regardless of parameter
            # This ensures we can resample to any timeframe on demand
            cursor.execute('''
                SELECT 
                    c.timestamp, c.symbol, c.open, c.high, c.low, c.close, c.ltp, c.volume, c.volume_diff,
                    f.price, f.buy_qty, f.sell_qty, f.total_qty
                FROM candles c
                LEFT JOIN footprint_levels f ON c.timestamp = f.candle_timestamp 
                    AND c.symbol = f.symbol AND c.timeframe = f.timeframe
                WHERE c.symbol = ? AND c.timeframe = '1' AND c.timestamp >= ?
                ORDER BY c.timestamp ASC, f.id ASC
            ''', (symbol, cutoff_timestamp_ms))
            
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
    
    def clear_old_session_data(self, symbol, timeframe='1'):
        """Clear candle data from previous trading sessions (older than today)
        This ensures Options Footprint chart starts fresh each day
        """
        try:
            target_db = self.get_db_path(symbol)
            if not os.path.exists(target_db):
                return False
            
            conn = sqlite3.connect(target_db)
            cursor = conn.cursor()
            
            # Calculate cutoff for today (00:00 in local time)
            today_start = datetime.now().replace(hour=0, minute=0, second=0, microsecond=0)
            cutoff_timestamp_ms = int(today_start.timestamp() * 1000)
            
            # Delete candles from BEFORE today
            cursor.execute('''
                DELETE FROM footprint_levels 
                WHERE symbol = ? AND timeframe = ? AND candle_timestamp < ?
            ''', (symbol, timeframe, cutoff_timestamp_ms))
            
            cursor.execute('''
                DELETE FROM candles 
                WHERE symbol = ? AND timeframe = ? AND timestamp < ?
            ''', (symbol, timeframe, cutoff_timestamp_ms))
            
            conn.commit()
            deleted_count = cursor.rowcount
            conn.close()
            
            if deleted_count > 0:
                print(f"🧹 Cleared {deleted_count} old candles from {symbol}")
            
            return True
            
        except Exception as e:
            print(f"Error clearing old data for {symbol}: {e}")
            return False

app = Flask(__name__)
app.secret_key = 'your-secret-key-change-this'
socketio = SocketIO(app, cors_allowed_origins="*", ping_timeout=60, ping_interval=25, async_mode='eventlet')

# Initialize logging system with 5-day retention
logger = initialize_logging(log_dir='logs', retention_days=5)
logger.info("=" * 80)
logger.info("🚀 Footprint Application Started")
logger.info("=" * 80)

# Analytics token (1-year validity, read-only, no OAuth redirect needed)
ANALYTICS_TOKEN = "eyJ0eXAiOiJKV1QiLCJrZXlfaWQiOiJza192MS4wIiwiYWxnIjoiSFMyNTYifQ.eyJzdWIiOiJBVjYwMDEiLCJqdGkiOiI2OWJlNzhiZTg3YTgwYjEzMWJkZTg0MWMiLCJpc011bHRpQ2xpZW50IjpmYWxzZSwiaXNQbHVzUGxhbiI6ZmFsc2UsImlzRXh0ZW5kZWQiOnRydWUsImlhdCI6MTc3NDA5MDQzMCwiaXNzIjoidWRhcGktZ2F0ZXdheS1zZXJ2aWNlIiwiZXhwIjoxODA1NjY2NDAwfQ.edEAi8hh4gU63ceOAK_Kqfww786nI0zO8LP-7kLm9pQ"

# Global variables
authenticated_users = {}
live_data = {}
data_storage = DataStorage()  # Initialize persistent storage
instrument_manager = InstrumentManager()  # Initialize instrument manager

# Refresh instrument data on startup (if cache is older than 24 hours)
logger.info("🔄 Checking instrument data...")
instrument_manager.refresh_if_needed(max_age_hours=24)
logger.info("✅ Instrument data check complete")

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
        self.vix_ltp = 0         # India VIX — updated from NSE_INDEX|India VIX
        # OI history for change tracking: instrument_key -> [(timestamp_ms, oi), ...]
        self.oi_history = {}
        # LTP history for RoC tracking: instrument_key -> [(timestamp_ms, ltp), ...]
        self.ltp_history = {}
        # NIFTY spot history for RoC denominator: [(timestamp_ms, spot), ...]
        self.nifty_history = []

        # ATM options footprint tracking (CE and PE separately)
        # Each: {'open', 'high', 'low', 'close', 'ts', 'vol', 'prev_volume', 'prev_ltp', 'prev_close', 'prev_category'}
        self.atm_ce_candle = None
        self.atm_pe_candle = None
        self.atm_ce_prev_volume = 0
        self.atm_pe_prev_volume = 0
        self.atm_ce_prev_ltp = 0
        self.atm_pe_prev_ltp = 0
        self.atm_ce_prev_close = 0
        self.atm_pe_prev_close = 0
        self.atm_ce_prev_category = 'buy'
        self.atm_pe_prev_category = 'buy'
        self.atm_ce_fp_processor = FootprintProcessor()
        self.atm_pe_fp_processor = FootprintProcessor()
        self.atm_ce_fp_processor.lot_size = 1   # options VTT is raw contracts, not lots
        self.atm_pe_fp_processor.lot_size = 1
        self.atm_ce_fp_processor.tick_size = 0.05  # options tick size
        self.atm_pe_fp_processor.tick_size = 0.05

        # Locked ATM for options footprint chart — set ONCE at login, never changes intraday
        # This ensures the footprint chart always tracks the same CE/PE contract all day
        self.atm_fp_strike = None       # e.g. 24500  — locked at login
        self.atm_fp_ce_key = None       # instrument_key for the locked ATM CE
        self.atm_fp_pe_key = None       # instrument_key for the locked ATM PE
        self.atm_fp_expiry = None       # expiry string for display

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
        # Also subscribe India VIX for the time-based analysis tab
        self.ws_client.subscribe({'NSE_INDEX|India VIX'}, mode="ltpc")
        print("📡 Started Upstox WebSocket V3")

        # Subscribe NIFTY options strikes in background
        threading.Thread(target=self.subscribe_options_strikes, daemon=True).start()
        # Start ATM monitor — re-subscribes when spot moves by 1 strike
        threading.Thread(target=self._atm_monitor, daemon=True).start()

    def subscribe_options_strikes(self, nifty_ltp=None):
        """
        Resolve ATM/ITM NIFTY option strikes and subscribe them on the existing WebSocket.
        Uses full mode so we get LTP, ATP, OHLC in every tick.
        Subscribes to 14 strikes: ATM±300, ATM±200, ATM±100, ATM (all CE and PE).
        100-point increments only (no 50-point strikes).
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
            strike_step = 100  # Changed from 50 to 100 per user requirement

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

            # 7 strikes above and below ATM (ATM±300, ±200, ±100, ATM) — subscribe both CE and PE for each
            # With 100-point increments: ATM-300, ATM-200, ATM-100, ATM, ATM+100, ATM+200, ATM+300
            all_strikes = [atm_strike + i * strike_step for i in range(-3, 4)]  # 7 strikes total

            opt_lookup = {}
            for opt in expiry_options:
                key = (float(opt.get('strike_price', 0)), opt.get('instrument_type'))
                opt_lookup[key] = opt.get('instrument_key')

            new_meta = []
            new_keys = set()
            
            # Initialize tracking for all 14 strike/type combinations (7 strikes × 2 types)
            self.ofp_strike_candles = {}  # {symbol: candle_obj}
            self.ofp_strike_volumes = {}  # {symbol: prev_vtt}
            self.ofp_strike_close = {}    # {symbol: prev_close}
            self.ofp_strike_category = {} # {symbol: prev_category}
            self.ofp_strike_fp_proc = {}  # {symbol: FootprintProcessor}

            for strike in all_strikes:
                for opt_type in ('CE', 'PE'):
                    ikey = opt_lookup.get((float(strike), opt_type))
                    if strike < atm_strike:
                        label = f'ATM-{int(atm_strike - strike)}'
                        offset = -int(atm_strike - strike)
                    elif strike > atm_strike:
                        label = f'ATM+{int(strike - atm_strike)}'
                        offset = int(strike - atm_strike)
                    else:
                        label = 'ATM'
                        offset = 0
                    
                    new_meta.append({'strike': strike, 'type': opt_type, 'label': label,
                                      'instrument_key': ikey, 'expiry': nearest_expiry.strftime('%d %b %Y'),
                                      'offset': offset})
                    if ikey:
                        new_keys.add(ikey)
                        
                        # Initialize tracking for this strike/type
                        symbol = f'NIFTY_{opt_type}_{offset}'
                        self.ofp_strike_candles[symbol] = None
                        self.ofp_strike_volumes[symbol] = 0
                        self.ofp_strike_close[symbol] = 0
                        self.ofp_strike_category[symbol] = 'buy'
                        self.ofp_strike_fp_proc[symbol] = FootprintProcessor()

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
                print(f"📡 Subscribed {len(new_keys)} NIFTY option strikes (ATM={atm_strike}, expiry={nearest_expiry}, 100-pt increments)")

                # Lock the ATM for the options footprint chart on FIRST subscription only.
                # Once set, atm_fp_strike never changes for the rest of the day — the footprint
                # chart always tracks the same CE/PE contract regardless of where spot moves.
                if self.atm_fp_strike is None:
                    ce_key = opt_lookup.get((float(atm_strike), 'CE'))
                    pe_key = opt_lookup.get((float(atm_strike), 'PE'))
                    self.atm_fp_strike = atm_strike
                    self.atm_fp_ce_key = ce_key
                    self.atm_fp_pe_key = pe_key
                    self.atm_fp_expiry = nearest_expiry.strftime('%d %b %Y')
                    print(f"🔒 Locked ATM footprint strike: {atm_strike} | CE={ce_key} | PE={pe_key}")

                # Reset ATM options footprint volume tracking state so stale cumulative
                # VTT doesn't produce a massive spike on the first tick after re-subscription.
                # We do NOT reset when ATM shifts — the locked keys are unaffected anyway.
                self.atm_ce_candle = None
                self.atm_pe_candle = None
                self.atm_ce_prev_volume = 0
                self.atm_pe_prev_volume = 0
                self.atm_ce_prev_ltp = 0
                self.atm_pe_prev_ltp = 0

        except Exception as e:
            print(f"❌ Error subscribing options strikes: {e}")

    def _atm_monitor(self):
        """Re-subscribe options whenever ATM strike shifts by 100 pts or expiry rolls over"""
        last_atm = None
        last_subscribed_expiry = None  # track the expiry date we last subscribed
        last_subscribe_time = 0        # throttle: prevent re-subscribing more than once per 30s
        HYSTERESIS = 50  # spot must move 50 pts past strike boundary before switching ATM (conservative)
        SUBSCRIBE_COOLDOWN = 30  # seconds between re-subscriptions
        MARKET_OPEN_HOUR = 9
        MARKET_OPEN_MIN = 15  # Market opens at 09:15 IST
        STRIKE_STEP = 100  # Options Footprint uses 100-point strikes

        # Wait up to 30s for NIFTY spot to arrive before starting the monitor loop
        for _ in range(30):
            if self.nifty_spot_ltp > 0:
                break
            time.sleep(1)
        if self.nifty_spot_ltp <= 0:
            print("⚠️ ATM monitor: NIFTY spot not available after 30s, will retry in loop")

        while True:
            try:
                time.sleep(10)  # check every 10 seconds
                spot = self.nifty_spot_ltp
                if spot <= 0:
                    continue
                # Calculate ATM using 100-point increments (matches Options Footprint strike_step)
                current_atm = round(spot / STRIKE_STEP) * STRIKE_STEP
                now = time.time()
                
                # Skip option subscription during pre-open (before 09:15)
                # Pre-open trades can give incorrect ATM calculation; wait for actual market open
                current_time = datetime.now().time()
                if current_time.hour == MARKET_OPEN_HOUR and current_time.minute < MARKET_OPEN_MIN:
                    if last_atm is None:
                        print(f"⏰ Pre-open detected ({current_time.strftime('%H:%M')}), waiting for market open at 09:15...")
                    continue

                # Detect expiry rollover: if today is past the subscribed expiry, re-subscribe
                if self.options_meta:
                    subscribed_expiry_str = self.options_meta[0].get('expiry')
                    if subscribed_expiry_str != last_subscribed_expiry:
                        last_subscribed_expiry = subscribed_expiry_str
                    else:
                        try:
                            subscribed_expiry = datetime.strptime(subscribed_expiry_str, '%d %b %Y').date()
                            if datetime.now().date() > subscribed_expiry:
                                if now - last_subscribe_time >= SUBSCRIBE_COOLDOWN:
                                    print(f"🔄 Expiry {subscribed_expiry_str} has passed, rolling to next expiry...")
                                    self.subscribe_options_strikes(nifty_ltp=spot)
                                    last_atm = current_atm
                                    last_subscribe_time = now
                                continue
                        except Exception:
                            pass

                if last_atm is None:
                    if now - last_subscribe_time >= SUBSCRIBE_COOLDOWN:
                        last_atm = current_atm
                        print(f"✅ Market open detected, subscribing to options strikes with ATM={current_atm}")
                        self.subscribe_options_strikes(nifty_ltp=spot)
                        last_subscribe_time = now
                    continue

                # Only shift ATM if spot has moved beyond hysteresis buffer
                # HYSTERESIS prevents oscillation when spot hovers near 100-point boundaries
                if current_atm != last_atm:
                    if now - last_subscribe_time < SUBSCRIBE_COOLDOWN:
                        continue  # throttle — too soon since last subscription
                    if current_atm > last_atm and spot >= last_atm + (STRIKE_STEP / 2) + HYSTERESIS:
                        print(f"🔄 ATM shifted {last_atm} → {current_atm} (spot={spot}), re-subscribing options...")
                        self.subscribe_options_strikes(nifty_ltp=spot)
                        last_atm = current_atm
                        last_subscribe_time = now
                    elif current_atm < last_atm and spot <= last_atm - (STRIKE_STEP / 2) - HYSTERESIS:
                        print(f"🔄 ATM shifted {last_atm} → {current_atm} (spot={spot}), re-subscribing options...")
                        self.subscribe_options_strikes(nifty_ltp=spot)
                        last_atm = current_atm
                        last_subscribe_time = now
            except Exception as e:
                print(f"❌ ATM monitor error: {e}")

    def _process_atm_option_footprint(self, opt_type, ltp, vtt, current_ts):
        """
        Build 1-minute candles + footprint for the ATM CE or PE option and
        emit via Socket.IO as 'options_fp_data' with field 'opt_type': 'CE'/'PE'.
        Also persist to footprint_data_OPTIONS_ATM.db.
        """
        try:
            timeframe_ms = 60000  # always 1-min for options footprint
            candle_ts = int(current_ts // timeframe_ms) * timeframe_ms
            symbol = f'NIFTY_{opt_type}_ATM'

            if opt_type == 'CE':
                current_candle = self.atm_ce_candle
                prev_volume    = self.atm_ce_prev_volume
                prev_close     = self.atm_ce_prev_close
                prev_category  = self.atm_ce_prev_category
                fp_proc        = self.atm_ce_fp_processor
            else:
                current_candle = self.atm_pe_candle
                prev_volume    = self.atm_pe_prev_volume
                prev_close     = self.atm_pe_prev_close
                prev_category  = self.atm_pe_prev_category
                fp_proc        = self.atm_pe_fp_processor

            # Candle bucketing
            if current_candle and abs(current_candle['ts'] - candle_ts) < 1000:
                current_candle['high']  = max(current_candle['high'], ltp)
                current_candle['low']   = min(current_candle['low'], ltp)
                current_candle['close'] = ltp
            else:
                current_candle = {
                    'open': ltp, 'high': ltp, 'low': ltp, 'close': ltp,
                    'vol': 0, 'ts': candle_ts
                }

            # Volume diff
            if prev_volume == 0:
                prev_volume = vtt
                volume_diff = 0
            else:
                volume_diff = max(0, vtt - prev_volume)
                prev_volume = vtt

            # Footprint — use raw volume diff for options (no lot-size flooring needed)
            footprint_levels = []
            if volume_diff > 0:
                footprint_levels, new_category = fp_proc.process_intrabar_footprint(
                    price=ltp,
                    volume_diff=volume_diff,
                    open_price=current_candle['open'],
                    prev_close=prev_close,
                    prev_category=prev_category
                )
                prev_category = new_category

            base_update = {
                'symbol':    symbol,
                'opt_type':  opt_type,
                'offset':    0,  # ATM footprint always uses offset 0
                'timestamp': int(current_candle['ts']),
                'open':      current_candle['open'],
                'high':      current_candle['high'],
                'low':       current_candle['low'],
                'close':     current_candle['close'],
                'ltp':       ltp,
                'volume':    vtt,
                'volume_diff': volume_diff,
                'historical': False
            }

            if footprint_levels:
                for level in footprint_levels:
                    update = base_update.copy()
                    update['footprint_level'] = level
                    socketio.emit('options_fp_data', update, room=self.user_id)
                    data_storage.store_candle(update, '1')
            else:
                socketio.emit('options_fp_data', base_update, room=self.user_id)
                data_storage.store_candle(base_update, '1')

            # Write back updated state
            prev_close = current_candle['close']
            if opt_type == 'CE':
                self.atm_ce_candle        = current_candle
                self.atm_ce_prev_volume   = prev_volume
                self.atm_ce_prev_close    = prev_close
                self.atm_ce_prev_category = prev_category
            else:
                self.atm_pe_candle        = current_candle
                self.atm_pe_prev_volume   = prev_volume
                self.atm_pe_prev_close    = prev_close
                self.atm_pe_prev_category = prev_category

        except Exception as e:
            print(f"❌ ATM options footprint error ({opt_type}): {e}")

    def _process_all_strike_footprints(self, instrument_key, opt_type, offset, ltp, vtt, current_ts):
        """
        Process footprint for all 7 strikes (ATM±300, ±200, ±100, ATM) for both CE and PE.
        Stores data in separate tables per strike.
        Used to track all 14 strike/type combinations irrespective of user UI selection.
        """
        try:
            timeframe_ms = 60000  # always 1-min
            candle_ts = int(current_ts // timeframe_ms) * timeframe_ms
            symbol = f'NIFTY_{opt_type}_{offset}'  # e.g., NIFTY_CE_-300, NIFTY_PE_0, NIFTY_CE_100

            # Get or initialize candle state for this strike/type
            if symbol not in self.ofp_strike_candles:
                self.ofp_strike_candles[symbol] = None
                self.ofp_strike_volumes[symbol] = 0
                self.ofp_strike_close[symbol] = 0
                self.ofp_strike_category[symbol] = 'buy'
                self.ofp_strike_fp_proc[symbol] = FootprintProcessor()

            current_candle = self.ofp_strike_candles[symbol]
            prev_volume    = self.ofp_strike_volumes[symbol]
            prev_close     = self.ofp_strike_close[symbol]
            prev_category  = self.ofp_strike_category[symbol]
            fp_proc        = self.ofp_strike_fp_proc[symbol]

            # Candle bucketing
            if current_candle and abs(current_candle['ts'] - candle_ts) < 1000:
                current_candle['high']  = max(current_candle['high'], ltp)
                current_candle['low']   = min(current_candle['low'], ltp)
                current_candle['close'] = ltp
            else:
                current_candle = {
                    'open': ltp, 'high': ltp, 'low': ltp, 'close': ltp,
                    'vol': 0, 'ts': candle_ts
                }

            # Volume diff
            if prev_volume == 0:
                prev_volume = vtt
                volume_diff = 0
            else:
                volume_diff = max(0, vtt - prev_volume)
                prev_volume = vtt

            # Footprint — use raw volume diff for options
            footprint_levels = []
            if volume_diff > 0:
                footprint_levels, new_category = fp_proc.process_intrabar_footprint(
                    price=ltp,
                    volume_diff=volume_diff,
                    open_price=current_candle['open'],
                    prev_close=prev_close,
                    prev_category=prev_category
                )
                prev_category = new_category

            base_update = {
                'symbol':    symbol,
                'opt_type':  opt_type,
                'offset':    offset,  # Track offset for filtering
                'timestamp': int(current_candle['ts']),
                'open':      current_candle['open'],
                'high':      current_candle['high'],
                'low':       current_candle['low'],
                'close':     current_candle['close'],
                'ltp':       ltp,
                'volume':    vtt,
                'volume_diff': volume_diff,
                'historical': False
            }

            if footprint_levels:
                for level in footprint_levels:
                    update = base_update.copy()
                    update['footprint_level'] = level
                    # Emit for real-time chart updates (not just store to DB)
                    socketio.emit('options_fp_data', update, room=self.user_id)
                    data_storage.store_candle(update, '1')
            else:
                # Emit even when no footprint levels (for candle updates)
                socketio.emit('options_fp_data', base_update, room=self.user_id)
                data_storage.store_candle(base_update, '1')

            # Write back updated state
            prev_close = current_candle['close']
            self.ofp_strike_candles[symbol] = current_candle
            self.ofp_strike_volumes[symbol] = prev_volume
            self.ofp_strike_close[symbol] = prev_close
            self.ofp_strike_category[symbol] = prev_category

        except Exception as e:
            print(f"❌ All-strike footprint error ({symbol}): {e}")

    def process_websocket_data(self, data):
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
                        # Record NIFTY spot history for RoC denominator (keep last 5 min)
                        self.nifty_history.append((current_ts, ltp_val))
                        cutoff_n = current_ts - 5 * 60 * 1000
                        self.nifty_history = [(t, v) for t, v in self.nifty_history if t >= cutoff_n]
                    continue

                # ── India VIX ────────────────────────────────────────
                if instrument_key == 'NSE_INDEX|India VIX':
                    ltpc = feed_data.get('ltpc') \
                           or (feed_data.get('fullFeed') or {}).get('indexFF', {}).get('ltpc', {})
                    vix_val = ltpc.get('ltp', 0) if ltpc else 0
                    if vix_val:
                        self.vix_ltp = round(vix_val, 2)
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
                        ltp_val = ltpc.get('ltp', 0)
                        self.options_cache[instrument_key] = {
                            'ltp':    ltp_val,
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
                        # Record LTP history for RoC tracking (keep last 5 min)
                        if ltp_val > 0:
                            lhist = self.ltp_history.setdefault(instrument_key, [])
                            lhist.append((current_ts, ltp_val))
                            cutoff_ltp = current_ts - 5 * 60 * 1000
                            self.ltp_history[instrument_key] = [(t, v) for t, v in lhist if t >= cutoff_ltp]

                        # ── Options Footprint Processing for All Strikes ─────────────────────
                        # Process all 14 strike/type combinations (7 strikes × 2 types)
                        # This stores data for all offsets irrespective of UI selection
                        for meta in self.options_meta:
                            if meta.get('instrument_key') == instrument_key and ltp_val > 0:
                                offset = meta.get('offset', 0)
                                self._process_all_strike_footprints(
                                    instrument_key=instrument_key,
                                    opt_type=meta['type'],
                                    offset=offset,
                                    ltp=ltp_val,
                                    vtt=int(full.get('vtt', 0) or 0),
                                    current_ts=current_ts
                                )
                                break
                        
                        # ── ATM Options Footprint Real-Time Emit ──────────────────────────────
                        # Emit real-time footprint updates for locked ATM CE and PE
                        if instrument_key == self.atm_fp_ce_key and ltp_val > 0:
                            self._process_atm_option_footprint(
                                opt_type='CE',
                                ltp=ltp_val,
                                vtt=int(full.get('vtt', 0) or 0),
                                current_ts=current_ts
                            )
                        elif instrument_key == self.atm_fp_pe_key and ltp_val > 0:
                            self._process_atm_option_footprint(
                                opt_type='PE',
                                ltp=ltp_val,
                                vtt=int(full.get('vtt', 0) or 0),
                                current_ts=current_ts
                            )
                    continue  # don't process options as futures candles

                # ── Futures Chart Processing ──────────────────────────────────────────
                # Only process if this is the subscribed futures contract
                if instrument_key != self.instrument_token:
                    # Log token mismatch for diagnostics (throttled to avoid spam)
                    if not hasattr(self, '_last_token_mismatch_log') or \
                       (time.time() - self._last_token_mismatch_log) > 60:  # Log once per minute
                        print(f"⚠️ Instrument token mismatch: received={instrument_key}, "
                              f"expected={self.instrument_token} ({self.current_symbol})")
                        self._last_token_mismatch_log = time.time()
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
                
                # Skip pre-open period (before 09:15) for futures candles
                # Pre-open trades should not be included in the main chart
                candle_dt = datetime.fromtimestamp(candle_timestamp / 1000)
                if candle_dt.hour == 9 and candle_dt.minute < 15:
                    # Pre-open period — skip storing and emitting this candle
                    return

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
    """Retrieve stored data from database for last N days, resampled to requested timeframe"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    # Get query parameters
    symbol = request.args.get('symbol', 'NIFTY_DEC')
    timeframe = request.args.get('timeframe', '1')
    days = int(request.args.get('days', 180))
    
    try:
        # 1. Always fetch 1-minute data from DB regardless of requested timeframe
        # This ensures we can resample from 1min to any other timeframe
        raw_data = data_storage.get_stored_data(symbol, timeframe='1', days=days)
        print(f"🔍 Raw 1-minute data count: {len(raw_data)}")
        if raw_data:
            print(f"🔍 First raw item timestamp: {raw_data[0].get('timestamp')}")
            print(f"🔍 Last raw item timestamp: {raw_data[-1].get('timestamp')}")
        
        # 2. Resample to requested timeframe if needed
        if timeframe != '1':
            stored_data = resample_data(raw_data, timeframe)
            print(f"🔍 Resampled to {timeframe}min: {len(stored_data)} candles")
        else:
            stored_data = raw_data
            print(f"🔍 No resampling needed, using {len(stored_data)} 1-minute candles")
            
        return jsonify({
            'success': True,
            'data': stored_data,
            'count': len(stored_data)
        })
    except Exception as e:
        print(f"❌ Error in get_stored_data: {e}")
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
    lot_size = data.get('lot_size', 65)  # Get lot size from request (NIFTY default = 65)
    
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

@app.route('/api/diagnostics')
def get_diagnostics():
    """Return current instrument and WebSocket state for debugging"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401
    
    user_id = session['user_id']
    upstox = authenticated_users[user_id]
    
    try:
        return jsonify({
            'success': True,
            'current_symbol': upstox.current_symbol,
            'instrument_token': upstox.instrument_token,
            'current_timeframe': upstox.current_timeframe,
            'ws_connected': upstox.ws_client is not None and upstox.ws_client.connection_established if hasattr(upstox.ws_client, 'connection_established') else False,
            'atm_fp_ce_key': upstox.atm_fp_ce_key,
            'atm_fp_pe_key': upstox.atm_fp_pe_key,
            'timestamp': datetime.now().isoformat()
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500

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

            # Trigger 3: OI decreasing — compare current OI vs OI 2 ticks ago
            oi_now  = cached.get('oi', 0)
            oi_hist = upstox.oi_history.get(ikey, []) if ikey else []
            oi_decreasing = None  # None = not enough data
            if len(oi_hist) >= 3 and oi_now > 0:
                oi_prev = oi_hist[-3][1]  # OI from 2 ticks ago
                if oi_prev > 0:
                    oi_decreasing = oi_now < oi_prev

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
                'oi':            oi_now,
                'oi_decreasing': oi_decreasing,
            })

        expiry = upstox.options_meta[0].get('expiry', '—') if upstox.options_meta else '—'

        # ── Trigger 2: Futures SMA(5) > SMA(8) ──────────────────────────
        # Query last 8 closed 1-min candle closes from SQLite for current symbol
        trigger2 = None  # None = not enough data, True = bullish cross, False = bearish
        sma5 = None
        sma8 = None
        try:
            db_path = data_storage.get_db_path(upstox.current_symbol)
            conn = sqlite3.connect(db_path)
            cursor = conn.cursor()
            # Get last 8 completed 1-min candles (exclude the current open candle)
            # Current candle timestamp to exclude
            current_candle_ts = None
            if upstox.current_minute_candle:
                current_candle_ts = str(upstox.current_minute_candle.get('ts', ''))
            if current_candle_ts:
                cursor.execute('''
                    SELECT close FROM candles
                    WHERE symbol = ? AND timeframe = '1' AND timestamp != ?
                    ORDER BY timestamp DESC LIMIT 8
                ''', (upstox.current_symbol, current_candle_ts))
            else:
                cursor.execute('''
                    SELECT close FROM candles
                    WHERE symbol = ? AND timeframe = '1'
                    ORDER BY timestamp DESC LIMIT 8
                ''', (upstox.current_symbol,))
            rows = cursor.fetchall()
            conn.close()

            closes = [r[0] for r in rows]  # most recent first
            if len(closes) >= 8:
                sma5 = round(sum(closes[:5]) / 5, 2)
                sma8 = round(sum(closes[:8]) / 8, 2)
                trigger2 = sma5 > sma8
        except Exception as e:
            print(f"⚠️ Trigger2 SMA error: {e}")

        return jsonify({
            'success':    True,
            'atm_strike': atm_strike,
            'nifty_ltp':  upstox.nifty_spot_ltp or upstox.prev_ltp,
            'expiry':     expiry,
            'data':       result_rows,
            'trigger2': {
                'signal':  trigger2,   # True=bullish, False=bearish, None=insufficient data
                'sma5':    sma5,
                'sma8':    sma8,
            }
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


@app.route('/api/volatility-skew')
def get_volatility_skew():
    """Compute implied volatility across strikes using Black-Scholes and return skew data"""
    import math

    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]

    try:
        if not upstox.options_meta:
            return jsonify({'success': False, 'message': 'Options data loading — please retry in a few seconds'})

        nifty_spot = upstox.nifty_spot_ltp or upstox.prev_ltp
        if not nifty_spot:
            return jsonify({'success': False, 'message': 'Waiting for NIFTY spot price'})

        atm_strike = round(nifty_spot / 50) * 50
        expiry_str = upstox.options_meta[0].get('expiry', '')

        # Time to expiry in years
        try:
            expiry_date = datetime.strptime(expiry_str, '%d %b %Y').date()
            today = datetime.now().date()
            dte = max((expiry_date - today).days, 0)
        except Exception:
            dte = 1
        T = max(dte / 365.0, 1 / 365.0)

        r = 0.065  # risk-free rate (approx India 10yr)

        def bs_price(S, K, T, r, sigma, opt_type):
            d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            def N(x):
                return 0.5 * (1 + math.erf(x / math.sqrt(2)))
            if opt_type == 'CE':
                return S * N(d1) - K * math.exp(-r * T) * N(d2)
            else:
                return K * math.exp(-r * T) * N(-d2) - S * N(-d1)

        def calc_iv(market_price, S, K, T, r, opt_type):
            """Newton-Raphson IV solver"""
            if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
                return None
            intrinsic = max(S - K, 0) if opt_type == 'CE' else max(K - S, 0)
            if market_price < intrinsic * 0.99:
                return None
            sigma = 0.3  # initial guess
            for _ in range(100):
                price = bs_price(S, K, T, r, sigma, opt_type)
                d1 = (math.log(S / K) + (r + 0.5 * sigma ** 2) * T) / (sigma * math.sqrt(T))
                vega = S * math.exp(-0.5 * d1 ** 2) / math.sqrt(2 * math.pi) * math.sqrt(T)
                if vega < 1e-10:
                    break
                diff = price - market_price
                sigma -= diff / vega
                if sigma <= 0:
                    sigma = 1e-6
                if abs(diff) < 0.001:
                    break
            return round(sigma * 100, 2) if 0 < sigma < 5 else None

        ce_data, pe_data = [], []

        for meta in upstox.options_meta:
            ikey = meta.get('instrument_key')
            cached = upstox.options_cache.get(ikey, {}) if ikey else {}
            ltp = cached.get('ltp', 0)
            strike = meta['strike']
            opt_type = meta['type']

            iv = calc_iv(ltp, nifty_spot, strike, T, r, opt_type)

            row = {
                'strike': strike,
                'type':   opt_type,
                'label':  meta['label'],
                'ltp':    ltp,
                'iv':     iv,
            }
            if opt_type == 'CE':
                ce_data.append(row)
            else:
                pe_data.append(row)

        return jsonify({
            'success':    True,
            'nifty_spot': nifty_spot,
            'atm_strike': atm_strike,
            'expiry':     expiry_str,
            'dte':        dte,
            'calls':      sorted(ce_data, key=lambda r: r['strike']),
            'puts':       sorted(pe_data, key=lambda r: r['strike']),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/option-chain-full')
def get_option_chain_full():
    """Return full option chain paired by strike — CE on left, PE on right"""
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]

    try:
        if not upstox.options_meta:
            threading.Thread(target=upstox.subscribe_options_strikes, daemon=True).start()
            return jsonify({'success': False, 'message': 'Options data loading — please retry in a few seconds'})

        strikes = {}
        for meta in upstox.options_meta:
            strike = meta['strike']
            ikey = meta.get('instrument_key')
            cached = upstox.options_cache.get(ikey, {}) if ikey else {}
            side = meta['type']  # 'CE' or 'PE'
            if strike not in strikes:
                strikes[strike] = {'ce': {}, 'pe': {}}
            strikes[strike][side.lower()] = {
                'ltp':    cached.get('ltp', 0),
                'open':   cached.get('open', 0),
                'high':   cached.get('high', 0),
                'low':    cached.get('low', 0),
                'close':  cached.get('cp', 0),
                'volume': cached.get('volume', 0),
                'oi':     cached.get('oi', 0),
            }

        nifty_spot = upstox.nifty_spot_ltp or upstox.prev_ltp
        atm_strike = round(nifty_spot / 50) * 50 if nifty_spot else None
        expiry = upstox.options_meta[0].get('expiry', '—') if upstox.options_meta else '—'

        rows = []
        for strike in sorted(strikes.keys()):
            rows.append({
                'strike': strike,
                'is_atm': strike == atm_strike,
                'ce': strikes[strike].get('ce', {}),
                'pe': strikes[strike].get('pe', {}),
            })

        return jsonify({
            'success':    True,
            'nifty_spot': nifty_spot,
            'atm_strike': atm_strike,
            'expiry':     expiry,
            'rows':       rows,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/options-footprint-data')
def get_options_footprint_data():
    """
    Return stored CE/PE footprint candle data from footprint_data_OPTIONS_ATM.db
    Supports fetching for any strike offset: ATM, ATM±100, ATM±200, ATM±300
    If no offset specified, defaults to current day data only
    """
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]
    opt_type = request.args.get('type', 'CE').upper()   # 'CE' or 'PE'
    offset = request.args.get('offset', '0')             # '0', '-100', '+100', '-200', '+200', '-300', '+300'
    days = int(request.args.get('days', 1))              # Default to current day only
    
    try:
        # Build symbol based on offset
        # Symbol format: NIFTY_CE_0, NIFTY_CE_-100, NIFTY_CE_100, etc.
        symbol = f'NIFTY_{opt_type}_{offset}'
        
        # If requesting current day only (days=1), clear old data from previous sessions
        if days == 1:
            data_storage.clear_old_session_data(symbol, timeframe='1')
        
        # Fetch data from database
        raw_data = data_storage.get_stored_data(symbol, timeframe='1', days=days)
        
        return jsonify({
            'success':      True,
            'data':         raw_data,
            'count':        len(raw_data),
            'opt_type':     opt_type,
            'offset':       offset,
            'locked_strike': upstox.atm_fp_strike,
            'locked_expiry': upstox.atm_fp_expiry,
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/tba-snapshot')
def get_tba_snapshot():
    """
    Returns a single Time-Based Analysis snapshot with all columns needed for the
    NIFTY Option Chain Time-Based Analysis tab:
      - Nifty Spot, PCR, Put OI (ATM & ATM-1), Call OI (ATM & ATM+1),
        IV (ATM straddle avg), VIX, Support/Resistance, Max Pain,
        Futures OI Change %, Bias
    """
    import math

    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]

    try:
        if not upstox.options_meta:
            return jsonify({'success': False, 'message': 'Options data loading — please retry'})

        nifty_spot = upstox.nifty_spot_ltp or upstox.prev_ltp
        atm_strike = round(nifty_spot / 50) * 50 if nifty_spot else None
        expiry = upstox.options_meta[0].get('expiry', '—') if upstox.options_meta else '—'
        now_ist = datetime.now()  # server runs in UTC on VPS — adjusted below
        try:
            import pytz
            ist = pytz.timezone('Asia/Kolkata')
            now_ist = datetime.now(ist)
        except Exception:
            from datetime import timezone, timedelta as td
            now_ist = datetime.now(timezone(td(hours=5, minutes=30)))

        # ── Build strike → CE/PE OI + volume map ──────────────────────
        strike_data = {}  # strike -> {ce_oi, pe_oi, ce_vol, pe_vol, ce_ltp, pe_ltp}
        for meta in upstox.options_meta:
            strike = meta['strike']
            ikey = meta.get('instrument_key')
            cached = upstox.options_cache.get(ikey, {}) if ikey else {}
            oi  = cached.get('oi', 0)
            vol = cached.get('volume', 0)
            ltp = cached.get('ltp', 0)
            if strike not in strike_data:
                strike_data[strike] = {'ce_oi': 0, 'pe_oi': 0, 'ce_vol': 0, 'pe_vol': 0,
                                       'ce_ltp': 0, 'pe_ltp': 0}
            if meta['type'] == 'CE':
                strike_data[strike]['ce_oi']  = oi
                strike_data[strike]['ce_vol'] = vol
                strike_data[strike]['ce_ltp'] = ltp
            else:
                strike_data[strike]['pe_oi']  = oi
                strike_data[strike]['pe_vol'] = vol
                strike_data[strike]['pe_ltp'] = ltp

        # ── PCR — from Upstox /v2/market/pcr API ──────────────────────
        # Converts expiry from '05 Jun 2026' → '2026-06-05' for the API
        pcr = None
        try:
            expiry_dt  = datetime.strptime(expiry, '%d %b %Y')
            expiry_api = expiry_dt.strftime('%Y-%m-%d')
            today_api  = datetime.now().strftime('%Y-%m-%d')
            pcr_resp = requests.get(
                'https://api.upstox.com/v2/market/pcr',
                params={
                    'instrument_key':  'NSE_INDEX|Nifty 50',
                    'expiry':          expiry_api,
                    'date':            today_api,
                    'bucket_interval': 5,   # 5-min buckets to match snapshot cadence
                },
                headers={
                    'Content-Type': 'application/json',
                    'Accept':       'application/json',
                    'Authorization': f'Bearer {upstox.access_token}',
                },
                timeout=4
            )
            if pcr_resp.status_code == 200:
                pcr_json = pcr_resp.json()
                d = pcr_json.get('data', {})

                # Try top-level pcr field first (overall day PCR)
                raw = d.get('pcr')

                # If not present, fall back to latest entry in intraday_insights array
                if raw is None:
                    insights = d.get('intraday_insights') or d.get('insights') or []
                    if insights:
                        raw = insights[-1].get('pcr')

                # Some responses nest under a list directly at data level
                if raw is None and isinstance(d, list) and d:
                    raw = d[-1].get('pcr')

                if raw is not None:
                    pcr = round(float(raw), 2)
                else:
                    print(f"⚠️ PCR API: unexpected response shape — {str(pcr_json)[:200]}")
            else:
                print(f"⚠️ PCR API HTTP {pcr_resp.status_code}: {pcr_resp.text[:200]}")
        except Exception as pcr_err:
            print(f"⚠️ PCR API error: {pcr_err}")

        # Fallback: compute PCR locally from subscribed strikes OI if API failed
        if pcr is None:
            total_ce_oi = sum(v['ce_oi'] for v in strike_data.values())
            total_pe_oi = sum(v['pe_oi'] for v in strike_data.values())
            pcr = round(total_pe_oi / total_ce_oi, 2) if total_ce_oi > 0 else None
            if pcr:
                print(f"ℹ️ PCR: using local fallback ({pcr})")

        # ── Put OI & Call OI — ATM and ATM±1 strike ───────────────────
        atm_minus1 = atm_strike - 50 if atm_strike else None
        atm_plus1  = atm_strike + 50 if atm_strike else None

        def oi_desc(strike, side):
            """Return OI and volume for a strike/side as a dict."""
            d = strike_data.get(strike, {})
            oi_val  = d.get(f'{side}_oi', 0)
            vol_val = d.get(f'{side}_vol', 0)
            ltp_val = d.get(f'{side}_ltp', 0)
            return {'strike': strike, 'oi': oi_val, 'volume': vol_val, 'ltp': ltp_val}

        put_atm   = oi_desc(atm_strike, 'pe') if atm_strike else {}
        put_atm_m1 = oi_desc(atm_minus1, 'pe') if atm_minus1 else {}
        call_atm  = oi_desc(atm_strike, 'ce') if atm_strike else {}
        call_atm_p1 = oi_desc(atm_plus1, 'ce') if atm_plus1 else {}

        # ── Max Pain — from Upstox /v2/market/max-pain API ────────────
        # Uses insights[-1].max_pain for the most recent intraday value.
        # Falls back to data.max_pain (end-of-day overall) if insights not yet available,
        # and finally falls back to local calculation if the API fails entirely.
        max_pain_strike = None
        try:
            expiry_dt_mp  = datetime.strptime(expiry, '%d %b %Y')
            expiry_api_mp = expiry_dt_mp.strftime('%Y-%m-%d')
            today_api_mp  = datetime.now().strftime('%Y-%m-%d')
            mp_resp = requests.get(
                'https://api.upstox.com/v2/market/max-pain',
                params={
                    'instrument_key':  'NSE_INDEX|Nifty 50',
                    'expiry':          expiry_api_mp,
                    'date':            today_api_mp,
                    'bucket_interval': 5,   # 5-min buckets for intraday granularity
                },
                headers={
                    'Content-Type': 'application/json',
                    'Accept':       'application/json',
                    'Authorization': f'Bearer {upstox.access_token}',
                },
                timeout=4
            )
            if mp_resp.status_code == 200:
                mp_json = mp_resp.json()
                mp_data = mp_json.get('data', {})

                # Prefer the latest intraday insight (most current value during market hours)
                insights = mp_data.get('insights', [])
                if insights:
                    raw_mp = insights[-1].get('max_pain')
                else:
                    # Fall back to overall day max_pain field
                    raw_mp = mp_data.get('max_pain')

                if raw_mp is not None:
                    max_pain_strike = int(float(raw_mp))
                else:
                    print(f"⚠️ Max Pain API: no value in response — {str(mp_json)[:200]}")
            else:
                print(f"⚠️ Max Pain API HTTP {mp_resp.status_code}: {mp_resp.text[:200]}")
        except Exception as mp_err:
            print(f"⚠️ Max Pain API error: {mp_err}")

        # Fallback: local max pain calculation from subscribed strikes OI
        if max_pain_strike is None:
            strikes_sorted = sorted(strike_data.keys())
            min_pain = float('inf')
            for test_strike in strikes_sorted:
                pain = 0
                for s, d in strike_data.items():
                    pain += max(0, test_strike - s) * d['ce_oi']
                    pain += max(0, s - test_strike) * d['pe_oi']
                if pain < min_pain:
                    min_pain = pain
                    max_pain_strike = int(test_strike)
            if max_pain_strike:
                print(f"ℹ️ Max Pain: using local fallback ({max_pain_strike})")

        # ── IV (ATM straddle average) ──────────────────────────────────
        try:
            expiry_date = datetime.strptime(expiry, '%d %b %Y').date()
            dte = max((expiry_date - datetime.now().date()).days, 0)
        except Exception:
            dte = 1
        T = max(dte / 365.0, 1 / 365.0)
        r = 0.065

        def bs_call(S, K, T, r, sigma):
            d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
            return S * N(d1) - K * math.exp(-r * T) * N(d2)

        def bs_put(S, K, T, r, sigma):
            d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
            d2 = d1 - sigma * math.sqrt(T)
            N = lambda x: 0.5 * (1 + math.erf(x / math.sqrt(2)))
            return K * math.exp(-r * T) * N(-d2) - S * N(-d1)

        def calc_iv_nr(market_price, S, K, T, r, opt_type):
            if market_price <= 0 or S <= 0 or K <= 0 or T <= 0:
                return None
            intrinsic = max(S - K, 0) if opt_type == 'CE' else max(K - S, 0)
            if market_price < intrinsic * 0.99:
                return None
            sigma = 0.3
            for _ in range(100):
                price = bs_call(S, K, T, r, sigma) if opt_type == 'CE' else bs_put(S, K, T, r, sigma)
                d1 = (math.log(S / K) + (r + 0.5 * sigma**2) * T) / (sigma * math.sqrt(T))
                vega = S * math.exp(-0.5 * d1**2) / math.sqrt(2 * math.pi) * math.sqrt(T)
                if vega < 1e-10:
                    break
                diff = price - market_price
                sigma -= diff / vega
                if sigma <= 0:
                    sigma = 1e-6
                if abs(diff) < 0.001:
                    break
            return round(sigma * 100, 2) if 0 < sigma < 5 else None

        atm_ce_ltp = strike_data.get(atm_strike, {}).get('ce_ltp', 0) if atm_strike else 0
        atm_pe_ltp = strike_data.get(atm_strike, {}).get('pe_ltp', 0) if atm_strike else 0
        iv_ce = calc_iv_nr(atm_ce_ltp, nifty_spot, atm_strike, T, r, 'CE') if (atm_ce_ltp and nifty_spot and atm_strike) else None
        iv_pe = calc_iv_nr(atm_pe_ltp, nifty_spot, atm_strike, T, r, 'PE') if (atm_pe_ltp and nifty_spot and atm_strike) else None
        iv_avg = None
        if iv_ce and iv_pe:
            iv_avg = round((iv_ce + iv_pe) / 2, 1)
        elif iv_ce:
            iv_avg = iv_ce
        elif iv_pe:
            iv_avg = iv_pe

        # ── Support & Resistance via OI concentration ──────────────────
        # Resistance: top CE OI strikes (sellers defend)
        # Support:    top PE OI strikes (sellers defend)
        ce_oi_sorted = sorted([(s, d['ce_oi']) for s, d in strike_data.items() if d['ce_oi'] > 0],
                               key=lambda x: x[1], reverse=True)
        pe_oi_sorted = sorted([(s, d['pe_oi']) for s, d in strike_data.items() if d['pe_oi'] > 0],
                               key=lambda x: x[1], reverse=True)

        resistance_strikes = [s for s, _ in ce_oi_sorted[:2]]
        support_strikes    = [s for s, _ in pe_oi_sorted[:2]]

        def sr_label(strikes, sr_type):
            if not strikes:
                return f'No {sr_type} data'
            parts = []
            for s in strikes:
                oi_v = strike_data[s]['ce_oi'] if sr_type == 'Resistance' else strike_data[s]['pe_oi']
                parts.append(f'{int(s)} ({_fmt_oi(oi_v)})')
            return ', '.join(parts)

        def _fmt_oi(v):
            if v >= 10000000: return f'{v/10000000:.1f}Cr'
            if v >= 100000:   return f'{v/100000:.1f}L'
            if v >= 1000:     return f'{v/1000:.0f}K'
            return str(v)

        # SR analysis text: compare highest PE OI (support) vs highest CE OI (resistance)
        sr_lines = []
        if support_strikes:
            s_strike = support_strikes[0]
            s_oi = strike_data[s_strike]['pe_oi']
            # Check if support is holding (i.e. OI not rapidly declining)
            s_ikey = next((m['instrument_key'] for m in upstox.options_meta
                           if m['strike'] == s_strike and m['type'] == 'PE'), None)
            s_hist = upstox.oi_history.get(s_ikey, []) if s_ikey else []
            s_hold = 'Holding' if (len(s_hist) < 3 or s_hist[-1][1] >= s_hist[-3][1]) else 'Under Pressure'
            sr_lines.append(f'Support: {int(s_strike)} {s_hold}')
        if resistance_strikes:
            r_strike = resistance_strikes[0]
            r_ikey = next((m['instrument_key'] for m in upstox.options_meta
                           if m['strike'] == r_strike and m['type'] == 'CE'), None)
            r_hist = upstox.oi_history.get(r_ikey, []) if r_ikey else []
            r_hold = 'Holding' if (len(r_hist) < 3 or r_hist[-1][1] >= r_hist[-3][1]) else 'Under Pressure'
            sr_lines.append(f'Resistance: {int(r_strike)} {r_hold}')
        sr_text = ' / '.join(sr_lines) if sr_lines else '—'

        # ── Futures OI Change % ────────────────────────────────────────
        # Use the last 2 stored 1-min candles from the futures DB
        fut_oi_chg = None
        try:
            db_path = data_storage.get_db_path(upstox.current_symbol)
            conn = sqlite3.connect(db_path)
            cur = conn.cursor()
            cur.execute('''SELECT volume FROM candles WHERE symbol=? AND timeframe='1'
                           ORDER BY timestamp DESC LIMIT 2''', (upstox.current_symbol,))
            vols = [r[0] for r in cur.fetchall()]
            conn.close()
            if len(vols) == 2 and vols[1] > 0:
                fut_oi_chg = round((vols[0] - vols[1]) / vols[1] * 100, 2)
        except Exception:
            pass

        # ── Bias ───────────────────────────────────────────────────────
        # Simple heuristic:
        #   PCR > 1.3  → Strong Bullish
        #   PCR > 1.1  → Bullish
        #   PCR > 0.9  → Neutral
        #   PCR > 0.7  → Bearish
        #   PCR <= 0.7 → Strong Bearish
        # Modified by support/resistance OI comparison
        bias = 'Neutral'
        if pcr is not None:
            if pcr >= 1.4:
                bias = 'Strong Bullish'
            elif pcr >= 1.15:
                bias = 'Bullish'
            elif pcr >= 0.85:
                bias = 'Neutral'
            elif pcr >= 0.65:
                bias = 'Bearish'
            else:
                bias = 'Strong Bearish'
            # Tilt bias if support is under pressure and price is near support
            if atm_strike and support_strikes:
                near_support = abs(nifty_spot - support_strikes[0]) < 75
                if near_support and 'Under Pressure' in sr_text:
                    if bias == 'Bullish':
                        bias = 'Neutral'
                    elif bias == 'Neutral':
                        bias = 'Bearish'

        def _vol_label(vol):
            if vol == 0:
                return 'Low vol'
            # Compare to ATM vol as baseline — rough categorisation
            atm_vol_base = max(strike_data.get(atm_strike, {}).get('ce_vol', 1),
                               strike_data.get(atm_strike, {}).get('pe_vol', 1), 1)
            ratio = vol / atm_vol_base
            if ratio >= 1.5:
                return 'High volume'
            elif ratio >= 0.8:
                return 'Moderate volume'
            return 'Low volume'

        return jsonify({
            'success':     True,
            'time':        now_ist.strftime('%H:%M'),
            'nifty_spot':  round(nifty_spot, 2) if nifty_spot else None,
            'pcr':         pcr,
            'vix':         upstox.vix_ltp if upstox.vix_ltp > 0 else None,
            'iv':          iv_avg,
            'expiry':      expiry,
            'atm_strike':  int(atm_strike) if atm_strike else None,
            'put_atm': {
                'strike':    put_atm.get('strike'),
                'oi':        put_atm.get('oi', 0),
                'volume':    put_atm.get('volume', 0),
                'ltp':       put_atm.get('ltp', 0),
                'vol_label': _vol_label(put_atm.get('volume', 0)),
            },
            'put_atm_m1': {
                'strike':    put_atm_m1.get('strike'),
                'oi':        put_atm_m1.get('oi', 0),
                'volume':    put_atm_m1.get('volume', 0),
                'ltp':       put_atm_m1.get('ltp', 0),
                'vol_label': _vol_label(put_atm_m1.get('volume', 0)),
            },
            'call_atm': {
                'strike':    call_atm.get('strike'),
                'oi':        call_atm.get('oi', 0),
                'volume':    call_atm.get('volume', 0),
                'ltp':       call_atm.get('ltp', 0),
                'vol_label': _vol_label(call_atm.get('volume', 0)),
            },
            'call_atm_p1': {
                'strike':    call_atm_p1.get('strike'),
                'oi':        call_atm_p1.get('oi', 0),
                'volume':    call_atm_p1.get('volume', 0),
                'ltp':       call_atm_p1.get('ltp', 0),
                'vol_label': _vol_label(call_atm_p1.get('volume', 0)),
            },
            'support_resistance': sr_text,
            'support_strikes':    support_strikes,
            'resistance_strikes': resistance_strikes,
            'max_pain':    max_pain_strike,
            'fut_oi_chg':  fut_oi_chg,
            'bias':        bias,
        })

    except Exception as e:
        print(f"❌ TBA snapshot error: {e}")
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/roc')
def get_roc():
    """
    Rate of Change of option LTP as a percentage over 30s, 1m and 3m windows.

    Two modes (passed as ?mode=rolling or ?mode=fixed):

    ROLLING (sliding window):
        ltp_past = option LTP exactly T seconds ago (closest tick within ±10s)
        RoC % = ((ltp_now - ltp_past) / ltp_past) * 100

    FIXED (candle-style reset):
        ltp_past = option LTP at the start of the current period
        Period boundaries: 30s → floor(now, 30s), 1m → floor(now, 60s), 3m → floor(now, 180s)
        RoC % = ((ltp_now - ltp_at_period_start) / ltp_at_period_start) * 100

    Shows None when ltp_past is zero or unavailable.
    """
    if 'user_id' not in session or session['user_id'] not in authenticated_users:
        return jsonify({'success': False}), 401

    user_id = session['user_id']
    upstox = authenticated_users[user_id]
    mode = request.args.get('mode', 'rolling')  # 'rolling' or 'fixed'

    try:
        if not upstox.options_meta:
            return jsonify({'success': False, 'message': 'Options data loading — please retry in a few seconds'})

        now_ms = int(time.time() * 1000)
        windows = [('30s', 30), ('1m', 60), ('3m', 180)]

        def closest(history, target_ms, tolerance_ms):
            """Return value of entry closest to target_ms within tolerance, or None."""
            if not history:
                return None
            best = min(history, key=lambda x: abs(x[0] - target_ms))
            if abs(best[0] - target_ms) <= tolerance_ms:
                return best[1]
            return None

        def period_start_ltp(history, secs):
            """
            Fixed mode: find the LTP at the start of the current period.
            Period start = floor(now_ms, secs*1000).
            Looks for the first tick at or just after that boundary (within +5s).
            """
            if not history:
                return None
            boundary_ms = (now_ms // (secs * 1000)) * (secs * 1000)
            # Find oldest tick that is >= boundary and within 5s after it
            candidates = [(t, v) for t, v in history if boundary_ms <= t <= boundary_ms + 5000]
            if candidates:
                return min(candidates, key=lambda x: x[0])[1]
            # Fallback: closest tick to boundary within tolerance
            return closest(history, boundary_ms, tolerance_ms=10 * 1000)

        calls, puts = [], []

        for meta in upstox.options_meta:
            ikey = meta.get('instrument_key')
            cached = upstox.options_cache.get(ikey, {}) if ikey else {}
            ltp_now = cached.get('ltp', 0)
            hist = upstox.ltp_history.get(ikey, []) if ikey else []

            roc = {}
            for label, secs in windows:
                if mode == 'fixed':
                    ltp_past = period_start_ltp(hist, secs)
                else:
                    target = now_ms - secs * 1000
                    ltp_past = closest(hist, target, tolerance_ms=10 * 1000)

                if ltp_past is None or ltp_past == 0 or ltp_now == 0:
                    roc[label] = None
                else:
                    roc[label] = round((ltp_now - ltp_past) / ltp_past * 100, 2)

            row = {
                'strike': meta['strike'],
                'type':   meta['type'],
                'label':  meta['label'],
                'ltp':    ltp_now,
                'roc':    roc,
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
            'mode':       mode,
            'calls':      sorted(calls, key=lambda r: r['strike']),
            'puts':       sorted(puts,  key=lambda r: r['strike']),
        })
    except Exception as e:
        return jsonify({'success': False, 'message': str(e)}), 500


@app.route('/api/logs-stats')
def get_logs_stats():
    """Get logging statistics and list of log files"""
    try:
        from log_manager import get_log_manager
        log_mgr = get_log_manager()
        stats = log_mgr.get_log_stats()
        return jsonify({'success': True, 'data': stats})
    except Exception as e:
        logger.error(f"Error getting log stats: {e}")
        return jsonify({'success': False, 'error': str(e)}), 500

@app.route('/logout')
def logout():
    if 'user_id' in session:
        user_id = session['user_id']
        logger.info(f"🚪 User {user_id} logging out")
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
        logger.info(f"✅ User {user_id} logged out successfully")
    return redirect(url_for('index'))

if __name__ == '__main__':
    logger.info("🌐 Starting Flask-SocketIO server")
    logger.info("📍 Server running on http://0.0.0.0:5001")
    try:
        socketio.run(app, debug=False, host='0.0.0.0', port=5001)
    except KeyboardInterrupt:
        logger.warning("⚠️ Server interrupted by user")
    except Exception as e:
        logger.critical(f"❌ Server error: {e}")
    finally:
        logger.info("🛑 Server shutdown")
        logger.info("=" * 80)
