import datetime
import logging
import os
import shutil
import tempfile

import numpy as np
import pandas as pd
from dateutil import parser as dt_parser
from netCDF4 import Dataset, date2num, stringtochar

from common import param_mapping_parser, set_var_attr, set_glob_attr, read_metadata_file
from generate_netcdf_att import generate_netcdf_att

logger = logging.getLogger(__name__)

ON_WAVE_PARAMETER_MAPPING = os.path.join(
    os.path.dirname(__file__), "on_wave_dm_parameters_mapping.csv"
)
NC_ATT_CONFIG = os.path.join(os.path.dirname(__file__), "generate_nc_file_att")


def metadata_info(station_path):
    """
    generate metadata dictionary from station_path folder name
    :param station_path:
    :return: dictionary of metadata
    """
    df = read_metadata_file()

    if "TAS01000" in station_path:
        site_code = "CIWRB"
    elif "TAS01970/" in station_path:
        site_code = "SOWRB"

    timezone = df.loc[site_code]["timezone"]
    timezone = dt_parser.parse(timezone[:]).time()

    return {
        "site_name": df.loc[site_code]["site_name"],
        "site_code": site_code,
        "latitude": df.loc[site_code]["latitude"],
        "longitude": df.loc[site_code]["longitude"],
        "timezone": timezone.hour + timezone.minute / 60.0,
        "title": "Waverider Buoy observations at {site_name}".format(
            site_name=df.loc[site_code]["site_name"]
        ),
        "instrument_maker": df.loc[site_code]["instrument_maker"],
        "instrument_model": df.loc[site_code]["instrument_model"],
        "waverider_type": df.loc[site_code]["waverider_type"],
        "water_depth": df.loc[site_code]["water_depth"],
        "water_depth_units": "meters",
        "wmo_id": df.loc[site_code]["wmo_id"],
    }


def parse_csv_on_wave(filepath):
    """
    parser for csv on wave files
    :param filepath:
    :return: dataframe of data
    """
    if filepath.endswith(".csv"):
        df = pd.read_csv(filepath, header=None, engine="python")

        if any(df[0] == "Time (UTC+10)"):
            time_var_name = "Time (UTC+10)"
        elif any(df[0] == "Time (UTC+9.5)"):
            time_var_name = "Time (UTC+9.5)"

        df2 = df.iloc[(df.loc[df[0] == time_var_name].index[0]) :, :].reset_index(
            drop=True
        )  # skip metadata lines
        df2.columns = df2.loc[0]  # set column header as first row
        df2.drop(df2.index[0], inplace=True)  # remove first row which was the header
        df2.rename(columns={time_var_name: "datetime"}, inplace=True)
        df2.rename(
            columns=lambda x: x.strip()
        )  # strip leading trailing spaces from header
        date_format = "%d/%m/%Y %H:%M"
        df2["datetime"] = pd.to_datetime(df2["datetime"], format=date_format)
        logger.warning("date format; {format}".format(format=date_format))
        df2.rename(columns={"Hs (m)": "Hs"}, inplace=True)

        return df2


def parse_txt_on_wave(filepath):
    """
    parser for csv on wave files
    :param filepath:
    :return: dataframe of data
    """
    if filepath.endswith(".txt"):
        col_lengths = {
            "datetime": range(1, 20),
            "Hs": range(20, 25),
            "Hrms": range(25, 30),
            "Hmax": range(30, 35),
            "Tz": range(35, 40),
            "Ts": range(40, 45),
            "Tc": range(45, 50),
            "THmax": range(50, 55),
            "EPS": range(55, 60),
            "T02": range(60, 65),
            "Tp": range(65, 70),
            "Hrms fd": range(70, 75),
            "EPS fd": range(75, 80),
        }
        col_lengths = {k: set(v) for k, v in col_lengths.items()}
        df = pd.read_fwf(
            filepath,
            skiprows=1,
            colspecs=[(min(x), max(x) + 1) for x in col_lengths.values()],
            header=None,
            names=col_lengths.keys(),
            engine="python",
        )

        df.drop(df.index[0], inplace=True)  # remove frst row which was the header
        df.rename(
            columns=lambda x: x.strip()
        )  # strip leading trailing spaces from header
        date_format = "%d/%m/%Y %H:%M:%S"
        df["datetime"] = pd.to_datetime(df["datetime"], format=date_format)
        logger.warning("date format; {format}".format(format=date_format))

        return df


def dateparse(year, monthday, time):
    return datetime.datetime(int(year), int(monthday[0:2]), int(monthday[2:4]), int(time[0:2]))


def dateparse_loop(years, monthdays, times):
    ret = []
    for year, monthday, time in zip(list(years), list(monthdays), list(times)):
        ret.append(dateparse(year, monthday, time))
    return ret


