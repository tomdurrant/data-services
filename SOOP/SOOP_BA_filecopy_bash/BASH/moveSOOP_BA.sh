#!/bin/bash

RSYNC_SOURCE_PATH=$INCOMING_DIR/SOOP/BA/Processed_data
RSYNC_SOURCE_RAW_PATH=$INCOMING_DIR/SOOP/BA/Raw_data
RSYNC_DEST_PUBLIC_PATH=$PUBLIC_DIR/SOOP/BA
RSYNC_DEST_RAW_PATH=$ARCHIVE_DIR/SOOP/BA/raw
RSYNC_DESTINATION_PATH=$OPENDAP_IMOS_DIR/SOOP/SOOP-BA

# rsync between staging and public : move png's
rsync -vr  --remove-source-files --include '+ */' --include '*.png' --include '*.inf' --include '*.csv' --exclude '- *' ${RSYNC_SOURCE_PATH}/ ${RSYNC_DEST_PUBLIC_PATH}/

# rsync between staging and opendap : move data to opendap
rsync -vr --remove-source-files --include '+ */' --include '*.nc' --exclude '*.png'  ${RSYNC_SOURCE_PATH}/ ${RSYNC_DESTINATION_PATH}/
