#!/usr/bin/env python
# -*- coding: utf-8 -*-
import argparse
import difflib
import os
import sys
import tempfile
from ConfigParser import SafeConfigParser
from datetime import datetime

import numpy as np
import numpy.ma as ma
from netCDF4 import Dataset, date2num

from generate_netcdf_att import generate_netcdf_att, get_imos_parameter_info
from ship_callsign import ship_callsign_list
from imos_logging import IMOSLogging
from xbt_line_vocab import xbt_line_info


class XbtException(Exception):
    pass


def _error(message):
    " Raise an exception with the given message."
    raise XbtException('In File \"%s\":\n%s' % (NETCDF_FILE_PATH, message))


def _call_parser(conf_file):
    """ parse a config file """
    parser = SafeConfigParser()
    parser.optionxform = str  # to preserve case
    conf_file_path = os.path.join(os.path.dirname(os.path.realpath(__file__)), conf_file)
    parser.read(conf_file_path)
    return parser


def invalid_to_ma_array(invalid_array, fillvalue=0):
    """
    returns a masked array from an invalid XBT variable
    """
    masked = []
    array  = []
    for val in invalid_array:
        val = val.replace(' ', '')
        if val == '':
            masked.append(True)
            array.append(np.inf)
        else:
            masked.append(False)
            array.append(int(val))

    array = ma.array(array, mask=masked, fill_value=fillvalue)
    array = ma.fix_invalid(array)
    array = ma.array(array).astype(int)
    return array


