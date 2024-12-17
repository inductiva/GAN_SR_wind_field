# GAN_SR_wind_field
Super resolve 3D wind flow based on data from the HARMONIE-SIMRA model, https://asmedigitalcollection.asme.org/OMAE/proceedings-abstract/OMAE2017/57786/V010T09A051/282088?redirectedFrom=PDF.

Dependencies for the python 3.9 environment are listed in requirements.txt. 

The model is trained, tested or used in a parameter seach by running the run.py file. Hyperparameters are set in the Config folder.

The model and test results, are thoroughly described in the following master thesis: [INSERT LINK WHEN AVAILABLE]

This work is besed on Vesterkjær 2019's implementation of ESRGAN, https://github.com/eirikeve/esrdgan/tree/master. It is therefore subject to APACHE licence, described in the LICENSE.txt file


Usage Instructions:

    1- Clone the repo to local disk: $git clone https://github.com/inductiva/GAN_SR_wind_field.git
    2- Change directory: $cd GAN_SR_wind_field
    3- Create and activate virtual env (tested on python 3.9)
    4- Install dependencies: $pip install -r requirements.txt
    5- Modify config files (GAN_SR_wind_field/wind_field_GAN_3D_config_local.ini) to set target libraries
    6- Once the dependencies are installed, the code can be run as follows
        python run.py < --train | --test | --use > [ --cfg path/to/config.ini ] [ -h ]