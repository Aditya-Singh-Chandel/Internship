from fastapi import HTTPException
from datetime import datetime

def parse_datetime_input(dt_str: str | None):
    if not dt_str:
        return None
        
    dt_str = dt_str.strip()
    parts = dt_str.split()
    
    if len(parts) > 1:
        date_part = parts[0]
        time_part = parts[1]
    else:
        date_part = parts[0]
        time_part = "00:00:00"
        
    try:
        day, month, year = date_part.split("/")
    except ValueError:
        raise HTTPException(status_code=400, detail="Date must be in dd/mm/yyyy format.")
    
    time_components = time_part.split(":")
    while len(time_components) < 3:
        time_components.append("00")
        
    try:
        hour, minute, second = time_components
        day_int = int(day)
        month_int = int(month)
        year_int = int(year)
        hour_int = int(hour)
        minute_int = int(minute)
        second_int = int(second)
    except ValueError:
        raise HTTPException(status_code=400, detail="Invalid date or time numbers.")
    
    if month_int in [4, 6, 9, 11] and day_int > 30:
        raise HTTPException(status_code=400, detail="Invalid date: This month only has 30 days.")
        
    if month_int == 2:
        is_leap_year = (year_int % 4 == 0 and year_int % 100 != 0) or (year_int % 400 == 0)
        if is_leap_year and day_int > 29:
            raise HTTPException(status_code=400, detail="Invalid date: February has only 29 days in a leap year.")
        elif not is_leap_year and day_int > 28:
            raise HTTPException(status_code=400, detail="Invalid date: February has only 28 days in a non-leap year.")
            
    return f"{year_int:04d}-{month_int:02d}-{day_int:02d}T{hour_int:02d}:{minute_int:02d}:{second_int:02d}"

def format_deadline_string(deadline_str: str | None):
    parsed = parse_datetime_input(deadline_str)
    
    if parsed is None:
        return None
        
    dt = datetime.fromisoformat(parsed)
    if dt <= datetime.now():
        raise HTTPException(status_code=400, detail="Deadline must be a date and time in the future.")
            
    return parsed