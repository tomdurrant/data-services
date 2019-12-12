New Zealand Defence Technology Agency Southern Ocean Deployments
===================================================================

This script aims to convert wave files from triaxys format (.WAVE).

The data was collected on two different deployments in the Southern Ocean:


## Using the Script

```bash
usage: on_wave_dm_process.py [-h] -i DATASET_PATH [-o OUTPUT_PATH]

Creates FV01 NetCDF files. Prints out the
path of the new locally generated FV01 file.

optional arguments:
  -h, --help            show this help message and exit
  -i DATASET_PATH, --wave-dataset-org-path DATASET_PATH
                        path to original wave dataset
  -o OUTPUT_PATH, --output-path OUTPUT_PATH
                        output directory of FV01 netcdf file. (Optional)

```
Example:
on_wave_dm_process.py -i AODN/DTA -o /tmp

## Contact Support
for support contact:
Email: laurent.besnard@utas.edu.au
