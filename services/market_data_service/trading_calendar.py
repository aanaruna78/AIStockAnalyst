from datetime import datetime, time

class TradingCalendar:
    # NSE 2026 holidays (partial list for demonstration)
    NSE_HOLIDAYS_2026 = [
        "2026-01-26",  # Republic Day
        "2026-03-01",  # Mahashivratri
        "2026-03-25",  # Holi
        "2026-04-02",  # Ram Navami
        "2026-04-10",  # Good Friday
        "2026-08-15",  # Independence Day
        "2026-10-02",  # Gandhi Jayanti
        "2026-10-24",  # Diwali
        "2026-11-14",  # Diwali Laxmi Pujan
        "2026-12-25",  # Christmas
    ]
    
    MARKET_OPEN = time(9, 15)
    MARKET_CLOSE = time(15, 30)
    
    @staticmethod
    def is_trading_day(date: datetime) -> bool:
        """Check if the given date is a trading day"""
        # Weekend check
        if date.weekday() >= 5:  # Saturday = 5, Sunday = 6
            return False
        
        # Holiday check
        date_str = date.strftime("%Y-%m-%d")
        if date_str in TradingCalendar.NSE_HOLIDAYS_2026:
            return False
        
        return True
    
    @staticmethod
    def is_market_open(dt: datetime = None) -> bool:
        """Check if market is currently open"""
        import pytz
        if dt is None:
            ist = pytz.timezone("Asia/Kolkata")
            dt = datetime.now(ist)
        
        if not TradingCalendar.is_trading_day(dt):
            return False
        
        current_time = dt.time()
        return TradingCalendar.MARKET_OPEN <= current_time <= TradingCalendar.MARKET_CLOSE
    
    @staticmethod
    def next_trading_day(date: datetime) -> datetime:
        """Get the next trading day"""
        next_day = date
        while True:
            next_day = next_day.replace(day=next_day.day + 1)
            if TradingCalendar.is_trading_day(next_day):
                return next_day

# Singleton
trading_calendar = TradingCalendar()
