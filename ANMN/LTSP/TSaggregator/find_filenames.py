
#!/usr/bin/env python
# -*- coding: utf-8 -*-
from __future__ import print_function
import sys
import argparse
from datetime import datetime
import pandas as pd
import csv

# dictionary of variables names
# this will change if the retunn file from the service change. Not good for chlorophyll, current
var_names_dict = {'TEMP':               'has_water_temperature',
                 'PSAL':                'has_salinity',
                 'VCUR':                'has_sea_water_velocity',
                 'UCUR':                'has_sea_water_velocity',
                 'WCUR':                'has_sea_water_velocity',
                 'PRES':                'has_water_pressure',
                 'PRES_REL':            'has_water_pressure',
                 'OXYGEN_UMOL_PER_L':   'has_oxygen',
                 'CHLU':                'has_chlorophyll',
                 'CHLF':                'has_chlorophyll',
                 'CPHL':                'has_chlorophyll'}




def args():
    """
    argument parser
    """

    allowed_features=['profile', 'timeseries', 'timeseriesprofile']

    parser = argparse.ArgumentParser()
    parser.add_argument('var', help='name of the variable to find in the files, like TEMP')
    parser.add_argument('site', help='site code, like NRMMAI')
    parser.add_argument('-t_start', help='start time like 2015-12-01. Default: 1944-10-15', default='1944-10-15', required=False)
    parser.add_argument('-t_end', help='End time like 2018-06-30. Default: today\'s date', default=str(datetime.now())[:10], required=False)
    parser.add_argument('-feature', nargs='*', help='feature type: profile, timeseries, timeseriesprofile. Default: all', default=allowed_features, required=False)
    parser.add_argument('-out', dest='out_filename', help='name of the file to store the selected files info. Default: fileList.csv', default="fileList.csv")
    vargs = parser.parse_args()

    if len(sys.argv) == 0:
        msg = "ERROR: no args given."
        sys.exit(msg)

    if isinstance(vargs.var, type(None)):
        msg = "ERROR: no variable name given."
        sys.exit(msg)

    if vargs.var not in var_names_dict.keys():
        msg = "ERROR: %s is not a valid variable name." % vargs.var
        sys.exit(msg)

    if isinstance(vargs.site, type(None)):
        msg = "ERROR: no site code name given."
        sys.exit(msg)

    if not all(items in allowed_features for items in vargs.feature):
        msg = 'ERROR: not a valid feature.'
        sys.exit(msg)

    return vargs




def write_filenames(filenames, out_filename):
    """
    Write the list of file addresses to csv file
    """

    with open(out_filename, "w") as outfile:
        for names in filenames:
            outfile.write(names)
            outfile.write("\n")



def find_filenames(var, site, feature, t_start, t_end):
    """
    get the file names and attr from the geoserver
    Only FV01 files and feature_type CTD_timeseries
    var:            Variable name as it appears in the file
    site:           Site code as it appears in the file
    t_start:        time_coverage_start of the first file
    t_end:          time_coverage_end of the last file
    returns a list with the names address of the files
    """
    web_root = 'http://thredds.aodn.org.au/thredds/dodsC/'

    url = "http://geoserver-123.aodn.org.au/geoserver/ows?typeName=moorings_all_map&SERVICE=WFS&REQUEST=GetFeature&VERSION=1.0.0&outputFormat=csv&CQL_FILTER=(file_version='1'%20AND%20realtime=FALSE)"

    geoserver_files = pd.read_csv(url)

    # set the filtering criteria
    criteria_site = geoserver_files['site_code'] == site
    if criteria_site.sum() == 0:
        sys.exit('ERROR: invalid site.')

    criteria_variable = geoserver_files[var_names_dict[var]]
    if criteria_variable.sum() == 0:
        sys.exit('ERROR: invalid variable.')

    criteria_feature = geoserver_files['feature_type'].str.lower().isin(feature)
    if criteria_variable.sum() == 0:
        sys.exit('ERROR: invalid or no feature type present.')

    criteria_startdate = pd.to_datetime(geoserver_files.time_coverage_start) >= datetime.strptime(t_start, '%Y-%m-%d')
    if criteria_startdate.sum() == 0:
        sys.exit('ERROR: invalid start date')

    criteria_enddate = pd.to_datetime(geoserver_files.time_coverage_end) <= datetime.strptime(t_end, '%Y-%m-%d')
    if criteria_enddate.sum() == 0:
        sys.exit('ERROR: invalid end date')

    criteria_all = criteria_site & criteria_variable & criteria_startdate & criteria_enddate & criteria_feature

    files = list(web_root + geoserver_files.url[criteria_all])


    if len(files)<=1:
        sys.exit('NONE or only ONE file found')

    write_filenames(files, vargs.out_filename)



if __name__ == "__main__":
    vargs = args()
    find_filenames(vargs.var, vargs.site, vargs.feature, vargs.t_start, vargs.t_end)
    print('File names addresses written to %s' % (vargs.out_filename))
