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
        from datetime import timedelta
        next_day = date
        while True:
            next_day = next_day + timedelta(days=1)
            if TradingCalendar.is_trading_day(next_day):
                return next_day

    @staticmethod
    def trading_days_between(start: datetime, end: datetime) -> int:
        """Count trading days between two dates (exclusive of start, inclusive of end).
        Used for GAP-8: accurate theta decay calculation.
        """
        from datetime import timedelta
        if end <= start:
            return 0
        count = 0
        current = start + timedelta(days=1)
        while current <= end:
            if TradingCalendar.is_trading_day(current):
                count += 1
            current = current + timedelta(days=1)
        return count

    @staticmethod
    def trading_days_to_expiry(expiry_date: datetime) -> float:
        """Return trading days (+ fractional intraday) to expiry.
        Used by PremiumSimulator for accurate theta calculation.
        """
        import pytz
        ist = pytz.timezone("Asia/Kolkata")
        now = datetime.now(ist)

        # Full trading days remaining (excluding today)
        full_days = TradingCalendar.trading_days_between(now, expiry_date)

        # Add fractional portion of today if market is open
        if TradingCalendar.is_trading_day(now):
            market_close = now.replace(hour=15, minute=30, second=0, microsecond=0)
            if now < market_close:
                remaining_today = (market_close - now).total_seconds()
                trading_day_seconds = (15 * 60 + 30 - 9 * 60 - 15) * 60  # 6h15m
                full_days += remaining_today / trading_day_seconds

        return max(0.01, full_days)

# Singleton
trading_calendar = TradingCalendar()