def parse_edited_nc(netcdf_file_path):
    """ Read an edited XBT file written in an un-friendly NetCDF format
    global attributes, data and annex information are returned

    gatts, data, annex = parse_edited_nc(netcdf_file_path)
    """
    LOGGER.info('Parsing %s' % netcdf_file_path)
    netcdf_file_obj = Dataset(netcdf_file_path, 'r', format='NETCDF4')
    no_prof      = netcdf_file_obj['No_Prof'][0]
    data_avail   = netcdf_file_obj['Data_Avail'][0]
    dup_flag     = netcdf_file_obj['Dup_Flag'][0]
    ident_code   = netcdf_file_obj['Ident_Code'][:]
    woce_date    = netcdf_file_obj['woce_date'][0]
    woce_time    = netcdf_file_obj['woce_time'][0]
    q_date_time  = int(netcdf_file_obj['Q_Date_Time'][0])
    latitude     = netcdf_file_obj['latitude'][0]
    longitude    = netcdf_file_obj['longitude'][0]
    q_pos        = netcdf_file_obj['Q_Pos'][0]

    for i in range(0,no_prof):
        prof_type    = ''.join(netcdf_file_obj['Prof_Type'][:][i]).strip()
        if prof_type == 'TEMP':
            temp_prof = i
            break

    # position QC
    if q_pos == '1':
        q_pos = 1
    else:
        q_pos = 0

    cruise_id    = ''.join(netcdf_file_obj['Cruise_ID'][:]).strip()
    deep_depth   = netcdf_file_obj['Deep_Depth'][temp_prof]
    srfc_code_nc = netcdf_file_obj['SRFC_Code'][:]
    srfc_parm    = netcdf_file_obj['SRFC_Parm'][:]

    # previous values history. same indexes and dimensions of all following vars
    act_code     = filter(None, [''.join(val).strip() for val in netcdf_file_obj['Act_Code'][:]])
    act_parm     = filter(None, [''.join(val).strip() for val in netcdf_file_obj['Act_Parm'][:]])
    prc_code     = filter(None, [''.join(val).strip() for val in netcdf_file_obj['PRC_Code'][:]])
    prc_date     = filter(None, [''.join(val).strip() for val in netcdf_file_obj['PRC_Date'][:]])
    prc_date     = [datetime.strptime(date, '%Y%m%d') for date in prc_date]
    aux_id       = filter(None, netcdf_file_obj['Aux_ID'][:])  # deoth value of modified act_parm var modified
    version_soft = filter(None, [''.join(val).strip() for val in netcdf_file_obj['Version'][:]])
    previous_val = [float(val) for val in filter(None, [''.join(val).strip() for val in netcdf_file_obj['Previous_Val'][:]])]

    xbt_date = '%sT%s' % (woce_date, str(woce_time).zfill(6))  # add leading 0
    xbt_date = datetime.strptime(xbt_date, '%Y%m%dT%H%M%S')

    xbt_config = _call_parser('xbt_config')
    if 'SRFC_CODES' in xbt_config.sections():
        srfc_code_list = dict(xbt_config.items('SRFC_CODES'))
    else:
        _error('xbt_config file not valid')

    # read a list of srfc code defined in the srfc_code conf file. Create a
    # dictionnary of matching values
    gatts = {}
    for i in range(len(srfc_code_nc)):
        srfc_code_iter = ''.join(srfc_code_nc[i])
        if srfc_code_iter in srfc_code_list.keys():
            att_name = srfc_code_list[srfc_code_iter].split(',')[0]
            att_type = srfc_code_list[srfc_code_iter].split(',')[1]
            att_val  = ''.join(srfc_parm[i]).strip()
            if att_val.replace(' ', '') != '':
                gatts[att_name] = att_val
                try:
                    if att_type == 'float':
                        gatts[att_name] = float(gatts[att_name].replace(' ', ''))
                    elif att_type == 'int':
                            gatts[att_name] = int(gatts[att_name].replace(' ', ''))
                except ValueError:
                    LOGGER.warning('"%s = %s" could not be converted to %s()' % (att_name, gatts[att_name], att_type.upper()))

        else:
            if srfc_code_iter != '':
                LOGGER.warning('%s code is not defined in srfc_code conf file. Please edit conf' % srfc_code_iter)

    # cleaning
    att_name = 'XBT_probetype_fallrate_equation'
    if att_name in gatts.keys():
        gatts[att_name] = ('See WMO Code Table 1770 for the information corresponding to the value: %s' % gatts[att_name])

    att_name = 'XBT_recorder_type'
    if att_name in gatts.keys():
        gatts[att_name] = ('See WMO Code Table 4770 for the information corresponding to the value: %s' % gatts[att_name])

    att_name = 'XBT_height_launch_above_water_in_meters'
    if att_name in gatts.keys():
        if gatts[att_name] > 30:
            LOGGER.warning('HTL$, xbt launch height attribute seems to be very heigh: %s meters' % gatts[att_name])

    gatts['geospatial_vertical_max'] = deep_depth
    gatts['XBT_cruise_ID']           = cruise_id
    gatts['XBT_input_filename']      = os.path.basename(netcdf_file_path)

    # get xbt line information from config file
    xbt_line_conf_section = [s for s in xbt_config.sections() if gatts['XBT_line'] in s]
    xbt_alt_codes = [s for s in XBT_LINE_INFO.keys() if XBT_LINE_INFO[s] is not None]  # alternative IMOS codes taken from vocabulary
    if xbt_line_conf_section != []:
        xbt_line_att = dict(xbt_config.items(xbt_line_conf_section[0]))
        gatts.update(xbt_line_att)
    elif gatts['XBT_line'] in xbt_alt_codes:
        xbt_line_conf_section = [s for s in xbt_config.sections() if XBT_LINE_INFO[gatts['XBT_line']] == s]
        xbt_line_att = dict(xbt_config.items(xbt_line_conf_section[0]))
        gatts.update(xbt_line_att)
    else:
        LOGGER.error('XBT line : "%s" is not defined in conf file(Please edit), or an alternative code has to be set up by AODN in vocabs.ands.org.au(contact AODN)' % gatts['XBT_line'])
        exit(1)

    depth_press      = netcdf_file_obj['Depthpress'][temp_prof]
    depth_press_flag = netcdf_file_obj['DepresQ'][temp_prof].flatten()
    depth_press_flag = invalid_to_ma_array(depth_press_flag, fillvalue=0)  # replace masked values to 0 for IMOS IODE flags

    if isinstance(netcdf_file_obj['Profparm'][temp_prof], np.ma.MaskedArray):
        prof = np.ma.masked_where(netcdf_file_obj['Profparm'][temp_prof].data > 50, netcdf_file_obj['Profparm'][temp_prof])
    else:
        prof = np.ma.masked_where(netcdf_file_obj['Profparm'][temp_prof] > 50, netcdf_file_obj['Profparm'][temp_prof])
        prof.set_fill_value(-99.99)

    prof_flag = netcdf_file_obj['ProfQP'][temp_prof].flatten()
    prof_flag = invalid_to_ma_array(prof_flag, fillvalue=99)  # replace masked values for IMOS IODE flags

    data = {}
    data['LATITUDE']                  = latitude
    data['LATITUDE_quality_control']  = q_pos
    data['LONGITUDE']                 = longitude
    data['LONGITUDE_quality_control'] = q_pos
    data['TIME']                      = xbt_date
    data['TIME_quality_control']      = q_date_time

    if isinstance(depth_press, np.ma.MaskedArray):
        data['DEPTH']                     = depth_press[~ma.getmask(depth_press)]  # DEPTH is a dimension, so we remove mask values, ie FillValues
        data['DEPTH_quality_control']     = depth_press_flag[~ma.getmask(depth_press)]
        data['TEMP']                      = prof[~ma.getmask(depth_press)]
        data['TEMP_quality_control']      = prof_flag[~ma.getmask(depth_press)]
    else:
        data['DEPTH']                     = depth_press
        data['DEPTH_quality_control']     = depth_press_flag
        data['TEMP']                      = prof
        data['TEMP_quality_control']      = prof_flag

    annex                 = {}
    annex['dup_flag']     = dup_flag
    annex['ident_code']   = ident_code
    annex['data_avail']   = data_avail
    annex['act_code']     = act_code
    annex['act_parm']     = act_parm
    annex['aux_id']       = aux_id
    annex['prc_code']     = prc_code
    annex['prc_date']     = prc_date
    annex['version_soft'] = version_soft
    annex['no_prof']      = no_prof
    annex['prof_type']    = prof_type
    annex['previous_val'] = previous_val

    netcdf_file_obj.close()
    return gatts, data, annex


