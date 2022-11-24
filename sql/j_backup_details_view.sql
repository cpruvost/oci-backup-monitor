CREATE OR REPLACE VIEW j_backup_detail_view
AS SELECT ba.id, ba.created_on, ba.last_modified, ba.version, jt.*
FROM backup ba,
json_table(ba.json_document, '$'
              COLUMNS (
                eventtype        VARCHAR2(100)        PATH '$.eventType',
                cloudeventsversion        VARCHAR2(10)  PATH '$.cloudEventsVersion',
                eventtypeversion        VARCHAR2(10) PATH '$.eventTypeVersion',
                source           VARCHAR2(50)  PATH '$.source',
                compartmentid    VARCHAR2(200) PATH '$.data.compartmentId',
                compartmentname    VARCHAR2(100) PATH '$.data.compartmentName',
                resourcename    VARCHAR2(200) PATH '$.data.resourceName',
                resourceid    VARCHAR2(200) PATH '$.data.resourceId',
                availabilitydomain    VARCHAR2(200) PATH '$.data.availabilityDomain'
              )) jt;

create search index srchidx on backup (json_document) for json;              