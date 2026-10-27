package com.example.shop.report.listener;

import com.example.shop.common.cdc.CdcEvent;
import com.example.shop.common.cdc.CdcTables;
import com.example.shop.report.service.DailySalesService;
import javax.annotation.Resource;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.stereotype.Component;

@Component
public class DailySalesListener {

    @Resource
    private DailySalesService dailySalesService;

    @KafkaListener(topics = "cdc.shop_order", groupId = "report-daily-sales")
    public void onMessage(CdcEvent event) {
        if (!event.matches(CdcTables.ORDER_TABLES)) {
            return;
        }
        dailySalesService.refresh(event.getDay(), event.getId());
    }
}
