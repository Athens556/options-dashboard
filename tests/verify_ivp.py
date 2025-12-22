
import pandas as pd
import numpy as np
import utils

def test_iv_percentile_calculation():
    print("Testing calculate_iv_percentile...")
    
    # Create synthetic IV series
    # Increasing trend
    dates = pd.date_range(start='2023-01-01', periods=300)
    values = np.linspace(10, 30, 300) # IV goes from 10 to 30
    iv_series = pd.Series(values, index=dates)
    
    # Calculate IVP (window 252)
    ivp = utils.calculate_iv_percentile(iv_series, period=252)
    
    # Check last value: Should be 100 (highest in window)
    last_ivp = ivp.iloc[-1]
    print(f"Last IVP (should be approx 100): {last_ivp}")
    
    if abs(last_ivp - 100) < 1:
        print("Success: Last IVP is correct.")
    else:
        print(f"Failure: Last IVP {last_ivp} is incorrect.")
        
    # Check middle value
    # At index 200, window is [0:200] (length 200 < 252, but > min_periods 126)
    # Value at 200 is higher than previous, so should be 100 too if strictly increasing
    mid_ivp = ivp.iloc[200]
    print(f"Mid IVP (should be approx 100): {mid_ivp}")

    # Random series
    np.random.seed(42)
    random_iv = pd.Series(np.random.normal(20, 5, 500), index=pd.date_range(start='2023-01-01', periods=500))
    ivp_random = utils.calculate_iv_percentile(random_iv, period=252)
    
    print(f"Random Series Last IVP: {ivp_random.iloc[-1]}")
    print(f"Random Series Mean IVP: {ivp_random.mean()}")
    
    if not ivp_random.isna().all():
        print("Success: Random IVP calculation produced values.")

if __name__ == "__main__":
    test_iv_percentile_calculation()
