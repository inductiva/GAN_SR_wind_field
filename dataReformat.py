from netCDF4 import Dataset
from  datetime import datetime, timedelta, time
import numpy as np
import os

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
        nc_fid = Dataset(filename, mode="r")

        #Getting the start and end dates of the dataset and accounting for spin up time
        t = nc_fid["time"][:]

        #Extract the date and time of the data in the file
        time_units = nc_fid["time"].getncattr("units")
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
        print("    Post spin-up start date:", data_start)
        run_time = (end_date - data_start).total_seconds()
        usable_data= timedelta(seconds=t[-1]) -spinUpTime
        print(f"    Usable data           :{usable_data} hrs")
        print(f"    Data used             :{timedelta(seconds=run_time)} hrs")
        spinUpTime_s = spinUpTime.total_seconds()

        #Accounting for spin-up time based on the start date
        if start_date>data_start:
            start_offset= (start_date - data_start).total_seconds()
            spinUp_indice=int((spinUpTime_s+start_offset)/sampling_rate)
        else:
            spinUp_indice = int(spinUpTime_s/sampling_rate)
            start_date = data_start
        last_indice = spinUp_indice + int(run_time/sampling_rate)

        #Loading the data
        t= t[spinUp_indice:last_indice]
        z = nc_fid["z"][:,0,0]

        #Creating a mock-sigma coordinate 
        z_len = len(z)
        l = np.linspace(1,z_len,z_len)

        y = nc_fid["y"][0,:,0]
        x = nc_fid["x"][0,0,:]
        h = nc_fid["z"][:,:,:]
        u= nc_fid["u"][spinUp_indice:last_indice,:,:,:]
        v= nc_fid["v"][spinUp_indice:last_indice,:,:,:]
        w= nc_fid["w"][spinUp_indice:last_indice,:,:,:]
        p= nc_fid["p"][spinUp_indice:last_indice,:,:,:]

        # Reverse the l dimension
        l = l[::-1]  # Flip l
        # Flip variables along the l dimension (z-axis)
        z = z[::-1]
        h = h[::-1, :, :]
        u = u[:, ::-1, :, :]
        v = v[:, ::-1, :, :]
        w = w[:, ::-1, :, :]
        p = p[:, ::-1, :, :]

        #Split data for each day -2 files per day
        split_and_save_data(t, x, y, l, h, u, v, w, p, destination_folder, start_date, end_date)
        nc_fid.close()

    except Exception as e:
        print("File not found or error:", e)
    
def create_netCDF(t, x, y, l, h, u, v, w, p, destination_folder, filename):

    # Creating the new netCDF file
    filename = os.path.join(destination_folder, filename)
    new_nc_fid = Dataset(filename, mode="w", format="NETCDF4")

    # Create corresponding variables for x, y, z in the new file
    time_dim = new_nc_fid.createDimension('time', len(t) )  # Create time dimension
    x_dim = new_nc_fid.createDimension('x', len(x))  # Create x variable
    y_dim = new_nc_fid.createDimension('y', len(y))  # Create y variable
    z_dim = new_nc_fid.createDimension('l', len(l))  # Create z variable

    #Creating the geopotentail height variable
    g = np.broadcast_to(h, (len(t), len(l), len(y), len(x)))
    
    # Creating variables in the new file
    time_var = new_nc_fid.createVariable("time", t.dtype, ("time",))
    z_var = new_nc_fid.createVariable("l", l.dtype, ("l"))
    y_var = new_nc_fid.createVariable("y", y.dtype, ("y")) 
    x_var = new_nc_fid.createVariable("x", x.dtype, ("x"))
    geoz_var = new_nc_fid.createVariable("geopotential_height_ml", g.dtype, ("time", "l", "y", "x"))
    alt_var = new_nc_fid.createVariable("surface_altitude", l.dtype, ("y", "x"))
    u_var = new_nc_fid.createVariable("x_wind_ml", u.dtype, ("time", "l", "y", "x"))
    v_var = new_nc_fid.createVariable("y_wind_ml", v.dtype, ("time", "l", "y", "x"))
    w_var = new_nc_fid.createVariable("upward_air_velocity_ml", w.dtype, ("time", "l", "y", "x"))
    p_var = new_nc_fid.createVariable("air_pressure_ml", p.dtype, ("time", "l", "y", "x")) 

    # Copying data into the new variables
    time_var[:] = t
    z_var[:] = l
    y_var[:] = y
    x_var[:] = x
    geoz_var[:,:,:,:] = g
    alt_var[:,:] = h[0,:,:]
    u_var[:] = u
    v_var[:] = v
    w_var[:] = w
    p_var[:] = p

    # Adding attributes
    new_nc_fid.description = "Reformatted Perdigao data"

    # Close the new NetCDF file
    new_nc_fid.close()

def split_and_save_data(t, x, y, l, h, u, v, w, p, destination_folder, start_date, end_date):
    # Splitting the data into daily files
    date = start_date
    start_indice, end_indice = 0,0
    initial_time = t[0]
    #Initializing loop variables
    loop_time = date + timedelta(seconds=t[0])-timedelta(seconds=initial_time)
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
                print("File exists: ", filename)
            else:
                #Variables definition and call create function
                t_ = t[start_indice:end_indice]
                u_ = u[start_indice:end_indice]
                v_ = v[start_indice:end_indice]
                w_ = w[start_indice:end_indice]
                p_ = p[start_indice:end_indice]
                create_netCDF(t_, x, y, l, h, u_, v_, w_, p_, destination_folder, filename)
                print("File created: ", filename)
                #The above duplication of lines can be eliminated by creating a 
                #function that does this job, but would require passing the variabels
                #around once more. Will that cause memory usage increase?
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
                print("File exists: ", filename)
            else:
                #Variables definition and call create function
                t_ = t[start_indice:end_indice]
                u_ = u[start_indice:end_indice]
                v_ = v[start_indice:end_indice]
                w_ = w[start_indice:end_indice]
                p_ = p[start_indice:end_indice]
                create_netCDF(t_, x, y, l, h, u_, v_, w_, p_, destination_folder, filename)
                print("File created: ", filename)
        else:
            cache_time = cache_time + timedelta(seconds=t[i+1])- timedelta(seconds=t[i])
        
        start_indice = end_indice
        
