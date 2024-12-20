# GAN_SR_wind_field
Super resolve 3D wind flow based on data from the HARMONIE-SIMRA model, https://asmedigitalcollection.asme.org/OMAE/proceedings-abstract/OMAE2017/57786/V010T09A051/282088?redirectedFrom=PDF.

Dependencies for the python 3.9 environment are listed in requirements.txt. 

The model is trained, tested or used in a parameter seach by running the run.py file. Hyperparameters are set in the Config folder.

The model and test results, are thoroughly described in the following master thesis: [INSERT LINK WHEN AVAILABLE]

This work is besed on Vesterkjær 2019's implementation of ESRGAN, https://github.com/eirikeve/esrdgan/tree/master. It is therefore subject to APACHE licence, described in the LICENSE.txt file


## Running the code
This code was developed using Python version 3.9. There will be dependency conflicts if other versions are used.

### Installing everything

Clone the repository using:

```bash
git clone git@github.com:inductiva/GAN_SR_wind_field.git
```
Create a virtual environment to solve solve any clashes with the library versions used here and anything else that might be installed in your own system:

```bash
python3.9 -m venv .env
source .env/bin/activate
```
After creating and activating the virtual environment install all the requirements of the project using:

```bash
pip install -r requirements.txt
```

### Downloading the training data

First modify the config files to specify the extend of the training data, by specifying the start and end date.  Other training parameters and hyper-parameters can also be edited here. 

Once the configuration file is ready, download the raw data and then create training, validation and test datasets from HARMONIE-SIMRA data using the following command.

```bash
python run.py --download
```
### Train the model
Start model training using the following comand

```bash
python run.py --train
```
The trained model can be now tested and used by using --test and --use flags.

The z interpolation feature cannot be used as of now. It is being fixed.