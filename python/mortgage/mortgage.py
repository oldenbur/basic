#!/usr/local/bin/python3

# see: http://pbpython.com/amortization-model.html
# pip3 install pandas

import pandas as pd
import numpy as np
from datetime import date

Interest_Rate = 0.04625
Years = 30
Payments_Year = 12
Principal = 296000
Addl_Princ = 650 
start_date = (date(2019,5,1))

for per in range(1, 360):

    # Calculate the interest
    ipmt = np.ipmt(Interest_Rate/Payments_Year, per, Years*Payments_Year, Principal)
    
    # Calculate the principal
    ppmt = np.ppmt(Interest_Rate/Payments_Year, per, Years*Payments_Year, Principal)
    
    print('{: 5d}  {:9.2f}  {:9.2f}  {:9.2f}'.format(per, ipmt, ppmt, ipmt + ppmt))

