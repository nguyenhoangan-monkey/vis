import pandas as pd
import matplotlib.pyplot as plt

def main():

#To do: make more robust by checking whether the data aligns with what the columns say.
#To do: combine multiple spreadsheets and see how data aligns.
     
    print("Below is the original CSV converted to a Pandas dataframe, BUT with a new column appended! It is labeled \"datetime,\" and comes from appending the \"Date\" and \"Time\" columns, then converting to a datetime object.")
    print()

    UPSdata = pd.read_csv("UPS-1-1-2025 to 4-7-2025.csv")
    UPSdata["datetime"] = pd.to_datetime(UPSdata['Date']+" "+UPSdata['Time']) 
    print(UPSdata)
    print()

    print("Below is a resampling of the dataframe above that takes the average of \"Watts Out (avg)\" in 15 minute blocks based on the datetime column, as described in my 4/24/25 email. I did not check this for bugs.")
    print()

    UPSblocks=UPSdata.resample('15min', on='datetime',closed = 'left')['Watts Out (avg)'].mean()
    print(UPSblocks)
    
    print()
    print("Now I will try to plot the data using a quick and dirty matplotlib plot")
    UPSblocks.plot()
    plt.show()


#To do: split main() into a "split(start, end, freq, target)" once everything works!
    # split(earliestAgreed , latestAgreed , frequency , UPSdata)

if __name__ == '__main__':
    main()