def create_filename_output(gatts, data):
    filename = 'XBT_T_%s_%s_FV01_ID-%s' % (data['TIME'].strftime('%Y%m%dT%H%M%SZ'), gatts['XBT_line'], gatts['XBT_uniqueid'])

    if data['TIME'] > datetime(2008, 01, 01):
        filename = 'IMOS_SOOP-%s' % filename

    if '/' in filename:
        LOGGER.error('The sign \'/\' is contained inside the NetCDF filename "%s". Likely '
                     'due to a slash in the XTB_line attribute. Please ammend '
                     'the XBT_line attribute in the config file for the XBT line "%s"'
                     % (filename, gatts['XBT_line']))
        exit(1)

    return filename


def check_nc_to_be_created(annex):
    """ different checks to make sure we want to create a netcdf for this profile
    """
    if annex['dup_flag'] == 'D':
        LOGGER.error('Profile not processed. Tagged as duplicate in original netcdf file')
        return False

    if 'TP' in annex['act_code'] or 'DU' in annex['act_code']:
        LOGGER.error('Profile not processed. Tagged as duplicate in original netcdf file')
        return False

    #    if annex['no_prof'] > 1:
    #        LOGGER.error('Profile not processed. No_Prof variable is greater than 0')
    #        return False

    if annex['prof_type'] != 'TEMP':
        LOGGER.error('Profile not processed. Main variable is not TEMP')
        return False

    return True


