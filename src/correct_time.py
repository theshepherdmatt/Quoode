import time
import datetime

def wait_for_correct_time(threshold_year=2023, timeout=60):
    """
    Polls system time until the year is at least `threshold_year` or `timeout` seconds pass.
    """
    start = time.time()
    while time.time() - start < timeout:
        now = datetime.datetime.now()
        if now.year >= threshold_year:
            print(f"System time is now {now}, considered 'correct'.")
            return True
        time.sleep(1)
    print(f"Time did not reach year {threshold_year} within {timeout} seconds.")
    return False
