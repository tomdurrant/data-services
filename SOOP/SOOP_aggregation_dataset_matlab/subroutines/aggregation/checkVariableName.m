function [fileList]=checkVariableName(fileList)
% we check that all the variable from the files in fileList are all
% similar,ie they don't have any difference of upper or lower case.
% In the opposite, we use the first file from fileList as a proxy
% to define the good variable names and searh for the equivalent ones.
% We modify some files with NCML, and change the fileList by adding those
% NCML instead of NetCDF files.

isFileListCorrupted=0;

nc = netcdf.open(fileList{1},'NC_NOWRITE');%proxy data set
[varnameReference,~]=listVarNC(nc);
netcdf.close(nc);
nVar=length(varnameReference);

nFiles=length(fileList);
for jjFile=2:nFiles
    nc = netcdf.open(fileList{jjFile},'NC_NOWRITE');
    [varnameFile,~]=listVarNC(nc);
    netcdf.close(nc);
    
    % m=int16(find(ismember( varnameFile(:), varnameReference(:))==0)')
    if nVar== length(varnameFile)
        [tf, loc] =ismember( varnameFile(:), varnameReference(:));
        m=find(tf==0)';
        
        if ~isempty(m)
            isFileListCorrupted=1;
            n=int16(find(ismember( (1:nVar),loc)==0)'); %pretty tricky :)
            varnameFile(m);
            varnameReference(n);
            ncmlFile=modifyNcToNCML(fileList{jjFile},varnameFile(m),varnameReference(n));
            fileList{jjFile}=ncmlFile;
        end
    else
        fprintf('%s - WARNING - The data set:%s; has different Variable numbers. The aggregation might still work\n',datestr(now),fileList{1})
        return
    end
    
end

if isFileListCorrupted
    fprintf('%s - WARNING - The data set:%s; has unconsistent Variable names. We create ncml files to match variable names with the first file of the list.\n',datestr(now),fileList{1})
end

end


function  [ncmlFile]=modifyNcToNCML(netcdfFile,OldVarname,newVarname)
%% we replace a list of old varnames by new ones in a netcdf file. The
%% modifications are written in an NCML file at the same location that the
%% physical netcdf file

ncmlFile=strcat(netcdfFile(1:end-3),'.ncml');
nVarToModify=length(OldVarname);

ncmlFile_fid = fopen(ncmlFile, 'w+');
fprintf(ncmlFile_fid,'<?xml version="1.0" encoding="UTF-8"?>\n');
fprintf(ncmlFile_fid,'  <netcdf xmlns="http://www.unidata.ucar.edu/namespaces/netcdf/ncml-2.2" \n   location="file:%s"> \n',netcdfFile); %add all the nc files from the list

for iiVarToModify=1:nVarToModify
    fprintf(ncmlFile_fid,char(strcat(' <variable name="',newVarname(iiVarToModify),'" orgName="',OldVarname(iiVarToModify),'"/> \n')));
end
fprintf(ncmlFile_fid,'</netcdf> \n');
fclose(ncmlFile_fid);
end