def create_nc_history_list(annex):
    """ create the history netcdf attribute based on data values change"""
    xbt_config = _call_parser('xbt_config')
    if 'ACT_CODES' in xbt_config.sections():
        act_code_list = dict(xbt_config.items('ACT_CODES'))
    else:
        _error('xbt_config file not valid')

    history = []
    for idx, date in enumerate(annex['prc_date']):
        if annex['act_code'][idx] in act_code_list:
            act_code_def = act_code_list[annex['act_code'][idx]]
        else:
            act_code_def = annex['act_code'][idx]
            LOGGER.warning("ACT CODE \"%s\" is not defined. Please edit config file" % annex['act_code'][idx])

        history.append("%s - CSIRO QC Cookbook software version %s: "
                       "Previous value %s=%s at DEPTH=%s - "
                       "Action performed on parameter: %s(%s)\n" %
                       (date.strftime('%a %b %d %H:%M:%S %Y'),
                        annex['version_soft'][idx],
                        annex['act_parm'][idx],
                        annex['previous_val'][idx],
                        annex['aux_id'][idx],
                        annex['act_code'][idx],
                        act_code_def))

    return ''.join(history)


def generate_xbt_nc(gatts, data, annex, output_folder):
    """create an xbt profile"""
    netcdf_filepath = os.path.join(output_folder, "%s.nc" % create_filename_output(gatts, data))
    LOGGER.info('Creating output %s' % netcdf_filepath)

    output_netcdf_obj = Dataset(netcdf_filepath, "w", format="NETCDF4")
    # set global attributes
    for gatt_name in gatts.keys():
        setattr(output_netcdf_obj, gatt_name, gatts[gatt_name])

    history_att = create_nc_history_list(annex)
    if history_att != '':
        setattr(output_netcdf_obj, 'history', history_att)

    # this will overwrite the value found in the original NetCDF file
    ships = SHIP_CALL_SIGN_LIST
    if gatts['Platform_code'] in ships:
        output_netcdf_obj.ship_name = ships[gatts['Platform_code']]
        output_netcdf_obj.Callsign  = gatts['Platform_code']
    elif difflib.get_close_matches(gatts['Platform_code'], ships, n=1, cutoff=0.8) != []:
        output_netcdf_obj.Callsign      = difflib.get_close_matches(gatts['Platform_code'], ships, n=1, cutoff=0.8)[0]
        output_netcdf_obj.Platform_code = output_netcdf_obj.Callsign
        output_netcdf_obj.ship_name     = ships[output_netcdf_obj.Callsign]
        LOGGER.warning('Vessel call sign %s seems to be wrong. Using his closest match to the AODN vocabulary: %s' % (gatts['Platform_code'], output_netcdf_obj.Callsign))
    else:
        LOGGER.warning('Vessel call sign %s is unknown in AODN vocabulary, Please contact info@aodn.org.au' % gatts['Platform_code'])

    output_netcdf_obj.date_created            = datetime.now().strftime("%Y-%m-%dT%H:%M:%SZ")
    output_netcdf_obj.geospatial_vertical_min = min(data['DEPTH'])
    output_netcdf_obj.geospatial_vertical_max = max(data['DEPTH'])
    output_netcdf_obj.geospatial_lat_min      = data['LATITUDE']
    output_netcdf_obj.geospatial_lat_max      = data['LATITUDE']
    output_netcdf_obj.geospatial_lon_min      = data['LONGITUDE']
    output_netcdf_obj.geospatial_lon_max      = data['LONGITUDE']
    output_netcdf_obj.time_coverage_start     = data['TIME'].strftime('%Y-%m-%dT%H:%M:%SZ')
    output_netcdf_obj.time_coverage_end       = data['TIME'].strftime('%Y-%m-%dT%H:%M:%SZ')

    output_netcdf_obj.createDimension('DEPTH', len(data['DEPTH']))
    output_netcdf_obj.createVariable("DEPTH", "f", "DEPTH")
    output_netcdf_obj.createVariable('DEPTH_quality_control', "b", "DEPTH")

    var_time = output_netcdf_obj.createVariable("TIME", "d", fill_value=get_imos_parameter_info('TIME', '_FillValue'))
    output_netcdf_obj.createVariable("TIME_quality_control", "b", fill_value=99)

    output_netcdf_obj.createVariable("LATITUDE", "f", fill_value=get_imos_parameter_info('LATITUDE', '_FillValue'))
    output_netcdf_obj.createVariable("LATITUDE_quality_control", "b", fill_value=99)

    output_netcdf_obj.createVariable("LONGITUDE", "f", fill_value=get_imos_parameter_info('LONGITUDE', '_FillValue'))
    output_netcdf_obj.createVariable("LONGITUDE_quality_control", "b", fill_value=99)

    output_netcdf_obj.createVariable("TEMP", "f", ["DEPTH"], fill_value=get_imos_parameter_info('TEMP', '_FillValue'))
    output_netcdf_obj.createVariable("TEMP_quality_control", "b", ["DEPTH"], fill_value=data['TEMP_quality_control'].fill_value)

    conf_file_generic = os.path.join(os.path.dirname(__file__), 'generate_nc_file_att')
    generate_netcdf_att(output_netcdf_obj, conf_file_generic, conf_file_point_of_truth=True)

    for var in data.keys():
        if var == 'TIME':
            time_val_dateobj = date2num(data['TIME'], output_netcdf_obj['TIME'].units, output_netcdf_obj['TIME'].calendar)
            var_time[:]      = time_val_dateobj
        else:
            output_netcdf_obj[var][:] = data[var]

    # default value for abstract
    if not hasattr(output_netcdf_obj, 'abstract'):
        setattr(output_netcdf_obj, 'abstract', output_netcdf_obj.title)

    output_netcdf_obj.close()
    return netcdf_filepath


