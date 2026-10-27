package com.example.shop.report.listener;

import com.example.shop.common.cdc.CdcEvent;
import com.example.shop.common.cdc.CdcTables;
import com.example.shop.report.mapper.StoreMapper;
import javax.annotation.Resource;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

/** Keeps a copy of the store dimension next to the reports. */
@Component
public class StoreSyncListener {

    @Resource
    private StoreMapper storeMapper;

    @KafkaListener(topics = "cdc.shop_member", groupId = "report-store-sync")
    public void onMessage(CdcEvent event) {
        if (!event.matches(CdcTables.STORE_TABLES)) {
            return;
        }
        storeMapper.upsert(event.getId(), event.getJson());
    }
}
