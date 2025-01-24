from netCDF4 import Dataset
from  datetime import datetime, timedelta, time
import numpy as np
import os
import xarray as xr

def perdigao_data_reformat(start_date,
                           start_time,
                           end_date,
                           end_time,
                           destination_folder,
                           source_folder
                           ):
    filename = "af_output.nc"
    filename = os.path.join(source_folder, filename)
    start_date = datetime.combine(start_date, time(start_time))
    end_date = datetime.combine(end_date, time(end_time))
    spinUpTime = timedelta(hours=6)
    sampling_rate = 5*60 #5 minutes
    try:
        ds = xr.open_dataset(filename, decode_times=False)

        #Getting the start and end dates of the dataset and accounting for spin up time
        t = ds['time'].values

        # Extract time units attribute
        time_units = ds.time.attrs["units"]

        # Parse the units string to extract the start date and time
        if "since" in time_units:
            start_datetime_str = time_units.split("since")[1].strip()
            data_start = datetime.strptime(start_datetime_str, "%Y-%m-%d %H:%M:%S")
            available_data = timedelta(seconds=t[-1])
            available_data = data_start + available_data
            print(f"    Data available from   :{data_start} to {available_data}")
        else:
            print("Start date/time not found in the data attributes")

        print(f"    Requested data        :{start_date} to {end_date}")
        print(f"    Spin up time          :{spinUpTime} hrs")

        #Verifying of the entered dates are available
        if available_data < end_date:
            print("    Data avialable only until ", available_data, ".. trimming datasetto available data")
            end_date = available_data

        if start_date < data_start:
            print(f"    Data avialable only from {data_start} .. trimming dataset to available data")

        if (end_date - data_start)<spinUpTime:
            print("Data available only for spin up time.. exiting")
            return
        
        data_start = data_start + spinUpTime
        run_time = (end_date - data_start).total_seconds()
        usable_data= timedelta(seconds=t[-1]) -spinUpTime
        spinUpTime_s = spinUpTime.total_seconds()
        print("    Post spin-up start date:", data_start)
        print(f"    Usable data           :{usable_data} hrs")
        print(f"    Data used             :{timedelta(seconds=run_time)} hrs")
        
        #Accounting for spin-up time based on the start date
        if start_date>data_start:
            start_offset= (start_date - data_start).total_seconds()
            spinUp_indice=int((spinUpTime_s+start_offset)/sampling_rate)
        else:
            spinUp_indice = int(spinUpTime_s/sampling_rate)
            start_date = data_start
        last_indice = spinUp_indice + int(run_time/sampling_rate)

        #Loading the data
        # Select the desired time range
        ds = ds.isel(time=slice(spinUp_indice, last_indice))

        # Alter x and y dimensions for specific variables
        h = ds['z'][:,:,:].data
        x = ds['x'][0, 0, :].data
        y = ds['y'][0, :, 0].data
        z = ds['z'][:, 0, 0].data
        t = ds['time'].data

        # Flip variables along the z-axis within the Dataset
        ds = ds.isel(z=slice(None, None, -1))

        # Create a new coordinate 'l'
        z_len = len(z)
        l = xr.DataArray(np.linspace(1, z_len, z_len), dims='z')

        # Create a new dataset with the new coordinates
        data = xr.Dataset(
            {
                'h': (['l', 'y', 'x'], h),
                'u': (['time', 'l', 'y', 'x'], ds['u'].data),
                'v': (['time', 'l', 'y', 'x'], ds['v'].data),
                'w': (['time', 'l', 'y', 'x'], ds['w'].data),
                'p': (['time', 'l', 'y', 'x'], ds['p'].data),
            },
            coords={
                'x': x,
                'y': y,
                'l': l,
                'time': t,
            }
        )
        ds.close() #closing ds to free up memory
        
        # Swap dimensions from z to l(mock sigma coordinate)
        data = data.swap_dims({'z': 'l'})

        #Split data for each day -2 files per day
        split_and_save_data(data, destination_folder, start_date, end_date)
        print("    Data split and saved successfully")
        

    except Exception as e:
        print("File not found or error:", e)
    
def create_netCDF(data, destination_folder, filename):

    # Creating the new netCDF file
    filename = os.path.join(destination_folder, filename)

    #Creating the geopotential height and surface altitude variables
    h = data['h']
    surface_altitude = data['h'].isel(l=-1)
    geopotential_height_ml = h.expand_dims(dim={'time': data.sizes['time']}).transpose('time', *h.dims)
 
    #Add geopotential height and surface altitude to the dataset
    data = data.assign(geopotential_height_ml=geopotential_height_ml)
    data = data.assign(surface_altitude=surface_altitude)

    #Remove `h` from the dataset
    data = data.drop_vars('h')
    
    #Renaming variables
    data = data.rename({'u': 'x_wind_ml', 'v': 'y_wind_ml', 'w': 'upward_air_velocity_ml', 'p': 'air_pressure_ml'})

    # Adding attributes
    data.to_netcdf(filename)

def split_and_save_data(data, destination_folder, start_date, end_date):
    # Splitting the data into daily files
    date = start_date
    start_indice, end_indice = 0,0
    t = data['time'].values
    initial_time = t[0]
    #Initializing loop variables
    loop_time = date
    next_date = date + timedelta(days=1)
    next_date = next_date.replace(hour=0, minute=0, second=0)

    #Files are to be produced for 12 hours of data, max cache variable checks if its time to output
    max_cache_time = timedelta(hours=12, minutes=0)
    cache_time = timedelta(seconds=0)

    for i in range(len(t)):
        loop_time = start_date + timedelta(seconds=t[i])-timedelta(seconds=initial_time)
        if cache_time >= max_cache_time:
            end_indice = i
            date_str = date.strftime("%Y%m%d")
            if loop_time.time()>= time(12,0):
                suffix = "T00Z"
            else:
                suffix = "T12Z"
                date = next_date
                next_date = date + timedelta(days=1)
                next_date = next_date.replace(hour=0, minute=0, second=0)

            filename = f"ventos_PERDIGAO_{date_str}{suffix}.nc"
            if os.path.exists(os.path.join(destination_folder, filename)):
                print(f"    File exists: {filename}")
            else:
                #Variables definition and call create function
                data_slice = data.isel(time=slice(start_indice, end_indice))
                create_netCDF(data_slice, destination_folder, filename)
                print(f"    File created: {filename}")
            start_indice = end_indice
            cache_time = timedelta(seconds=0)

        if i == len(t)-1:
            if loop_time.time()>= time(12,0):
                suffix = "T12Z"
            else:
                suffix = "T00Z"
            end_indice = i+1
            date_str = date.strftime("%Y%m%d")
            filename = f"ventos_PERDIGAO_{date_str}{suffix}.nc"
            
            if os.path.exists(os.path.join(destination_folder, filename)):
                print(f"    File exists: {filename}")
            else:
                data_slice = data.isel(time=slice(start_indice, end_indice))
                #Variables definition and call create function
                create_netCDF(data_slice, destination_folder, filename)
                print(f"    File created: {filename}")
        else:
            cache_time = cache_time + timedelta(seconds=t[i+1])- timedelta(seconds=t[i])
        
        start_indice = end_indice
        