def args():
    """ define input argument"""
    parser = argparse.ArgumentParser()
    parser.add_argument('-i', '--input-edited-xbt-path', type=str,
                        help="path to edited xbt file or folder containing edited xbt files")
    parser.add_argument('-o', '--output-folder', nargs='?', default=1,
                        help="output directory of generated files")
    parser.add_argument('-l', '--log-file', nargs='?', default=1,
                        help="log directory")
    vargs = parser.parse_args()

    if vargs.output_folder == 1:
        vargs.output_folder = tempfile.mkdtemp(prefix='xbt_dm_')
    elif not os.path.isabs(os.path.expanduser(vargs.output_folder)):
        vargs.output_folder = os.path.join(os.getcwd(), vargs.output_folder)

    if vargs.log_file == 1:
        vargs.log_file = os.path.join(vargs.output_folder, 'xbt.log')
    else:
        if not os.path.exists(os.path.dirname(vargs.log_file)):
            os.makedirs(os.path.dirname(vargs.log_file))

    if not os.path.exists(vargs.input_edited_xbt_path):
        msg = '%s not a valid path' % vargs.input_edited_xbt_path
        print >> sys.stderr, msg
        sys.exit(1)
    if not os.path.exists(vargs.output_folder):
        os.makedirs(vargs.output_folder)

    return vargs


def process_xbt_file(xbt_file_path, output_folder):
    gatts, data, annex = parse_edited_nc(xbt_file_path)
    if check_nc_to_be_created(annex):
        generate_xbt_nc(gatts, data, annex, output_folder)


def global_vars(vargs):
    global LOGGER
    logging = IMOSLogging()
    LOGGER  = logging.logging_start(vargs.log_file)

    global NETCDF_FILE_PATH  # defined as glob to be used in exception

    global SHIP_CALL_SIGN_LIST
    SHIP_CALL_SIGN_LIST = ship_callsign_list()  # AODN CALLSIGN vocabulary

    global XBT_LINE_INFO
    XBT_LINE_INFO = xbt_line_info()


if __name__ == '__main__':
    os.umask(0o002)
    vargs = args()
    global_vars(vargs)

    # dealing with input folder or input file
    if vargs.input_edited_xbt_path.endswith('ed.nc'):
        NETCDF_FILE_PATH = vargs.input_edited_xbt_path
        process_xbt_file(NETCDF_FILE_PATH, vargs.output_folder)

    else:
        result = [os.path.join(dp, f) for dp, dn, filenames in os.walk(vargs.input_edited_xbt_path) for f in filenames if f.endswith('ed.nc')]
        for f in result:
            NETCDF_FILE_PATH = f
            process_xbt_file(NETCDF_FILE_PATH, vargs.output_folder)
