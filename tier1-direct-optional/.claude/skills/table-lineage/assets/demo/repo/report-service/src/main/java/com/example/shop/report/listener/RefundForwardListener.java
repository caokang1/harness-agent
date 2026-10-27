package com.example.shop.report.listener;

import com.example.shop.common.cdc.CdcEvent;
import com.example.shop.common.cdc.CdcTables;
import com.example.shop.report.constants.ReportTopics;
import javax.annotation.Resource;
import org.springframework.kafka.annotation.KafkaListener;
import org.springframework.kafka.core.KafkaTemplate;
import org.springframework.stereotype.Component;

/** Re-publishes refund changes on an internal topic so slow consumers do not block the binlog stream. */
@Component
public class RefundForwardListener {

    @Resource
    private KafkaTemplate<String, String> kafkaTemplate;

    @KafkaListener(topics = "cdc.shop_order", groupId = "report-refund-forward")
    public void onMessage(CdcEvent event) {
        if (!event.matches(CdcTables.REFUND_TABLES)) {
            return;
        }
        kafkaTemplate.send(ReportTopics.REFUND, event.getJson());
    }
}
