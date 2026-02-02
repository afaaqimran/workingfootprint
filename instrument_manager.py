import requests
import gzip
import json
from datetime import datetime, timedelta
import os

class InstrumentManager:
    def __init__(self, cache_file='instruments_cache.json'):
        self.cache_file = cache_file
        self.instruments_url = 'https://assets.upstox.com/market-quote/instruments/exchange/complete.json.gz'
        self.instruments = []
        
    def download_instruments(self):
        """Download and extract instrument master file from Upstox"""
        try:
            print("📥 Downloading instrument master file from Upstox...")
            response = requests.get(self.instruments_url, timeout=30)
            
            if response.status_code == 200:
                # Decompress gzip data
                decompressed_data = gzip.decompress(response.content)
                self.instruments = json.loads(decompressed_data.decode('utf-8'))
                
                # Cache the data
                with open(self.cache_file, 'w') as f:
                    json.dump(self.instruments, f)
                
                print(f"✅ Downloaded {len(self.instruments)} instruments")
                return True
            else:
                print(f"❌ Failed to download instruments: HTTP {response.status_code}")
                return False
                
        except Exception as e:
            print(f"❌ Error downloading instruments: {e}")
            return False
    
    def load_cached_instruments(self):
        """Load instruments from cache file"""
        try:
            if os.path.exists(self.cache_file):
                with open(self.cache_file, 'r') as f:
                    self.instruments = json.load(f)
                print(f"✅ Loaded {len(self.instruments)} instruments from cache")
                return True
            return False
        except Exception as e:
            print(f"❌ Error loading cached instruments: {e}")
            return False
    
    def get_futures_contracts(self, symbol_name, segment='NSE_FO', months=3):
        """
        Get next N months of futures contracts for a given symbol
        
        Args:
            symbol_name: Base symbol name (e.g., 'NIFTY', 'BANKNIFTY')
            segment: Exchange segment (default: 'NSE_FO')
            months: Number of future months to return (default: 3)
        
        Returns:
            List of contract dictionaries with instrument_key, expiry, etc.
        """
        try:
            # Ensure instruments are loaded
            if not self.instruments:
                if not self.load_cached_instruments():
                    self.download_instruments()
            
            # Filter for futures contracts of the specified symbol
            futures = [
                inst for inst in self.instruments
                if inst.get('segment') == segment
                and inst.get('instrument_type') == 'FUT'
                and inst.get('name') == symbol_name
            ]
            
            # Parse expiry dates and filter future contracts
            today = datetime.now().date()
            valid_futures = []
            
            for contract in futures:
                try:
                    expiry_value = contract.get('expiry')
                    if expiry_value:
                        # Handle millisecond timestamp
                        if isinstance(expiry_value, (int, float)):
                            expiry_date = datetime.fromtimestamp(expiry_value / 1000).date()
                        else:
                            # Fallback to string parsing
                            expiry_date = datetime.strptime(str(expiry_value), '%Y-%m-%d').date()
                        
                        # Only include contracts that haven't expired
                        if expiry_date >= today:
                            contract['expiry_date'] = expiry_date
                            contract['expiry_str'] = expiry_date.strftime('%Y-%m-%d')
                            # Default lot_size to 1 if missing to avoid division by zero
                            contract['lot_size'] = contract.get('lot_size', 1)
                            valid_futures.append(contract)
                except Exception as e:
                    print(f"Error parsing expiry for {contract.get('trading_symbol')}: {e}")
                    continue
            
            # Sort by expiry date (nearest first)
            valid_futures.sort(key=lambda x: x['expiry_date'])
            
            # Return only the next N months
            return valid_futures[:months]
            
        except Exception as e:
            print(f"❌ Error getting futures contracts: {e}")
            return []
    
    def get_contract_list_for_dropdown(self):
        """
        Get formatted contract list for dropdown display
        
        Returns:
            List of dictionaries with display info for dropdown
        """
        contracts = []
        
        # Get NIFTY contracts (next 3 months)
        nifty_contracts = self.get_futures_contracts('NIFTY', months=3)
        for contract in nifty_contracts:
            expiry_date = contract['expiry_date']
            month_name = expiry_date.strftime('%b')  # e.g., 'Nov', 'Dec'
            
            contracts.append({
                'symbol': f"NIFTY_{month_name.upper()}",
                'display_name': f"NIFTY {month_name} Fut",
                'instrument_key': contract['instrument_key'],
                'exchange_token': contract.get('exchange_token', ''),
                'tradingsymbol': contract.get('trading_symbol', ''),
                'expiry': contract['expiry_str'],
                'lot_size': contract.get('lot_size', 65),
                'type': 'NIFTY'
            })
        
        # Get BANKNIFTY contracts (next 3 months)
        banknifty_contracts = self.get_futures_contracts('BANKNIFTY', months=3)
        for contract in banknifty_contracts:
            expiry_date = contract['expiry_date']
            month_name = expiry_date.strftime('%b')
            
            contracts.append({
                'symbol': f"BANKNIFTY_{month_name.upper()}",
                'display_name': f"BANKNIFTY {month_name} Fut",
                'instrument_key': contract['instrument_key'],
                'exchange_token': contract.get('exchange_token', ''),
                'tradingsymbol': contract.get('trading_symbol', ''),
                'expiry': contract['expiry_str'],
                'lot_size': contract.get('lot_size', 30),
                'type': 'BANKNIFTY'
            })
        
        return contracts
    
    def refresh_if_needed(self, max_age_hours=24):
        """
        Refresh instrument data if cache is older than max_age_hours
        
        Args:
            max_age_hours: Maximum age of cache in hours before refresh
        """
        try:
            if os.path.exists(self.cache_file):
                file_age = datetime.now() - datetime.fromtimestamp(os.path.getmtime(self.cache_file))
                
                if file_age > timedelta(hours=max_age_hours):
                    print(f"⏰ Cache is {file_age.total_seconds()/3600:.1f} hours old, refreshing...")
                    return self.download_instruments()
                else:
                    print(f"✅ Cache is fresh ({file_age.total_seconds()/3600:.1f} hours old)")
                    return self.load_cached_instruments()
            else:
                print("📥 No cache found, downloading fresh data...")
                return self.download_instruments()
                
        except Exception as e:
            print(f"❌ Error checking cache: {e}")
            return self.download_instruments()


# Test the module
if __name__ == '__main__':
    manager = InstrumentManager()
    
    # Download and cache instruments
    manager.refresh_if_needed()
    
    # Get contract list
    contracts = manager.get_contract_list_for_dropdown()
    
    print("\n📋 Available Contracts:")
    for contract in contracts:
        print(f"  {contract['display_name']}: {contract['instrument_key']} (Expiry: {contract['expiry']})")
