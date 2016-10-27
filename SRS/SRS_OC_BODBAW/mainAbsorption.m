function mainAbsorption()
%% mainAbsorption
% this processes all the XLS absorption files found in 'data_absorption.path' from config.txt
% to their recepective CSV files and NetCDF files. 
% 2 folders are created, 
% -CSV : the content of this folder has to be copied to the public folder
% of the IMOS cloud storage, at this location SRS/BioOptical
% -NetCDF : the content of this folder has to be copied to the opendap folder
% of the IMOS cloud storage, at this location SRS/BioOptical
% 
% A SQL script is also created to load to the IMOS database in oder to
% populate the table used by geoserver. This script has to be loaded
% manually afterwards.
% Finally, the original XLS file stays at the same location.
%
%
% Establish bio-optical data base of Australian Waters (SRS-OC-BODBAW)
% This database will be used to assess accuracy of Satellite ocean colour products for current
% and forthcoming satellite missions for the Australian Waters. The match-up dataset is
% essential to assess ocean colour products in the Australian region (e.g. chlorophyll a
% concentrations, phytoplankton species composition and primary production).  Such a data
% set is crucial to quantify the uncertainty in the ocean colour products in our region.
%
%
% Syntax:  mainAbsorption
%
% Inputs: DATA - structure created by Absorption_CSV_reader
%         METADATA - structure created by Absorption_CSV_reader
%         FileName - filename created by createAbsorptionFilename
%         folderHierarchy - folder structure hierarchy created by createAbsorptionFilename
% Outputs: logfile
%
%
% Example:
%    mainAbsorption
%
% Other m-files
% required: IMOS User Code Library
% Other files required:config.txt
% Subfunctions: mkpath
% MAT-files required: none
%
% See also:
% Absorption_CSV_reader,createAbsorptionFilename,processAbsorption,CreateBioOptical_Absorption_SQL_fromCSV,CreateBioOptical_Absorption_NetCDF
%
% Author: Laurent Besnard, IMOS/eMII
% email: laurent.besnard@utas.edu.au
% Website: http://imos.org.au/  http://froggyscripts.blogspot.com
% Aug 2011; Last revision: 28-Nov-2012

WhereAreScripts=what;
Toolbox_Matlab_Folder=WhereAreScripts.path;
addpath(genpath(Toolbox_Matlab_Folder));

DataFileFolder=readConfig('data_absorption.path', 'config.txt','=');
xlsFiles=dir (strcat(DataFileFolder,filesep,'*.xls'));

diary (strcat(DataFileFolder,filesep,readConfig('logFile.absorption.name', 'config.txt','=')));

for ii=1:length(xlsFiles)
    processAbsorption(DataFileFolder,xlsFiles(ii).name)
end
diary off

end