def parse_on_wave(filepath):
    """
    parser for csv on wave files
    :param filepath:
    :return: dataframe of data
    """

    col_names = [
        "Received",
        "Year",
        "MonthDay",
        "Time",
        "Buoy ID",
        "Location",
        "Number of Zero Crossings",
        "Average Wave Height (Havg)",
        "Tz",
        "Max Wave Height (Hmax)",
        "Significant Wave Height (Hsig)",
        "Significant Wave Period (Tsig)",
        "H 10",
        "T 10",
        "Mean Period",
        "Peak Period",
        "Tp5",
        "Hm0",
        "Mean Magnetic Direction",
        "Mean Spread",
        "Mean True Direction",
        "Te",
        "Wave Steepness",
    ]
    if filepath.endswith(".WAVE"):
        df = pd.read_csv(
            filepath,
            sep="\t",
            engine="python",
            names=col_names,
            skiprows=1,
            date_parser=dateparse_loop,
            parse_dates={"datetime": ["Year", "MonthDay", "Time"]},
        )

        df.drop(df.index[0], inplace=True)  # remove frst row which was the header
        # df.rename(columns=lambda x: x.strip())  # strip leading trailing spaces from header
        # date_format = '%d/%m/%Y %H:%M:%S'
        # df['datetime'] = pd.to_datetime(df['datetime'], format=date_format)
        # logger.warning('date format; {format}'.format(format=date_format))
        return df


def gen_nc_on_wave_dm_deployment(filepath, metadata, output_path):
    """
    generate a FV01 NetCDF file of current data.
    :param filepath_path: the path to a wave file to parse
    :param metadata: metadata output from metadata_info function
    :param output_path: NetCDF file output path
    :return: output file path
    """

    wave_df = parse_on_wave(filepath)  # only one file

    # substract timezone to be in UTC
    wave_df["datetime"] = wave_df["datetime"].dt.tz_localize(None).astype(
        "O"
    ).values - datetime.timedelta(hours=metadata["timezone"])

    var_mapping = param_mapping_parser(ON_WAVE_PARAMETER_MAPPING)
    site_code = metadata["site_code"]
    nc_file_name = "DTA_{date_start}_{site_code}_WAVERIDER_FV01_END-{date_end}.nc".format(
        date_start=wave_df.datetime.dt.strftime("%Y%m%dT%H%M%SZ").values.min(),
        site_code=site_code,
        date_end=wave_df.datetime.dt.strftime("%Y%m%dT%H%M%SZ").values.max(),
    )

    temp_dir = tempfile.mkdtemp()
    nc_file_path = os.path.join(temp_dir, nc_file_name)

    try:
        with Dataset(nc_file_path, "w", format="NETCDF4") as nc_file_obj:
            nc_file_obj.createDimension("TIME", wave_df.datetime.shape[0])
            nc_file_obj.createDimension("station_id_strlen", 30)

            nc_file_obj.createVariable("LATITUDE", "d", fill_value=99999.0)
            nc_file_obj.createVariable("LONGITUDE", "d", fill_value=99999.0)
            nc_file_obj.createVariable(
                "STATION_ID", "S1", ("TIME", "station_id_strlen")
            )

            nc_file_obj["LATITUDE"][:] = metadata["latitude"]
            nc_file_obj["LONGITUDE"][:] = metadata["longitude"]
            nc_file_obj["STATION_ID"][:] = [
                stringtochar(np.array(metadata["site_name"], "S30"))
            ] * wave_df.shape[0]

            var_time = nc_file_obj.createVariable("TIME", "d", "TIME")

            # add gatts and variable attributes as stored in config files
            generate_netcdf_att(
                nc_file_obj, NC_ATT_CONFIG, conf_file_point_of_truth=True
            )

            time_val_dateobj = date2num(
                wave_df.datetime.dt.to_pydatetime(), var_time.units, var_time.calendar
            )

            var_time[:] = time_val_dateobj

            df_varname_ls = list(wave_df[wave_df.keys()].columns.values)
            df_varname_ls.remove("datetime")

            for df_varname in df_varname_ls:
                df_varname_mapped_equivalent = df_varname
                try:
                    mapped_varname = var_mapping.loc[df_varname_mapped_equivalent][
                        "VARNAME"
                    ]
                except Exception as e:
                    continue

                dtype = wave_df[df_varname].values.dtype
                if dtype == np.dtype("int64"):
                    dtype = np.dtype("int16")  # short
                else:
                    dtype = np.dtype("f")

                nc_file_obj.createVariable(mapped_varname, dtype, "TIME")
                set_var_attr(
                    nc_file_obj,
                    var_mapping,
                    mapped_varname,
                    df_varname_mapped_equivalent,
                    dtype,
                )
                setattr(
                    nc_file_obj[mapped_varname],
                    "coordinates",
                    "TIME LATITUDE LONGITUDE",
                )

                nc_file_obj[mapped_varname][:] = wave_df[df_varname].values

            set_glob_attr(nc_file_obj, wave_df, metadata)

        # we do this for pipeline v2
        # os.chmod(nc_file_path, 0664)
        shutil.move(nc_file_path, output_path)

    except Exception as err:
        raise
        logger.error(err)

    shutil.rmtree(temp_dir)

    return os.path.join(output_path, os.path.basename(nc_file_path))


# fname = "/source/so_imos/TAS01000/2018/03/WAVE/20180302.WAVE"
# data = parse_on_wave(fname)
